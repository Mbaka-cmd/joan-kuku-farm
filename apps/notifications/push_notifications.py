# Push Notifications System - Email, SMS, Push, In-App

from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta
import logging

logger = logging.getLogger('notifications')

# ============================================================
# NOTIFICATION MODELS
# ============================================================

class NotificationTemplate(models.Model):
    """Notification templates"""
    CHANNEL_CHOICES = [
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('push', 'Push Notification'),
        ('in_app', 'In-App'),
        ('whatsapp', 'WhatsApp'),
    ]
    
    name = models.CharField(max_length=255)
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)
    
    # Template content
    subject = models.CharField(max_length=255, blank=True)  # For email
    body = models.TextField()
    
    # Variables
    variables = models.JSONField(default=list)  # {{var_name}}
    
    # Configuration
    priority = models.IntegerField(default=5)  # 1-10
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'notification_template'
        unique_together = ['name', 'channel']


class Notification(models.Model):
    """Sent notifications"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('read', 'Read'),
    ]
    
    CHANNEL_CHOICES = [
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('push', 'Push Notification'),
        ('in_app', 'In-App'),
        ('whatsapp', 'WhatsApp'),
    ]
    
    # Recipient
    user = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE, related_name='notifications')
    
    # Content
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)
    subject = models.CharField(max_length=255, blank=True)
    body = models.TextField()
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True)
    
    # Delivery
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    template = models.ForeignKey(NotificationTemplate, null=True, blank=True, on_delete=models.SET_NULL)
    reference_id = models.CharField(max_length=100, blank=True)  # Order ID, etc
    data = models.JSONField(default=dict)  # Additional data
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'notification'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['channel', 'created_at']),
        ]


class UserNotificationPreference(models.Model):
    """User notification preferences"""
    user = models.OneToOneField('users.CustomUser', on_delete=models.CASCADE)
    
    # Channel preferences
    email_enabled = models.BooleanField(default=True)
    sms_enabled = models.BooleanField(default=True)
    push_enabled = models.BooleanField(default=True)
    in_app_enabled = models.BooleanField(default=True)
    whatsapp_enabled = models.BooleanField(default=False)
    
    # Notification type preferences
    marketing_emails = models.BooleanField(default=True)
    order_updates = models.BooleanField(default=True)
    promotions = models.BooleanField(default=True)
    transactional = models.BooleanField(default=True)
    
    # Frequency
    email_frequency = models.CharField(
        max_length=20,
        choices=[
            ('immediate', 'Immediate'),
            ('daily', 'Daily Digest'),
            ('weekly', 'Weekly'),
        ],
        default='immediate'
    )
    
    # Quiet hours
    quiet_hours_enabled = models.BooleanField(default=False)
    quiet_hours_start = models.TimeField(null=True, blank=True)  # e.g., 22:00
    quiet_hours_end = models.TimeField(null=True, blank=True)    # e.g., 08:00
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_notification_preference'


# ============================================================
# NOTIFICATION DISPATCHER
# ============================================================

class NotificationDispatcher:
    """Send notifications through multiple channels"""
    
    @staticmethod
    def send_notification(user, template_name, variables=None, channels=None):
        """Send notification using template"""
        from apps.notifications.models import NotificationTemplate, Notification
        
        variables = variables or {}
        
        # Get template
        templates = NotificationTemplate.objects.filter(name=template_name, is_active=True)
        
        if not templates.exists():
            logger.error(f'Template not found: {template_name}')
            return None
        
        notifications = []
        
        for template in templates:
            # Check user preferences
            if not NotificationDispatcher.should_send(user, template):
                continue
            
            if channels and template.channel not in channels:
                continue
            
            # Render template
            body = template.body
            subject = template.subject
            
            for var, value in variables.items():
                body = body.replace(f'{{{{{var}}}}}', str(value))
                subject = subject.replace(f'{{{{{var}}}}}', str(value))
            
            # Create notification record
            notification = Notification.objects.create(
                user=user,
                channel=template.channel,
                subject=subject,
                body=body,
                template=template,
                data=variables,
            )
            
            # Send through channel
            NotificationDispatcher.send_by_channel(notification)
            notifications.append(notification)
        
        return notifications
    
    @staticmethod
    def should_send(user, template):
        """Check if should send to user"""
        try:
            pref = user.usernotificationpreference
        except:
            return True  # Send if no preferences set
        
        # Check channel preference
        channel_key = f'{template.channel}_enabled'
        if not getattr(pref, channel_key, True):
            return False
        
        # Check quiet hours
        if pref.quiet_hours_enabled:
            now = timezone.now().time()
            if pref.quiet_hours_start < pref.quiet_hours_end:
                # Quiet hours don't cross midnight
                if pref.quiet_hours_start <= now <= pref.quiet_hours_end:
                    return False
            else:
                # Quiet hours cross midnight
                if now >= pref.quiet_hours_start or now <= pref.quiet_hours_end:
                    return False
        
        return True
    
    @staticmethod
    def send_by_channel(notification):
        """Send notification through specific channel"""
        try:
            if notification.channel == 'email':
                NotificationDispatcher.send_email(notification)
            elif notification.channel == 'sms':
                NotificationDispatcher.send_sms(notification)
            elif notification.channel == 'push':
                NotificationDispatcher.send_push(notification)
            elif notification.channel == 'in_app':
                NotificationDispatcher.send_in_app(notification)
            elif notification.channel == 'whatsapp':
                NotificationDispatcher.send_whatsapp(notification)
        except Exception as e:
            notification.status = 'failed'
            notification.error_message = str(e)
            notification.save()
            logger.error(f'Failed to send notification {notification.id}: {e}')
    
    @staticmethod
    def send_email(notification):
        """Send email notification"""
        from django.core.mail import send_mail
        from django.conf import settings
        
        send_mail(
            subject=notification.subject,
            message=notification.body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[notification.user.email],
            html_message=notification.body,
        )
        
        notification.status = 'sent'
        notification.sent_at = timezone.now()
        notification.save()
    
    @staticmethod
    def send_sms(notification):
        """Send SMS notification"""
        from twilio.rest import Client
        from django.conf import settings
        
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        
        message = client.messages.create(
            body=notification.body,
            from_=settings.TWILIO_PHONE_NUMBER,
            to=notification.user.phone_number,
        )
        
        notification.status = 'sent'
        notification.sent_at = timezone.now()
        notification.save()
    
    @staticmethod
    def send_push(notification):
        """Send push notification"""
        from firebase_admin import messaging
        
        message = messaging.Message(
            notification=messaging.Notification(
                title=notification.subject,
                body=notification.body,
            ),
            data=notification.data,
            token=notification.user.fcm_token,  # Firebase Cloud Messaging token
        )
        
        response = messaging.send(message)
        
        notification.status = 'sent'
        notification.sent_at = timezone.now()
        notification.save()
    
    @staticmethod
    def send_in_app(notification):
        """Store in-app notification"""
        notification.status = 'sent'
        notification.sent_at = timezone.now()
        notification.save()
    
    @staticmethod
    def send_whatsapp(notification):
        """Send WhatsApp notification"""
        from twilio.rest import Client
        from django.conf import settings
        
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        
        message = client.messages.create(
            body=notification.body,
            from_=f"whatsapp:{settings.TWILIO_WHATSAPP_NUMBER}",
            to=f"whatsapp:{notification.user.phone_number}",
        )
        
        notification.status = 'sent'
        notification.sent_at = timezone.now()
        notification.save()


# ============================================================
# CELERY TASKS
# ============================================================

"""
from celery import shared_task

@shared_task
def send_order_confirmation(order_id):
    '''Send order confirmation notification'''
    from apps.orders.models import Order
    from apps.notifications.dispatcher import NotificationDispatcher
    
    order = Order.objects.get(id=order_id)
    
    NotificationDispatcher.send_notification(
        order.customer,
        'order_confirmation',
        variables={
            'order_id': order.order_id,
            'total_amount': order.total_amount,
        },
        channels=['email', 'sms', 'in_app']
    )

@shared_task
def send_promotional_campaign(campaign_id):
    '''Send promotional campaign to users'''
    from apps.notifications.models import Notification
    from django.contrib.auth import get_user_model
    
    User = get_user_model()
    
    # Get all active users
    users = User.objects.filter(is_active=True, email_verified=True)
    
    for user in users:
        send_notification_task.delay(
            user.id,
            'promotional_offer',
            {'discount': '20%'}
        )

@shared_task
def cleanup_old_notifications():
    '''Delete old notifications'''
    from apps.notifications.models import Notification
    
    cutoff = timezone.now() - timedelta(days=30)
    Notification.objects.filter(created_at__lt=cutoff).delete()

# Add to CELERY_BEAT_SCHEDULE:
'send-promotional-campaign': {
    'task': 'apps.notifications.tasks.send_promotional_campaign',
    'schedule': 604800.0,  # Weekly
},
'cleanup-notifications': {
    'task': 'apps.notifications.tasks.cleanup_old_notifications',
    'schedule': 604800.0,  # Weekly
},
"""

# ============================================================
# API ENDPOINTS
# ============================================================

"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

class NotificationViewSet(viewsets.ModelViewSet):
    queryset = Notification.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)
    
    @action(detail=False)
    def unread(self, request):
        '''Get unread notifications'''
        notifications = self.get_queryset().filter(status__in=['sent', 'failed'])
        serializer = NotificationSerializer(notifications, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def mark_as_read(self, request, pk=None):
        '''Mark notification as read'''
        notification = self.get_object()
        notification.status = 'read'
        notification.read_at = timezone.now()
        notification.save()
        return Response({'message': 'Marked as read'})
    
    @action(detail=False, methods=['post'])
    def mark_all_as_read(self, request):
        '''Mark all as read'''
        self.get_queryset().filter(status='sent').update(status='read')
        return Response({'message': 'All marked as read'})

class NotificationPreferenceViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    
    @action(detail=False)
    def my_preferences(self, request):
        '''Get user notification preferences'''
        pref = request.user.usernotificationpreference
        return Response({
            'email': pref.email_enabled,
            'sms': pref.sms_enabled,
            'push': pref.push_enabled,
            'in_app': pref.in_app_enabled,
            'whatsapp': pref.whatsapp_enabled,
        })
    
    @action(detail=False, methods=['post'])
    def update_preferences(self, request):
        '''Update notification preferences'''
        pref = request.user.usernotificationpreference
        
        for channel in ['email', 'sms', 'push', 'in_app', 'whatsapp']:
            if channel in request.data:
                setattr(pref, f'{channel}_enabled', request.data[channel])
        
        pref.save()
        return Response({'message': 'Preferences updated'})
"""