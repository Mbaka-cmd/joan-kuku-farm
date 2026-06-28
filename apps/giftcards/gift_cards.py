# Gift Cards & Vouchers System

from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import logging
import secrets

logger = logging.getLogger('giftcards')

# ============================================================
# GIFT CARD MODELS
# ============================================================

class GiftCard(models.Model):
    """Gift card management"""
    STATUS_CHOICES = [
        ('inactive', 'Inactive'),
        ('active', 'Active'),
        ('used', 'Fully Used'),
        ('expired', 'Expired'),
    ]
    
    # Gift card details
    code = models.CharField(max_length=50, unique=True)
    pin = models.CharField(max_length=50, blank=True)  # Optional PIN
    
    # Value
    initial_amount = models.DecimalField(max_digits=10, decimal_places=2)
    remaining_balance = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='inactive')
    
    # Dates
    activation_date = models.DateTimeField(null=True, blank=True)
    expiry_date = models.DateTimeField()
    
    # Owner
    buyer = models.ForeignKey('users.CustomUser', null=True, blank=True, on_delete=models.SET_NULL, related_name='purchased_gift_cards')
    recipient = models.ForeignKey('users.CustomUser', null=True, blank=True, on_delete=models.SET_NULL, related_name='received_gift_cards')
    
    # Message
    message = models.TextField(blank=True)
    recipient_email = models.EmailField(blank=True)
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'gift_card'
        ordering = ['-created_at']
    
    def save(self, *args, **kwargs):
        if not self.code:
            self.code = secrets.token_urlsafe(12).upper()
        if not self.pin:
            self.pin = secrets.token_urlsafe(8)
        super().save(*args, **kwargs)


class GiftCardTransaction(models.Model):
    """Gift card usage transactions"""
    TRANSACTION_TYPE = [
        ('purchase', 'Purchase'),
        ('refund', 'Refund'),
        ('adjustment', 'Manual Adjustment'),
        ('expired', 'Expired'),
    ]
    
    gift_card = models.ForeignKey(GiftCard, on_delete=models.CASCADE, related_name='transactions')
    
    # Transaction
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Reference
    order = models.ForeignKey('orders.Order', null=True, blank=True, on_delete=models.SET_NULL)
    
    # Details
    description = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'gift_card_transaction'
        ordering = ['-created_at']


class Voucher(models.Model):
    """Voucher codes for discounts"""
    TYPE_CHOICES = [
        ('percentage', 'Percentage Discount'),
        ('fixed', 'Fixed Amount'),
        ('free_shipping', 'Free Shipping'),
        ('tiered', 'Tiered Discount'),
    ]
    
    # Voucher details
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    voucher_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    
    # Value
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    max_discount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Conditions
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    applicable_products = models.ManyToManyField('products.Product', blank=True)
    applicable_categories = models.ManyToManyField('products.Category', blank=True)
    
    # Usage limits
    max_uses = models.IntegerField(null=True, blank=True)
    max_uses_per_customer = models.IntegerField(default=1)
    current_uses = models.IntegerField(default=0)
    
    # Validity
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'voucher'
        ordering = ['-created_at']
    
    def save(self, *args, **kwargs):
        if not self.code:
            self.code = secrets.token_urlsafe(10).upper()
        super().save(*args, **kwargs)


class PromotionalCode(models.Model):
    """Promotional codes for campaigns"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('expired', 'Expired'),
    ]
    
    # Code details
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Campaign
    campaign = models.CharField(max_length=255, blank=True)  # Campaign name
    
    # Discount
    discount_type = models.CharField(
        max_length=20,
        choices=[('percentage', 'Percentage'), ('fixed', 'Fixed'), ('free_shipping', 'Free Shipping')]
    )
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Limits
    max_uses = models.IntegerField(null=True, blank=True)
    current_uses = models.IntegerField(default=0)
    max_per_customer = models.IntegerField(default=1)
    
    # Validity
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Target
    customer_groups = models.JSONField(default=list, blank=True)  # VIP, new, etc
    
    # Analytics
    views = models.IntegerField(default=0)
    uses = models.IntegerField(default=0)
    revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'promotional_code'
        ordering = ['-created_at']


# ============================================================
# GIFT CARD MANAGER
# ============================================================

class GiftCardManager:
    """Manage gift cards"""
    
    @staticmethod
    def create_gift_card(initial_amount, buyer=None, recipient_email=None, message='', expiry_days=365):
        """Create new gift card"""
        
        gift_card = GiftCard.objects.create(
            initial_amount=initial_amount,
            remaining_balance=initial_amount,
            buyer=buyer,
            recipient_email=recipient_email,
            message=message,
            expiry_date=timezone.now() + timedelta(days=expiry_days),
        )
        
        logger.info(f'Gift card created: {gift_card.code}')
        
        # Send email if recipient email provided
        if recipient_email:
            GiftCardManager.send_gift_card_email(gift_card)
        
        return gift_card
    
    @staticmethod
    def activate_gift_card(code, pin=None):
        """Activate gift card"""
        try:
            gift_card = GiftCard.objects.get(code=code)
        except GiftCard.DoesNotExist:
            raise ValueError('Invalid gift card code')
        
        if pin and gift_card.pin != pin:
            raise ValueError('Invalid PIN')
        
        if gift_card.status != 'inactive':
            raise ValueError('Gift card already activated')
        
        if gift_card.expiry_date < timezone.now():
            raise ValueError('Gift card expired')
        
        gift_card.status = 'active'
        gift_card.activation_date = timezone.now()
        gift_card.save()
        
        logger.info(f'Gift card activated: {gift_card.code}')
        
        return gift_card
    
    @staticmethod
    def redeem_gift_card(gift_card, order, amount):
        """Redeem gift card on order"""
        
        if gift_card.status not in ['active', 'used']:
            raise ValueError('Gift card cannot be redeemed')
        
        if gift_card.remaining_balance < amount:
            raise ValueError('Insufficient balance')
        
        # Create transaction
        transaction = GiftCardTransaction.objects.create(
            gift_card=gift_card,
            transaction_type='purchase',
            amount=amount,
            order=order,
        )
        
        # Update balance
        gift_card.remaining_balance -= amount
        gift_card.last_used = timezone.now()
        
        # Update status
        if gift_card.remaining_balance == 0:
            gift_card.status = 'used'
        else:
            gift_card.status = 'active'
        
        gift_card.save()
        
        logger.info(f'Gift card redeemed: {gift_card.code}, Amount: {amount}')
        
        return transaction
    
    @staticmethod
    def check_balance(code):
        """Check gift card balance"""
        try:
            gift_card = GiftCard.objects.get(code=code)
            return gift_card.remaining_balance
        except GiftCard.DoesNotExist:
            return None
    
    @staticmethod
    def send_gift_card_email(gift_card):
        """Send gift card to recipient"""
        from django.core.mail import send_mail
        
        subject = 'You received a gift card!'
        message = f"""
        You've received a gift card!
        
        {gift_card.message}
        
        Gift Card Code: {gift_card.code}
        Amount: KES {gift_card.initial_amount}
        
        Visit our store to use this gift card.
        """
        
        send_mail(
            subject,
            message,
            'noreply@joankkfarm.com',
            [gift_card.recipient_email],
        )


# ============================================================
# CELERY TASKS
# ============================================================

"""
from celery import shared_task

@shared_task
def expire_gift_cards():
    '''Expire old gift cards'''
    from apps.giftcards.models import GiftCard
    
    expired = GiftCard.objects.filter(
        expiry_date__lt=timezone.now(),
        status__in=['active', 'inactive']
    )
    
    for card in expired:
        card.status = 'expired'
        card.save()

@shared_task
def expire_vouchers():
    '''Expire old vouchers'''
    from apps.giftcards.models import Voucher
    
    expired = Voucher.objects.filter(
        end_date__lt=timezone.now(),
        is_active=True
    )
    
    expired.update(is_active=False)

@shared_task
def cleanup_gift_card_transactions():
    '''Archive old gift card transactions'''
    from apps.giftcards.models import GiftCardTransaction
    
    cutoff = timezone.now() - timedelta(days=365)
    GiftCardTransaction.objects.filter(created_at__lt=cutoff).delete()

# Add to CELERY_BEAT_SCHEDULE:
'expire-gift-cards': {
    'task': 'apps.giftcards.tasks.expire_gift_cards',
    'schedule': 86400.0,  # Daily
},
'expire-vouchers': {
    'task': 'apps.giftcards.tasks.expire_vouchers',
    'schedule': 86400.0,  # Daily
},
'cleanup-gift-card-transactions': {
    'task': 'apps.giftcards.tasks.cleanup_gift_card_transactions',
    'schedule': 604800.0,  # Weekly
},
"""