# Return Management System - Returns, Exchanges, Refunds

from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import logging

logger = logging.getLogger('returns')

# ============================================================
# RETURN MODELS
# ============================================================

class ReturnPolicy(models.Model):
    """Return policy configuration"""
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Timeline
    return_window_days = models.IntegerField(default=30)  # Days to initiate return
    refund_processing_days = models.IntegerField(default=14)  # Days to process refund
    
    # Conditions
    condition_choices = [
        ('new', 'Like New'),
        ('good', 'Good Condition'),
        ('fair', 'Fair Condition'),
    ]
    min_condition = models.CharField(max_length=20, choices=condition_choices, default='good')
    
    # Restocking fee
    has_restocking_fee = models.BooleanField(default=False)
    restocking_fee_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Shipping
    free_return_shipping = models.BooleanField(default=True)
    
    # Exclusions
    non_returnable_categories = models.ManyToManyField('products.Category', blank=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'return_policy'


class ReturnRequest(models.Model):
    """Customer return requests"""
    STATUS_CHOICES = [
        ('initiated', 'Initiated'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('in_transit', 'In Transit'),
        ('received', 'Received'),
        ('inspected', 'Inspected'),
        ('refunded', 'Refunded'),
        ('exchanged', 'Exchanged'),
    ]
    
    REASON_CHOICES = [
        ('defective', 'Defective Product'),
        ('not_as_described', 'Not as Described'),
        ('wrong_item', 'Wrong Item Sent'),
        ('damaged', 'Damaged on Arrival'),
        ('changed_mind', 'Changed Mind'),
        ('better_price', 'Found Better Price'),
        ('other', 'Other'),
    ]
    
    CONDITION_CHOICES = [
        ('new', 'Like New'),
        ('good', 'Good Condition'),
        ('fair', 'Fair Condition'),
        ('poor', 'Poor Condition'),
    ]
    
    # Return request
    return_id = models.CharField(max_length=50, unique=True)
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, related_name='returns')
    customer = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE)
    
    # Details
    reason = models.CharField(max_length=30, choices=REASON_CHOICES)
    description = models.TextField()
    
    # Items
    items = models.ManyToManyField('orders.OrderItem', through='ReturnItem')
    
    # Refund
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2)
    refund_method = models.CharField(
        max_length=20,
        choices=[('original', 'Original Payment'), ('store_credit', 'Store Credit'), ('bank_transfer', 'Bank Transfer')]
    )
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='initiated')
    
    # Return shipping
    return_shipping_label = models.URLField(blank=True)
    tracking_number = models.CharField(max_length=100, blank=True)
    
    # Inspection
    condition_on_arrival = models.CharField(max_length=20, choices=CONDITION_CHOICES, blank=True)
    inspection_notes = models.TextField(blank=True)
    
    # Dates
    requested_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'return_request'
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['status', '-requested_at']),
            models.Index(fields=['customer']),
        ]
    
    def save(self, *args, **kwargs):
        if not self.return_id:
            import uuid
            self.return_id = f"RET-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)


class ReturnItem(models.Model):
    """Individual items in return"""
    return_request = models.ForeignKey(ReturnRequest, on_delete=models.CASCADE)
    order_item = models.ForeignKey('orders.OrderItem', on_delete=models.CASCADE)
    
    quantity = models.IntegerField()
    unit_refund_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    class Meta:
        db_table = 'return_item'
        unique_together = ['return_request', 'order_item']


class ReturnExchange(models.Model):
    """Exchange option instead of return"""
    return_request = models.OneToOneField(ReturnRequest, on_delete=models.CASCADE, related_name='exchange')
    
    # Exchange details
    new_product = models.ForeignKey('products.Product', on_delete=models.PROTECT)
    quantity = models.IntegerField()
    
    # Cost adjustment
    price_difference = models.DecimalField(max_digits=10, decimal_places=2)  # Positive = customer pays, negative = refund
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[('pending', 'Pending'), ('shipped', 'Shipped'), ('delivered', 'Delivered')]
    )
    
    tracking_number = models.CharField(max_length=100, blank=True)
    
    class Meta:
        db_table = 'return_exchange'


class ReturnHistory(models.Model):
    """Track return status changes"""
    return_request = models.ForeignKey(ReturnRequest, on_delete=models.CASCADE, related_name='history')
    
    # Status change
    old_status = models.CharField(max_length=20)
    new_status = models.CharField(max_length=20)
    
    # Note
    note = models.TextField(blank=True)
    changed_by = models.ForeignKey('users.CustomUser', null=True, blank=True, on_delete=models.SET_NULL)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'return_history'
        ordering = ['-created_at']


# ============================================================
# RETURN MANAGER
# ============================================================

class ReturnManager:
    """Manage product returns"""
    
    @staticmethod
    def create_return_request(order, customer, reason, items, description=''):
        """Create return request"""
        from apps.returns.models import ReturnRequest, ReturnItem
        
        # Check if eligible for return
        if not ReturnManager.is_eligible_for_return(order):
            raise ValueError('Order is not eligible for return')
        
        # Calculate refund amount
        refund_amount = ReturnManager.calculate_refund_amount(items)
        
        return_request = ReturnRequest.objects.create(
            order=order,
            customer=customer,
            reason=reason,
            description=description,
            refund_amount=refund_amount,
        )
        
        # Add items to return
        for item in items:
            ReturnItem.objects.create(
                return_request=return_request,
                order_item=item,
                quantity=item.quantity,
                unit_refund_amount=item.unit_price,
            )
        
        # Send confirmation
        ReturnManager.send_return_request_email(return_request)
        
        logger.info(f'Return request created: {return_request.return_id}')
        
        return return_request
    
    @staticmethod
    def is_eligible_for_return(order):
        """Check if order is eligible for return"""
        from django.utils import timezone
        from apps.returns.models import ReturnPolicy
        
        # Check order status
        if order.status not in ['delivered', 'completed']:
            return False
        
        # Check return window
        policy = ReturnPolicy.objects.first()
        if not policy:
            return False
        
        days_since_delivery = (timezone.now() - order.delivered_at).days
        return days_since_delivery <= policy.return_window_days
    
    @staticmethod
    def calculate_refund_amount(items, restocking_fee_pct=0):
        """Calculate refund amount"""
        subtotal = sum(item.unit_price * item.quantity for item in items)
        
        # Apply restocking fee if applicable
        restocking_fee = (subtotal * restocking_fee_pct) / 100
        
        return subtotal - restocking_fee
    
    @staticmethod
    def approve_return(return_request, moderator=None):
        """Approve return request"""
        return_request.status = 'approved'
        return_request.approved_at = timezone.now()
        return_request.save()
        
        # Generate shipping label
        label_url = ReturnManager.generate_return_label(return_request)
        return_request.return_shipping_label = label_url
        return_request.save()
        
        # Send approval email
        ReturnManager.send_return_approval_email(return_request)
        
        logger.info(f'Return {return_request.return_id} approved')
    
    @staticmethod
    def reject_return(return_request, reason):
        """Reject return request"""
        return_request.status = 'rejected'
        return_request.save()
        
        # Send rejection email
        ReturnManager.send_return_rejection_email(return_request, reason)
        
        logger.info(f'Return {return_request.return_id} rejected')
    
    @staticmethod
    def process_return_receipt(return_request, condition):
        """Process return when item received"""
        return_request.status = 'received'
        return_request.received_at = timezone.now()
        return_request.condition_on_arrival = condition
        return_request.save()
        
        # Inspect item
        if condition in ['new', 'good']:
            return_request.status = 'inspected'
            return_request.save()
            
            # Process refund
            ReturnManager.process_refund(return_request)
        else:
            # Flag for manual review
            return_request.status = 'inspected'
            return_request.inspection_notes = f'Item arrived in {condition} condition'
            return_request.save()
    
    @staticmethod
    def process_refund(return_request):
        """Process refund to customer"""
        from apps.payments.models import PaymentRefund
        
        # Create refund record
        refund = PaymentRefund.objects.create(
            original_payment=return_request.order.payment_set.first(),
            refund_amount=return_request.refund_amount,
            reason='Return',
            status='processed',
        )
        
        return_request.status = 'refunded'
        return_request.refunded_at = timezone.now()
        return_request.save()
        
        # Send refund email
        ReturnManager.send_refund_email(return_request)
        
        logger.info(f'Refund processed for {return_request.return_id}: KES {return_request.refund_amount}')
    
    @staticmethod
    def generate_return_label(return_request):
        """Generate return shipping label"""
        # Integration with shipping provider
        # This would call your shipping API (DHL, FedEx, etc)
        pass
    
    @staticmethod
    def send_return_request_email(return_request):
        """Send return request confirmation"""
        from django.core.mail import send_mail
        
        subject = f'Return Request Confirmed - {return_request.return_id}'
        message = f"""
        Your return request has been received.
        
        Return ID: {return_request.return_id}
        Reason: {return_request.get_reason_display()}
        Refund Amount: KES {return_request.refund_amount}
        
        We will review your request and respond within 24 hours.
        """
        
        send_mail(subject, message, 'support@joankkfarm.com', [return_request.customer.email])
    
    @staticmethod
    def send_return_approval_email(return_request):
        """Send return approval"""
        from django.core.mail import send_mail
        
        subject = f'Return Approved - {return_request.return_id}'
        message = f"""
        Your return has been approved!
        
        Return Shipping Label: {return_request.return_shipping_label}
        Please print this label and return your item within 7 days.
        """
        
        send_mail(subject, message, 'support@joankkfarm.com', [return_request.customer.email])


# ============================================================
# CELERY TASKS
# ============================================================

"""
from celery import shared_task

@shared_task
def process_pending_returns():
    '''Process pending returns after 3 days'''
    from apps.returns.models import ReturnRequest
    
    cutoff = timezone.now() - timedelta(days=3)
    
    pending = ReturnRequest.objects.filter(
        status='initiated',
        requested_at__lt=cutoff
    )
    
    for return_req in pending:
        # Auto-approve if reasonable
        ReturnManager.approve_return(return_req)

@shared_task
def send_return_reminders():
    '''Send reminders for returns in transit'''
    from apps.returns.models import ReturnRequest
    
    in_transit = ReturnRequest.objects.filter(
        status='in_transit',
        received_at__isnull=True
    )
    
    for return_req in in_transit:
        # Send reminder email
        pass

@shared_task
def cleanup_old_returns():
    '''Archive completed returns'''
    from apps.returns.models import ReturnRequest
    
    cutoff = timezone.now() - timedelta(days=90)
    ReturnRequest.objects.filter(status='refunded', refunded_at__lt=cutoff).update(archived=True)

# Add to CELERY_BEAT_SCHEDULE:
'process-pending-returns': {
    'task': 'apps.returns.tasks.process_pending_returns',
    'schedule': 86400.0,  # Daily
},
'send-return-reminders': {
    'task': 'apps.returns.tasks.send_return_reminders',
    'schedule': 604800.0,  # Weekly
},
'cleanup-old-returns': {
    'task': 'apps.returns.tasks.cleanup_old_returns',
    'schedule': 2592000.0,  # Monthly
},
"""