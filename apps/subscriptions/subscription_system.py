# Subscription Management System - Recurring Orders & Billing

from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import logging

logger = logging.getLogger('subscriptions')

# ============================================================
# SUBSCRIPTION MODELS
# ============================================================

class SubscriptionPlan(models.Model):
    """Subscription plan templates"""
    FREQUENCY_CHOICES = [
        ('weekly', 'Weekly'),
        ('biweekly', 'Every 2 weeks'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('annual', 'Annual'),
    ]
    
    # Plan info
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Products
    products = models.ManyToManyField('products.Product')
    
    # Pricing
    price = models.DecimalField(max_digits=10, decimal_places=2)
    billing_frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    
    # Trial
    trial_days = models.IntegerField(default=0)
    
    # Terms
    min_billing_cycles = models.IntegerField(default=3)
    max_billing_cycles = models.IntegerField(null=True, blank=True)
    
    # Discounts
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Status
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'subscription_plan'
        ordering = ['price']


class Subscription(models.Model):
    """Active subscriptions"""
    STATUS_CHOICES = [
        ('trial', 'Trial'),
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
    ]
    
    # Customer & plan
    customer = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE, related_name='subscriptions')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT)
    
    # Billing
    billing_cycle_number = models.IntegerField(default=1)
    next_billing_date = models.DateField()
    
    # Payment
    payment_method = models.CharField(
        max_length=20,
        choices=[('mpesa', 'M-Pesa'), ('card', 'Credit Card'), ('bank', 'Bank Transfer')],
        default='mpesa'
    )
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='trial')
    auto_renew = models.BooleanField(default=True)
    
    # Trial
    trial_starts = models.DateTimeField(null=True, blank=True)
    trial_ends = models.DateTimeField(null=True, blank=True)
    
    # Dates
    started_at = models.DateTimeField(auto_now_add=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'subscription'
        ordering = ['-started_at']


class SubscriptionBilling(models.Model):
    """Billing history for subscriptions"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='billings')
    
    # Billing
    billing_cycle = models.IntegerField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Dates
    due_date = models.DateField()
    paid_date = models.DateTimeField(null=True, blank=True)
    
    # Reference
    order = models.ForeignKey('orders.Order', null=True, blank=True, on_delete=models.SET_NULL)
    transaction_id = models.CharField(max_length=100, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'subscription_billing'
        ordering = ['-due_date']
        unique_together = ['subscription', 'billing_cycle']


class SubscriptionModification(models.Model):
    """Track subscription modifications"""
    TYPE_CHOICES = [
        ('upgrade', 'Upgrade'),
        ('downgrade', 'Downgrade'),
        ('change_frequency', 'Change Frequency'),
        ('pause', 'Pause'),
        ('resume', 'Resume'),
        ('cancel', 'Cancel'),
    ]
    
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE)
    
    modification_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    
    # Changes
    old_plan = models.ForeignKey(
        SubscriptionPlan,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+'
    )
    new_plan = models.ForeignKey(
        SubscriptionPlan,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+'
    )
    
    # Proration
    credit_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    charge_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'subscription_modification'
        ordering = ['-created_at']


# ============================================================
# SUBSCRIPTION MANAGER
# ============================================================

class SubscriptionManager:
    """Manage subscriptions"""
    
    @staticmethod
    def create_subscription(customer, plan, payment_method='mpesa'):
        """Create new subscription"""
        
        subscription = Subscription.objects.create(
            customer=customer,
            plan=plan,
            payment_method=payment_method,
            status='trial' if plan.trial_days > 0 else 'active',
        )
        
        # Set dates
        if plan.trial_days > 0:
            subscription.trial_starts = timezone.now()
            subscription.trial_ends = timezone.now() + timedelta(days=plan.trial_days)
            subscription.next_billing_date = subscription.trial_ends.date()
        else:
            frequency_days = SubscriptionManager.get_frequency_days(plan.billing_frequency)
            subscription.next_billing_date = (timezone.now() + timedelta(days=frequency_days)).date()
        
        subscription.save()
        
        logger.info(f'Subscription created for {customer.email}')
        
        return subscription
    
    @staticmethod
    def get_frequency_days(frequency):
        """Get days for billing frequency"""
        frequencies = {
            'weekly': 7,
            'biweekly': 14,
            'monthly': 30,
            'quarterly': 90,
            'annual': 365,
        }
        return frequencies.get(frequency, 30)
    
    @staticmethod
    def process_subscription_billing(subscription):
        """Create billing and process payment"""
        from apps.orders.models import Order, OrderItem
        
        # Create billing record
        billing = SubscriptionBilling.objects.create(
            subscription=subscription,
            billing_cycle=subscription.billing_cycle_number,
            amount=subscription.plan.price,
            due_date=subscription.next_billing_date,
        )
        
        # Create order for subscription
        order = Order.objects.create(
            customer=subscription.customer,
            status='confirmed',
            payment_method=subscription.payment_method,
            total_amount=subscription.plan.price,
        )
        
        # Add items from subscription plan
        for product in subscription.plan.products.all():
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=1,
                unit_price=product.price,
            )
        
        # Update billing
        billing.order = order
        billing.status = 'paid'
        billing.paid_date = timezone.now()
        billing.save()
        
        # Update subscription
        subscription.billing_cycle_number += 1
        frequency_days = SubscriptionManager.get_frequency_days(subscription.plan.billing_frequency)
        subscription.next_billing_date = (timezone.now() + timedelta(days=frequency_days)).date()
        subscription.save()
        
        logger.info(f'Subscription billing processed for {subscription.customer.email}')
        
        return order
    
    @staticmethod
    def pause_subscription(subscription, reason=''):
        """Pause subscription"""
        subscription.status = 'paused'
        subscription.auto_renew = False
        subscription.save()
        
        logger.info(f'Subscription paused: {subscription.customer.email}')
    
    @staticmethod
    def resume_subscription(subscription):
        """Resume paused subscription"""
        subscription.status = 'active'
        subscription.auto_renew = True
        subscription.save()
        
        logger.info(f'Subscription resumed: {subscription.customer.email}')
    
    @staticmethod
    def cancel_subscription(subscription, reason=''):
        """Cancel subscription"""
        subscription.status = 'cancelled'
        subscription.cancelled_at = timezone.now()
        subscription.auto_renew = False
        subscription.save()
        
        SubscriptionModification.objects.create(
            subscription=subscription,
            modification_type='cancel',
            reason=reason,
        )
        
        logger.info(f'Subscription cancelled: {subscription.customer.email}')
    
    @staticmethod
    def upgrade_subscription(subscription, new_plan):
        """Upgrade to higher tier"""
        old_plan = subscription.plan
        
        # Calculate proration
        days_remaining = (subscription.next_billing_date - timezone.now().date()).days
        daily_old_rate = old_plan.price / 30
        daily_new_rate = new_plan.price / 30
        
        credit_amount = daily_old_rate * days_remaining
        charge_amount = daily_new_rate * days_remaining
        net_charge = charge_amount - credit_amount
        
        # Create modification record
        SubscriptionModification.objects.create(
            subscription=subscription,
            modification_type='upgrade',
            old_plan=old_plan,
            new_plan=new_plan,
            credit_amount=credit_amount,
            charge_amount=charge_amount,
        )
        
        # Update subscription
        subscription.plan = new_plan
        subscription.save()
        
        logger.info(f'Subscription upgraded: {subscription.customer.email}')


# ============================================================
# CELERY TASKS
# ============================================================

"""
from celery import shared_task

@shared_task
def process_subscription_renewals():
    '''Process subscription renewals'''
    from apps.subscriptions.models import Subscription
    
    today = timezone.now().date()
    
    subscriptions = Subscription.objects.filter(
        status='active',
        auto_renew=True,
        next_billing_date=today
    )
    
    for subscription in subscriptions:
        try:
            SubscriptionManager.process_subscription_billing(subscription)
        except Exception as e:
            logger.error(f'Failed to process subscription {subscription.id}: {e}')

@shared_task
def end_trial_subscriptions():
    '''End trial periods and convert to paid'''
    from apps.subscriptions.models import Subscription
    
    now = timezone.now()
    
    trials = Subscription.objects.filter(
        status='trial',
        trial_ends__lte=now
    )
    
    for subscription in trials:
        subscription.status = 'active'
        subscription.save()
        
        # Process first billing
        SubscriptionManager.process_subscription_billing(subscription)

@shared_task
def send_renewal_reminders():
    '''Send renewal reminders 7 days before billing'''
    from apps.subscriptions.models import Subscription
    
    reminder_date = (timezone.now() + timedelta(days=7)).date()
    
    subscriptions = Subscription.objects.filter(
        status='active',
        next_billing_date=reminder_date
    )
    
    for subscription in subscriptions:
        # Send reminder email
        pass

# Add to CELERY_BEAT_SCHEDULE:
'process-subscription-renewals': {
    'task': 'apps.subscriptions.tasks.process_subscription_renewals',
    'schedule': 86400.0,  # Daily
},
'end-trial-subscriptions': {
    'task': 'apps.subscriptions.tasks.end_trial_subscriptions',
    'schedule': 3600.0,  # Hourly
},
'send-renewal-reminders': {
    'task': 'apps.subscriptions.tasks.send_renewal_reminders',
    'schedule': 86400.0,  # Daily
},
"""