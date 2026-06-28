# Webhook System for Event-Driven Integrations

import json
import hmac
import hashlib
from datetime import datetime, timedelta
import logging

from django.db import models
from django.dispatch import Signal
from rest_framework import serializers, viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
import requests
from celery import shared_task

logger = logging.getLogger('webhooks')

# ============================================================
# WEBHOOK MODELS
# ============================================================

class WebhookEndpoint(models.Model):
    """Webhook endpoint configuration"""
    EVENTS = [
        ('order.created', 'Order Created'),
        ('order.updated', 'Order Updated'),
        ('order.delivered', 'Order Delivered'),
        ('order.cancelled', 'Order Cancelled'),
        ('payment.completed', 'Payment Completed'),
        ('payment.failed', 'Payment Failed'),
        ('product.stock_low', 'Product Stock Low'),
        ('product.out_of_stock', 'Product Out of Stock'),
        ('user.registered', 'User Registered'),
        ('user.verified', 'User Verified'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('disabled', 'Disabled'),
    ]
    
    # Webhook configuration
    name = models.CharField(max_length=200)
    url = models.URLField()
    events = models.JSONField(default=list)  # List of event types to listen for
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Security
    secret = models.CharField(max_length=255, editable=False)
    headers = models.JSONField(default=dict)  # Custom headers to send
    
    # Metadata
    organization = models.CharField(max_length=200, blank=True)
    contact_email = models.EmailField(blank=True)
    
    # Retry configuration
    max_retries = models.IntegerField(default=5)
    retry_delay = models.IntegerField(default=300)  # seconds
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_triggered = models.DateTimeField(null=True, blank=True)
    
    def generate_secret(self):
        """Generate webhook secret"""
        import secrets
        self.secret = secrets.token_urlsafe(32)
    
    def generate_signature(self, payload):
        """Generate HMAC-SHA256 signature for payload"""
        message = json.dumps(payload, sort_keys=True).encode()
        signature = hmac.new(
            self.secret.encode(),
            message,
            hashlib.sha256
        ).hexdigest()
        return signature
    
    class Meta:
        db_table = 'webhooks_endpoint'


class WebhookEvent(models.Model):
    """Webhook event log"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('delivered', 'Delivered'),
    ]
    
    endpoint = models.ForeignKey(WebhookEndpoint, on_delete=models.CASCADE, related_name='events')
    event_type = models.CharField(max_length=50)
    payload = models.JSONField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Response tracking
    response_status = models.IntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)
    
    # Retry tracking
    attempt_count = models.IntegerField(default=0)
    next_retry = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'webhooks_event'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['endpoint', 'status']),
            models.Index(fields=['created_at']),
        ]


# ============================================================
# WEBHOOK SIGNALS
# ============================================================

# Define custom signals for webhook events
order_created = Signal()
order_updated = Signal()
order_delivered = Signal()
order_cancelled = Signal()
payment_completed = Signal()
payment_failed = Signal()
product_stock_low = Signal()
user_registered = Signal()

WEBHOOK_SIGNALS = {
    'order.created': order_created,
    'order.updated': order_updated,
    'order.delivered': order_delivered,
    'order.cancelled': order_cancelled,
    'payment.completed': payment_completed,
    'payment.failed': payment_failed,
    'product.stock_low': product_stock_low,
    'user.registered': user_registered,
}


# ============================================================
# WEBHOOK DISPATCHER
# ============================================================

class WebhookDispatcher:
    """Send webhooks to registered endpoints"""
    
    @staticmethod
    def dispatch_event(event_type, payload):
        """Dispatch webhook event to all relevant endpoints"""
        endpoints = WebhookEndpoint.objects.filter(
            status='active',
            events__contains=event_type
        )
        
        for endpoint in endpoints:
            WebhookDispatcher.send_webhook(endpoint, event_type, payload)
    
    @staticmethod
    def send_webhook(endpoint, event_type, payload):
        """Send webhook to endpoint"""
        # Create event record
        event = WebhookEvent.objects.create(
            endpoint=endpoint,
            event_type=event_type,
            payload=payload,
        )
        
        # Send asynchronously
        send_webhook_task.delay(event.id)
        
        return event
    
    @staticmethod
    def verify_webhook_signature(secret, signature, payload):
        """Verify webhook signature"""
        expected_signature = hmac.new(
            secret.encode(),
            json.dumps(payload, sort_keys=True).encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)


# ============================================================
# CELERY TASK FOR SENDING WEBHOOKS
# ============================================================

@shared_task(bind=True, max_retries=5)
def send_webhook_task(self, event_id):
    """Send webhook with retry logic"""
    try:
        event = WebhookEvent.objects.get(id=event_id)
        endpoint = event.endpoint
        
        # Prepare headers
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Joan-Kuku-Farm/1.0',
            'X-Webhook-Event': event.event_type,
            'X-Webhook-Delivery': str(event.id),
            'X-Webhook-Signature': endpoint.generate_signature(event.payload),
            'X-Webhook-Timestamp': datetime.now().isoformat(),
        }
        
        # Add custom headers
        headers.update(endpoint.headers)
        
        # Send request
        response = requests.post(
            endpoint.url,
            json=event.payload,
            headers=headers,
            timeout=10,
        )
        
        # Update event
        event.response_status = response.status_code
        event.response_body = response.text[:500]  # Store first 500 chars
        event.attempt_count += 1
        
        # Check if successful
        if response.status_code in [200, 201, 202, 204]:
            event.status = 'delivered'
            event.delivered_at = datetime.now()
            endpoint.last_triggered = datetime.now()
            endpoint.save()
            logger.info(f'Webhook delivered: {event_id}')
        else:
            raise Exception(f'HTTP {response.status_code}')
        
        event.save()
        
    except Exception as exc:
        event = WebhookEvent.objects.get(id=event_id)
        event.status = 'failed'
        event.attempt_count += 1
        
        # Schedule retry
        if event.attempt_count < event.endpoint.max_retries:
            retry_delay = event.endpoint.retry_delay * (2 ** (event.attempt_count - 1))
            event.next_retry = datetime.now() + timedelta(seconds=retry_delay)
            event.save()
            
            # Retry with exponential backoff
            raise self.retry(exc=exc, countdown=retry_delay)
        else:
            event.status = 'failed'
            logger.error(f'Webhook failed after {event.attempt_count} attempts: {event_id}')
        
        event.save()


# ============================================================
# WEBHOOK SERIALIZERS
# ============================================================

class WebhookEndpointSerializer(serializers.ModelSerializer):
    """Serializer for webhook endpoints"""
    
    class Meta:
        model = WebhookEndpoint
        fields = [
            'id', 'name', 'url', 'events', 'status', 'headers',
            'organization', 'contact_email', 'max_retries',
            'created_at', 'updated_at', 'last_triggered'
        ]
        read_only_fields = ['created_at', 'updated_at', 'last_triggered']
    
    def create(self, validated_data):
        """Create endpoint with generated secret"""
        endpoint = super().create(validated_data)
        endpoint.generate_secret()
        endpoint.save()
        return endpoint


class WebhookEventSerializer(serializers.ModelSerializer):
    """Serializer for webhook events"""
    
    class Meta:
        model = WebhookEvent
        fields = [
            'id', 'endpoint', 'event_type', 'status',
            'response_status', 'attempt_count', 'created_at',
            'delivered_at', 'next_retry'
        ]
        read_only_fields = fields


# ============================================================
# WEBHOOK VIEWSETS
# ============================================================

class WebhookEndpointViewSet(viewsets.ModelViewSet):
    """Manage webhook endpoints"""
    queryset = WebhookEndpoint.objects.all()
    serializer_class = WebhookEndpointSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter by current user/organization"""
        return self.queryset.filter(organization=self.request.user.username)
    
    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """Send test webhook"""
        endpoint = self.get_object()
        
        test_payload = {
            'event_type': 'test.webhook',
            'timestamp': datetime.now().isoformat(),
            'data': {
                'message': 'This is a test webhook from Joan Kuku Farm',
            }
        }
        
        event = WebhookDispatcher.send_webhook(
            endpoint,
            'test.webhook',
            test_payload
        )
        
        return Response({
            'message': 'Test webhook sent',
            'event_id': event.id,
        })
    
    @action(detail=True, methods=['get'])
    def events(self, request, pk=None):
        """Get recent events for endpoint"""
        endpoint = self.get_object()
        events = endpoint.events.all()[:10]
        serializer = WebhookEventSerializer(events, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def available_events(self, request):
        """List all available webhook events"""
        return Response({
            'events': [
                {'key': key, 'label': label}
                for key, label in WebhookEndpoint.EVENTS
            ]
        })


class WebhookEventViewSet(viewsets.ReadOnlyModelViewSet):
    """View webhook events"""
    queryset = WebhookEvent.objects.all()
    serializer_class = WebhookEventSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter by user's endpoints"""
        return self.queryset.filter(
            endpoint__organization=self.request.user.username
        )
    
    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        """Manually retry failed webhook"""
        event = self.get_object()
        
        if event.status == 'delivered':
            return Response(
                {'error': 'Event already delivered'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Reset and retry
        event.attempt_count = 0
        event.status = 'pending'
        event.save()
        
        send_webhook_task.delay(event.id)
        
        return Response({'message': 'Webhook retry scheduled'})


# ============================================================
# WEBHOOK USAGE EXAMPLES
# ============================================================

"""
1. TRIGGER WEBHOOK FROM ORDER CREATION:

from apps.webhooks.system import WebhookDispatcher

def create_order(request):
    # Create order
    order = Order.objects.create(...)
    
    # Dispatch webhook
    WebhookDispatcher.dispatch_event('order.created', {
        'id': order.id,
        'order_id': order.order_id,
        'total_amount': str(order.total_amount),
        'status': order.status,
        'created_at': order.created_at.isoformat(),
    })
    
    return Response({'order_id': order.order_id})


2. WEBHOOK SIGNATURE VERIFICATION (Client Side):

import hmac
import hashlib
import json

def verify_webhook(request):
    signature = request.headers.get('X-Webhook-Signature')
    payload = request.body
    
    expected_signature = hmac.new(
        WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(signature, expected_signature):
        return Response({'error': 'Invalid signature'}, status=401)
    
    data = json.loads(payload)
    # Process webhook...
    return Response({'received': True})


3. WEBHOOK PAYLOAD EXAMPLES:

Order Created:
{
    "event_type": "order.created",
    "timestamp": "2024-01-15T10:30:00Z",
    "data": {
        "id": 123,
        "order_id": "JKF-20240115-ABC123",
        "customer_id": 45,
        "total_amount": "5000.00",
        "items": [
            {"product_id": 1, "quantity": 5, "price": "1000.00"}
        ],
        "status": "pending"
    }
}

Payment Completed:
{
    "event_type": "payment.completed",
    "timestamp": "2024-01-15T10:35:00Z",
    "data": {
        "payment_id": 456,
        "order_id": "JKF-20240115-ABC123",
        "amount": "5000.00",
        "method": "mpesa",
        "transaction_id": "MPR24011500123",
        "status": "completed"
    }
}
"""

# ============================================================
# SETTINGS.PY ADDITIONS
# ============================================================

"""
Add to settings.py:

WEBHOOK_CONFIG = {
    'MAX_RETRIES': 5,
    'RETRY_DELAY': 300,  # 5 minutes
    'TIMEOUT': 10,  # seconds
    'MAX_PAYLOAD_SIZE': 1048576,  # 1 MB
}

LOGGING = {
    ...
    'loggers': {
        'webhooks': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': False,
        }
    }
}

# Add to urls.py:
from rest_framework.routers import DefaultRouter
from apps.webhooks.views import WebhookEndpointViewSet, WebhookEventViewSet

router = DefaultRouter()
router.register(r'webhooks/endpoints', WebhookEndpointViewSet)
router.register(r'webhooks/events', WebhookEventViewSet)

urlpatterns = [
    ...
    path('api/', include(router.urls)),
]
"""