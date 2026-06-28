# Dynamic Pricing Engine - Intelligent Price Adjustments

from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import logging

logger = logging.getLogger('pricing')

# ============================================================
# PRICING MODELS
# ============================================================

class PricingRule(models.Model):
    """Pricing rules for dynamic pricing"""
    RULE_TYPE_CHOICES = [
        ('volume', 'Volume-based'),
        ('customer_tier', 'Customer tier'),
        ('time_based', 'Time-based'),
        ('inventory', 'Inventory-based'),
        ('competitor', 'Competitor-based'),
        ('seasonal', 'Seasonal'),
    ]
    
    OPERATOR_CHOICES = [
        ('equals', 'Equals'),
        ('greater', 'Greater than'),
        ('less', 'Less than'),
        ('between', 'Between'),
    ]
    
    # Basic info
    name = models.CharField(max_length=255)
    rule_type = models.CharField(max_length=20, choices=RULE_TYPE_CHOICES)
    
    # Products
    products = models.ManyToManyField('products.Product')
    
    # Conditions
    condition_field = models.CharField(max_length=50)  # e.g., quantity, customer_tier
    condition_operator = models.CharField(max_length=20, choices=OPERATOR_CHOICES)
    condition_value = models.CharField(max_length=100)  # e.g., 10, gold, 2024-01-01
    
    # Adjustment
    adjustment_type = models.CharField(
        max_length=20,
        choices=[('percentage', 'Percentage'), ('fixed', 'Fixed Amount')],
        default='percentage'
    )
    adjustment_value = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Min/Max price
    min_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    max_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Validity
    start_date = models.DateTimeField()
    end_date = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    # Priority
    priority = models.IntegerField(default=10)  # 1-100, lower = higher priority
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'pricing_rule'
        ordering = ['priority', '-created_at']


class Discount(models.Model):
    """Discount and coupon management"""
    TYPE_CHOICES = [
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed Amount'),
        ('free_shipping', 'Free Shipping'),
        ('bogo', 'Buy One Get One'),
    ]
    
    # Info
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    discount_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    
    # Value
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Conditions
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    applicable_products = models.ManyToManyField('products.Product', blank=True)
    applicable_categories = models.ManyToManyField('products.Category', blank=True)
    
    # Restrictions
    max_uses = models.IntegerField(null=True, blank=True)  # Total uses
    max_uses_per_customer = models.IntegerField(default=1)
    
    # Customer restrictions
    customer_groups = models.JSONField(default=list, blank=True)  # VIP, Gold, etc
    
    # Validity
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    
    # Tracking
    current_uses = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'discount'
        ordering = ['-created_at']


class PriceHistory(models.Model):
    """Track price changes"""
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    
    # Prices
    original_price = models.DecimalField(max_digits=10, decimal_places=2)
    adjusted_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Rules applied
    applied_rules = models.JSONField(default=list)
    
    # Context
    customer = models.ForeignKey('users.CustomUser', null=True, blank=True, on_delete=models.SET_NULL)
    quantity = models.IntegerField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'price_history'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['product', 'created_at']),
        ]


class CompetitorPrice(models.Model):
    """Track competitor prices"""
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    
    # Competitor info
    competitor_name = models.CharField(max_length=255)
    competitor_url = models.URLField()
    
    # Price
    competitor_price = models.DecimalField(max_digits=10, decimal_places=2)
    our_price = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Tracking
    price_difference = models.DecimalField(max_digits=10, decimal_places=2)
    is_cheaper = models.BooleanField()
    
    checked_at = models.DateTimeField()
    
    class Meta:
        db_table = 'competitor_price'
        unique_together = ['product', 'competitor_name']


# ============================================================
# PRICING ENGINE
# ============================================================

class PricingEngine:
    """Calculate dynamic prices"""
    
    @staticmethod
    def calculate_price(product, quantity=1, customer=None):
        """Calculate final price with all rules applied"""
        from apps.pricing.models import PricingRule, PriceHistory
        from django.utils import timezone
        
        base_price = product.price
        adjusted_price = base_price
        applied_rules = []
        
        # Get applicable rules
        rules = PricingRule.objects.filter(
            products=product,
            is_active=True,
            start_date__lte=timezone.now()
        ).exclude(end_date__lt=timezone.now())
        
        # Apply rules in priority order
        for rule in rules:
            if PricingEngine.rule_applies(rule, customer, quantity):
                adjustment = PricingEngine.apply_rule(rule, adjusted_price)
                adjusted_price = adjustment['price']
                applied_rules.append(rule.name)
        
        # Apply minimum/maximum if set
        if adjusted_price < product.min_price if product.min_price else 0:
            adjusted_price = product.min_price
        
        # Log price change
        PriceHistory.objects.create(
            product=product,
            original_price=base_price,
            adjusted_price=adjusted_price,
            discount_amount=base_price - adjusted_price,
            applied_rules=applied_rules,
            customer=customer,
            quantity=quantity,
        )
        
        return adjusted_price
    
    @staticmethod
    def rule_applies(rule, customer, quantity):
        """Check if pricing rule applies"""
        
        if rule.rule_type == 'volume':
            try:
                threshold = int(rule.condition_value)
                if rule.condition_operator == 'greater':
                    return quantity > threshold
                elif rule.condition_operator == 'equals':
                    return quantity == threshold
                elif rule.condition_operator == 'between':
                    min_val, max_val = map(int, rule.condition_value.split('-'))
                    return min_val <= quantity <= max_val
            except:
                return False
        
        elif rule.rule_type == 'customer_tier':
            if customer:
                customer_tier = getattr(customer, 'loyalty_tier', None)
                return customer_tier == rule.condition_value
        
        elif rule.rule_type == 'time_based':
            now = timezone.now()
            target_time = datetime.strptime(rule.condition_value, '%H:%M').time()
            return now.time() >= target_time
        
        return True
    
    @staticmethod
    def apply_rule(rule, current_price):
        """Apply pricing rule"""
        
        if rule.adjustment_type == 'percentage':
            adjustment = (current_price * rule.adjustment_value) / 100
        else:  # fixed
            adjustment = rule.adjustment_value
        
        new_price = current_price - adjustment  # Assume adjustment is discount
        
        # Apply min/max
        if rule.min_price and new_price < rule.min_price:
            new_price = rule.min_price
        if rule.max_price and new_price > rule.max_price:
            new_price = rule.max_price
        
        return {
            'price': new_price,
            'adjustment': adjustment,
            'rule_name': rule.name,
        }
    
    @staticmethod
    def apply_discount(order, discount_code):
        """Apply discount to order"""
        from apps.pricing.models import Discount
        
        try:
            discount = Discount.objects.get(
                code=discount_code,
                is_active=True,
                start_date__lte=timezone.now(),
                end_date__gte=timezone.now()
            )
        except Discount.DoesNotExist:
            raise ValueError('Invalid discount code')
        
        # Check usage
        if discount.max_uses and discount.current_uses >= discount.max_uses:
            raise ValueError('Discount limit reached')
        
        # Check order total
        if order.subtotal < discount.min_order_amount:
            raise ValueError(f'Minimum order amount {discount.min_order_amount} required')
        
        # Calculate discount
        if discount.discount_type == 'percentage':
            discount_amount = (order.subtotal * discount.discount_value) / 100
        elif discount.discount_type == 'fixed':
            discount_amount = discount.discount_value
        else:
            discount_amount = 0
        
        # Apply discount
        order.discount_code = discount_code
        order.discount_amount = discount_amount
        order.total_amount = order.subtotal + order.tax_amount - discount_amount
        order.save()
        
        # Update discount usage
        discount.current_uses += 1
        discount.save()
        
        return discount_amount
    
    @staticmethod
    def check_price_competitiveness(product):
        """Check if we're competitive"""
        from apps.pricing.models import CompetitorPrice
        
        competitor_prices = CompetitorPrice.objects.filter(
            product=product,
            checked_at__gte=timezone.now() - timedelta(days=7)
        )
        
        if not competitor_prices.exists():
            return None
        
        avg_competitor_price = sum(cp.competitor_price for cp in competitor_prices) / competitor_prices.count()
        
        return {
            'our_price': product.price,
            'avg_competitor_price': avg_competitor_price,
            'price_difference': product.price - avg_competitor_price,
            'is_competitive': product.price <= avg_competitor_price,
        }


# ============================================================
# CELERY TASKS
# ============================================================

"""
from celery import shared_task

@shared_task
def check_competitor_prices():
    '''Check competitor prices'''
    from apps.products.models import Product
    import requests
    from bs4 import BeautifulSoup
    
    products = Product.objects.filter(track_competitors=True)
    
    for product in products:
        # Implement competitor price scraping
        # This is simplified - implement based on actual competitors
        pass

@shared_task
def cleanup_old_price_history():
    '''Delete price history older than 1 year'''
    from apps.pricing.models import PriceHistory
    
    cutoff = timezone.now() - timedelta(days=365)
    PriceHistory.objects.filter(created_at__lt=cutoff).delete()

# Add to CELERY_BEAT_SCHEDULE:
'check-competitor-prices': {
    'task': 'apps.pricing.tasks.check_competitor_prices',
    'schedule': 86400.0,  # Daily
},
'cleanup-price-history': {
    'task': 'apps.pricing.tasks.cleanup_old_price_history',
    'schedule': 604800.0,  # Weekly
},
"""