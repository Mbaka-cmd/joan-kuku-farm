# Payment Gateway Integration Hub - Multi-Gateway Support

from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import logging

logger = logging.getLogger('payments')

# ============================================================
# PAYMENT GATEWAY MODELS
# ============================================================

class PaymentGateway(models.Model):
    """Payment gateway configurations"""
    GATEWAY_TYPE = [
        ('mpesa', 'M-Pesa'),
        ('stripe', 'Stripe'),
        ('paypal', 'PayPal'),
        ('razorpay', 'Razorpay'),
        ('square', 'Square'),
        ('bank_transfer', 'Bank Transfer'),
        ('wallet', 'Digital Wallet'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('testing', 'Testing'),
        ('inactive', 'Inactive'),
    ]
    
    # Gateway
    name = models.CharField(max_length=255)
    gateway_type = models.CharField(max_length=50, choices=GATEWAY_TYPE)
    
    # Credentials
    api_key = models.CharField(max_length=500)
    api_secret = models.CharField(max_length=500, blank=True)
    webhook_secret = models.CharField(max_length=500, blank=True)
    
    # Configuration
    is_primary = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='testing')
    
    # Fees
    transaction_fee_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    fixed_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Limits
    min_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    max_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Webhooks
    webhook_url = models.URLField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'payment_gateway'
        unique_together = ['gateway_type', 'status']


class PaymentMethod(models.Model):
    """Customer payment methods"""
    METHOD_TYPE = [
        ('card', 'Credit/Debit Card'),
        ('mpesa', 'M-Pesa'),
        ('bank', 'Bank Transfer'),
        ('wallet', 'Digital Wallet'),
        ('check', 'Check'),
    ]
    
    customer = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE)
    
    # Method
    method_type = models.CharField(max_length=50, choices=METHOD_TYPE)
    
    # Details (encrypted)
    token = models.CharField(max_length=500)  # Gateway token
    
    # Card info (partial)
    last_four = models.CharField(max_length=4, blank=True)
    card_brand = models.CharField(max_length=50, blank=True)
    expiry_month = models.IntegerField(null=True, blank=True)
    expiry_year = models.IntegerField(null=True, blank=True)
    
    # Account info
    account_holder = models.CharField(max_length=255, blank=True)
    account_number = models.CharField(max_length=100, blank=True)
    
    # Settings
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    # Trust
    is_verified = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'payment_method'


class GatewayTransaction(models.Model):
    """Track gateway transactions"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('authorized', 'Authorized'),
        ('captured', 'Captured'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    # Transaction
    transaction_id = models.CharField(max_length=100, unique=True)
    gateway = models.ForeignKey(PaymentGateway, on_delete=models.PROTECT)
    
    # Reference
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, null=True, blank=True)
    
    # Amounts
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='KES')
    
    # Gateway response
    gateway_reference = models.CharField(max_length=100, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Error
    error_code = models.CharField(max_length=100, blank=True)
    error_message = models.TextField(blank=True)
    
    # Dates
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'gateway_transaction'
        ordering = ['-created_at']


class PaymentWebhook(models.Model):
    """Track payment webhooks"""
    # Webhook
    webhook_id = models.CharField(max_length=100, unique=True)
    gateway = models.ForeignKey(PaymentGateway, on_delete=models.CASCADE)
    
    # Event
    event_type = models.CharField(max_length=100)
    
    # Data
    payload = models.JSONField()
    
    # Processing
    is_processed = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    # Error
    error = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'payment_webhook'


# ============================================================
# PAYMENT GATEWAY ENGINE
# ============================================================

class PaymentGatewayEngine:
    """Multi-gateway payment processing"""
    
    @staticmethod
    def select_gateway(amount, customer_type='regular'):
        """Select best gateway for transaction"""
        from apps.payments.models import PaymentGateway
        
        gateways = PaymentGateway.objects.filter(
            status='active',
            is_primary=True
        )
        
        # Filter by amount limits
        suitable_gateways = gateways.filter(
            min_amount__lte=amount,
            max_amount__gte=amount
        )
        
        if not suitable_gateways.exists():
            suitable_gateways = gateways
        
        # Select by lowest fees
        best_gateway = suitable_gateways.order_by('transaction_fee_percent').first()
        
        return best_gateway
    
    @staticmethod
    def process_payment(order, payment_method, amount):
        """Process payment through gateway"""
        from apps.payments.models import PaymentGateway, GatewayTransaction
        
        # Select gateway
        gateway = PaymentGatewayEngine.select_gateway(amount)
        
        if not gateway:
            return {
                'success': False,
                'error': 'No suitable payment gateway found',
            }
        
        # Create transaction record
        import uuid
        transaction = GatewayTransaction.objects.create(
            transaction_id=str(uuid.uuid4()),
            gateway=gateway,
            order=order,
            amount=Decimal(str(amount)),
        )
        
        try:
            # Process based on gateway type
            if gateway.gateway_type == 'mpesa':
                result = PaymentGatewayEngine.process_mpesa(transaction, payment_method)
            
            elif gateway.gateway_type == 'stripe':
                result = PaymentGatewayEngine.process_stripe(transaction, payment_method)
            
            elif gateway.gateway_type == 'paypal':
                result = PaymentGatewayEngine.process_paypal(transaction, payment_method)
            
            else:
                result = {'success': False, 'error': 'Gateway not implemented'}
            
            if result['success']:
                transaction.status = 'captured'
                transaction.gateway_reference = result.get('reference', '')
            else:
                transaction.status = 'failed'
                transaction.error_message = result.get('error', '')
            
            transaction.save()
            
            return result
        
        except Exception as e:
            transaction.status = 'failed'
            transaction.error_message = str(e)
            transaction.save()
            
            logger.error(f'Payment processing failed: {e}')
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def process_mpesa(transaction, phone_number):
        """Process M-Pesa payment"""
        # Integration with Safaricom M-Pesa API
        # This would call Safaricom's API
        
        try:
            # Simulate M-Pesa processing
            logger.info(f'Processing M-Pesa: {phone_number} - KES {transaction.amount}')
            
            return {
                'success': True,
                'reference': f"MPesa-{transaction.transaction_id[:8]}",
                'message': 'Payment initiated',
            }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
            }
    
    @staticmethod
    def process_stripe(transaction, payment_method):
        """Process Stripe payment"""
        # Integration with Stripe API
        try:
            import stripe
            
            gateway = transaction.gateway
            stripe.api_key = gateway.api_key
            
            # Create charge
            charge = stripe.Charge.create(
                amount=int(transaction.amount * 100),
                currency='kes',
                source=payment_method.token,
                description=f"Order {transaction.order.order_id}",
            )
            
            return {
                'success': True,
                'reference': charge.id,
                'message': 'Payment captured',
            }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
            }
    
    @staticmethod
    def process_paypal(transaction, email):
        """Process PayPal payment"""
        # Integration with PayPal API
        try:
            logger.info(f'Processing PayPal: {email} - KES {transaction.amount}')
            
            return {
                'success': True,
                'reference': f"PayPal-{transaction.transaction_id[:8]}",
                'message': 'Payment initiated',
            }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
            }
    
    @staticmethod
    def process_webhook(gateway, payload):
        """Process payment webhook"""
        from apps.payments.models import PaymentWebhook, GatewayTransaction
        import uuid
        
        webhook = PaymentWebhook.objects.create(
            webhook_id=str(uuid.uuid4()),
            gateway=gateway,
            event_type=payload.get('type', 'unknown'),
            payload=payload,
        )
        
        try:
            # Update transaction status based on webhook
            gateway_ref = payload.get('id') or payload.get('reference')
            
            transaction = GatewayTransaction.objects.get(
                gateway_reference=gateway_ref
            )
            
            if payload.get('status') == 'succeeded':
                transaction.status = 'captured'
            elif payload.get('status') == 'failed':
                transaction.status = 'failed'
                transaction.error_message = payload.get('error', '')
            
            transaction.save()
            
            webhook.is_processed = True
            webhook.processed_at = timezone.now()
        
        except Exception as e:
            webhook.error = str(e)
            logger.error(f'Webhook processing failed: {e}')
        
        webhook.save()
        
        return webhook


# ============================================================
# CELERY TASKS
# ============================================================

"""
from celery import shared_task

@shared_task
def retry_failed_payments():
    '''Retry failed payment transactions'''
    from apps.payments.models import GatewayTransaction
    
    failed = GatewayTransaction.objects.filter(
        status='failed',
        created_at__gte=timezone.now() - timedelta(hours=24)
    )
    
    for transaction in failed:
        # Retry logic
        pass

@shared_task
def process_pending_webhooks():
    '''Process pending payment webhooks'''
    from apps.payments.models import PaymentWebhook
    
    pending = PaymentWebhook.objects.filter(is_processed=False)
    
    for webhook in pending:
        PaymentGatewayEngine.process_webhook(webhook.gateway, webhook.payload)

# Add to CELERY_BEAT_SCHEDULE:
'retry-payments': {
    'task': 'apps.payments.tasks.retry_failed_payments',
    'schedule': 3600.0,  # Hourly
},
'process-webhooks': {
    'task': 'apps.payments.tasks.process_pending_webhooks',
    'schedule': 300.0,  # Every 5 minutes
},
"""