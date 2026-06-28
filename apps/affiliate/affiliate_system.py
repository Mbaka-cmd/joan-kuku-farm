# Affiliate Marketing System

from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import logging

logger = logging.getLogger('affiliate')

# ============================================================
# AFFILIATE MODELS
# ============================================================

class AffiliateProgram(models.Model):
    """Affiliate program configuration"""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('paused', 'Paused'),
    ]
    
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Commission structure
    default_commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10)  # %
    cookie_duration = models.IntegerField(default=30)  # Days
    
    # Requirements
    min_withdrawal = models.DecimalField(max_digits=10, decimal_places=2, default=100)
    payment_frequency = models.CharField(
        max_length=20,
        choices=[('weekly', 'Weekly'), ('monthly', 'Monthly'), ('quarterly', 'Quarterly')],
        default='monthly'
    )
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'affiliate_program'


class Affiliate(models.Model):
    """Affiliate program members"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('suspended', 'Suspended'),
        ('inactive', 'Inactive'),
    ]
    
    program = models.ForeignKey(AffiliateProgram, on_delete=models.CASCADE)
    user = models.OneToOneField('users.CustomUser', on_delete=models.CASCADE)
    
    # Affiliate info
    affiliate_id = models.CharField(max_length=50, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Commission
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10)  # %
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_earned = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Stats
    total_clicks = models.IntegerField(default=0)
    total_conversions = models.IntegerField(default=0)
    total_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Links & tracking
    unique_code = models.CharField(max_length=50, unique=True)
    referral_url = models.URLField(blank=True)
    
    # Banking
    payment_email = models.EmailField()
    payment_method = models.CharField(
        max_length=20,
        choices=[('bank', 'Bank Transfer'), ('mpesa', 'M-Pesa'), ('paypal', 'PayPal')],
        default='mpesa'
    )
    
    # Dates
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'affiliate'
        unique_together = ['program', 'user']
    
    def save(self, *args, **kwargs):
        if not self.affiliate_id:
            import uuid
            self.affiliate_id = f"AFF-{uuid.uuid4().hex[:8].upper()}"
        if not self.unique_code:
            import secrets
            self.unique_code = secrets.token_urlsafe(12)
        super().save(*args, **kwargs)


class AffiliateClick(models.Model):
    """Track affiliate clicks"""
    affiliate = models.ForeignKey(Affiliate, on_delete=models.CASCADE, related_name='clicks')
    
    # Click info
    source_url = models.URLField()
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    
    # Session
    session_id = models.CharField(max_length=100)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'affiliate_click'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['affiliate', 'created_at']),
            models.Index(fields=['session_id']),
        ]


class AffiliateConversion(models.Model):
    """Track affiliate conversions (sales)"""
    affiliate = models.ForeignKey(Affiliate, on_delete=models.CASCADE, related_name='conversions')
    order = models.ForeignKey('orders.Order', on_delete=models.SET_NULL, null=True)
    
    # Click reference
    click = models.ForeignKey(AffiliateClick, on_delete=models.SET_NULL, null=True, blank=True)
    session_id = models.CharField(max_length=100)
    
    # Commission
    sale_amount = models.DecimalField(max_digits=12, decimal_places=2)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2)
    commission_amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')],
        default='pending'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'affiliate_conversion'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['affiliate', 'status']),
            models.Index(fields=['session_id']),
        ]


class AffiliateWithdrawal(models.Model):
    """Track affiliate withdrawals"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    affiliate = models.ForeignKey(Affiliate, on_delete=models.CASCADE)
    
    # Withdrawal
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Payment info
    payment_method = models.CharField(max_length=20)
    reference_id = models.CharField(max_length=100, blank=True)
    
    # Dates
    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'affiliate_withdrawal'
        ordering = ['-requested_at']


# ============================================================
# AFFILIATE MANAGER
# ============================================================

class AffiliateManager:
    """Manage affiliate program"""
    
    @staticmethod
    def track_click(affiliate_code, source_url, session_id, ip_address, user_agent):
        """Track affiliate click"""
        from apps.affiliate.models import Affiliate, AffiliateClick
        
        try:
            affiliate = Affiliate.objects.get(unique_code=affiliate_code, status='approved')
        except Affiliate.DoesNotExist:
            return None
        
        click = AffiliateClick.objects.create(
            affiliate=affiliate,
            source_url=source_url,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
        )
        
        affiliate.total_clicks += 1
        affiliate.save()
        
        return click
    
    @staticmethod
    def track_conversion(session_id, order):
        """Track affiliate conversion"""
        from apps.affiliate.models import AffiliateClick, AffiliateConversion
        
        # Find click for session
        click = AffiliateClick.objects.filter(session_id=session_id).first()
        
        if not click:
            return None
        
        affiliate = click.affiliate
        
        # Calculate commission
        commission_rate = affiliate.commission_rate
        commission_amount = (order.total_amount * commission_rate) / 100
        
        conversion = AffiliateConversion.objects.create(
            affiliate=affiliate,
            order=order,
            click=click,
            session_id=session_id,
            sale_amount=order.total_amount,
            commission_rate=commission_rate,
            commission_amount=commission_amount,
        )
        
        # Update affiliate stats
        affiliate.total_conversions += 1
        affiliate.total_sales += order.total_amount
        affiliate.balance += conversion.commission_amount
        affiliate.total_earned += conversion.commission_amount
        affiliate.save()
        
        logger.info(f'Conversion tracked for affiliate {affiliate.affiliate_id}')
        
        return conversion
    
    @staticmethod
    def approve_affiliate(affiliate):
        """Approve new affiliate"""
        affiliate.status = 'approved'
        affiliate.approved_at = timezone.now()
        affiliate.save()
        
        logger.info(f'Affiliate {affiliate.affiliate_id} approved')
    
    @staticmethod
    def process_withdrawal(affiliate, amount):
        """Process affiliate withdrawal"""
        from apps.affiliate.models import AffiliateWithdrawal
        
        if affiliate.balance < amount:
            raise ValueError('Insufficient balance')
        
        withdrawal = AffiliateWithdrawal.objects.create(
            affiliate=affiliate,
            amount=amount,
            payment_method=affiliate.payment_method,
        )
        
        # Deduct from balance
        affiliate.balance -= amount
        affiliate.save()
        
        logger.info(f'Withdrawal created for {affiliate.affiliate_id}: {amount}')
        
        return withdrawal
    
    @staticmethod
    def get_affiliate_stats(affiliate, start_date=None, end_date=None):
        """Get affiliate statistics"""
        if not start_date:
            start_date = timezone.now() - timedelta(days=30)
        if not end_date:
            end_date = timezone.now()
        
        clicks = affiliate.clicks.filter(created_at__range=[start_date, end_date]).count()
        conversions = affiliate.conversions.filter(
            created_at__range=[start_date, end_date],
            status='approved'
        )
        
        total_commission = sum(c.commission_amount for c in conversions)
        
        return {
            'clicks': clicks,
            'conversions': conversions.count(),
            'conversion_rate': (conversions.count() / clicks * 100) if clicks > 0 else 0,
            'total_sales': sum(c.sale_amount for c in conversions),
            'total_commission': total_commission,
        }


# ============================================================
# CELERY TASKS
# ============================================================

"""
from celery import shared_task

@shared_task
def auto_approve_conversions():
    '''Auto-approve pending conversions after 10 days'''
    from apps.affiliate.models import AffiliateConversion
    
    cutoff = timezone.now() - timedelta(days=10)
    pending = AffiliateConversion.objects.filter(
        status='pending',
        created_at__lt=cutoff
    )
    
    for conversion in pending:
        conversion.status = 'approved'
        conversion.save()

@shared_task
def process_monthly_payouts():
    '''Process monthly affiliate payouts'''
    from apps.affiliate.models import Affiliate, AffiliateWithdrawal
    
    affiliates = Affiliate.objects.filter(
        status='approved',
        balance__gte=F('program__min_withdrawal')
    )
    
    for affiliate in affiliates:
        withdrawal = AffiliateManager.process_withdrawal(
            affiliate,
            affiliate.balance
        )
        
        # Actually send payment (implement based on payment method)
        send_affiliate_payment.delay(withdrawal.id)

@shared_task
def cleanup_old_clicks():
    '''Delete clicks older than 90 days'''
    from apps.affiliate.models import AffiliateClick
    
    cutoff = timezone.now() - timedelta(days=90)
    AffiliateClick.objects.filter(created_at__lt=cutoff).delete()

# Add to CELERY_BEAT_SCHEDULE:
'auto-approve-conversions': {
    'task': 'apps.affiliate.tasks.auto_approve_conversions',
    'schedule': 86400.0,  # Daily
},
'process-monthly-payouts': {
    'task': 'apps.affiliate.tasks.process_monthly_payouts',
    'schedule': 2592000.0,  # Monthly
},
'cleanup-old-clicks': {
    'task': 'apps.affiliate.tasks.cleanup_old_clicks',
    'schedule': 604800.0,  # Weekly
},
"""