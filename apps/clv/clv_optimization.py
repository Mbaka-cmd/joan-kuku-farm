# Customer Lifetime Value (CLV) Optimization System

from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import logging

logger = logging.getLogger('clv')

# ============================================================
# CLV MODELS
# ============================================================

class CustomerValue(models.Model):
    """Customer value metrics"""
    customer = models.OneToOneField('users.CustomUser', on_delete=models.CASCADE)
    
    # Historical values
    total_spent = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_orders = models.IntegerField(default=0)
    
    # Current metrics
    avg_order_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    purchase_frequency = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # orders per month
    
    # Predictive CLV
    predicted_clv = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # 12-month
    predicted_clv_3yr = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # 3-year
    
    # Costs
    customer_acquisition_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    lifetime_marketing_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Profit
    lifetime_gross_profit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    lifetime_net_profit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Segmentation
    value_segment = models.CharField(
        max_length=20,
        choices=[
            ('vip', 'VIP'),
            ('high', 'High Value'),
            ('medium', 'Medium Value'),
            ('low', 'Low Value'),
            ('at_risk', 'At Risk'),
        ]
    )
    
    # Growth potential
    growth_potential = models.DecimalField(max_digits=5, decimal_places=2)  # 0-100
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'customer_value'
        ordering = ['-predicted_clv']


class CLVAction(models.Model):
    """Actions to increase CLV"""
    ACTION_TYPE = [
        ('upsell', 'Upsell'),
        ('cross_sell', 'Cross-sell'),
        ('retention', 'Retention'),
        ('upgrade', 'Upgrade'),
        ('referral', 'Referral'),
    ]
    
    customer = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE)
    
    action_type = models.CharField(max_length=20, choices=ACTION_TYPE)
    description = models.TextField()
    
    # Target
    target_value = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[('active', 'Active'), ('completed', 'Completed'), ('failed', 'Failed')]
    )
    
    # Results
    actual_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'clv_action'
        ordering = ['-created_at']


class CLVForecast(models.Model):
    """Forecast CLV for groups of customers"""
    period = models.CharField(
        max_length=20,
        choices=[('1_month', '1 Month'), ('3_month', '3 Months'), ('1_year', '1 Year'), ('3_year', '3 Years')]
    )
    
    # Segment
    segment = models.CharField(max_length=100)
    
    # Forecast
    avg_predicted_clv = models.DecimalField(max_digits=12, decimal_places=2)
    customer_count = models.IntegerField()
    total_potential_value = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Confidence
    confidence_interval = models.JSONField(default=dict)  # {low, high}
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'clv_forecast'


# ============================================================
# CLV OPTIMIZATION ENGINE
# ============================================================

class CLVOptimizer:
    """Optimize customer lifetime value"""
    
    @staticmethod
    def calculate_clv(customer):
        """Calculate customer lifetime value"""
        from apps.orders.models import Order
        from apps.customers_value.models import CustomerValue
        
        # Get order history
        orders = Order.objects.filter(customer=customer)
        
        if not orders.exists():
            return None
        
        # Calculate metrics
        total_spent = orders.aggregate(models.Sum('total_amount'))['total_amount__sum'] or 0
        total_orders = orders.count()
        avg_order_value = total_spent / total_orders if total_orders > 0 else 0
        
        # Calculate purchase frequency
        first_order = orders.order_by('created_at').first()
        last_order = orders.order_by('-created_at').first()
        
        if first_order and last_order:
            days_active = (last_order.created_at - first_order.created_at).days
            months_active = max(1, days_active / 30)
            purchase_frequency = total_orders / months_active
        else:
            purchase_frequency = 0
        
        # Predict 12-month CLV
        if purchase_frequency > 0 and avg_order_value > 0:
            predicted_clv = avg_order_value * purchase_frequency * 12
        else:
            predicted_clv = 0
        
        # Predict 3-year CLV
        predicted_clv_3yr = predicted_clv * 3
        
        # Calculate profit margins
        # Assume 30% gross margin
        gross_margin = Decimal('0.30')
        lifetime_gross_profit = Decimal(str(total_spent)) * gross_margin
        
        # Estimate marketing cost (20% of revenue for customer acquisition)
        customer_acquisition_cost = Decimal(str(total_spent)) * Decimal('0.20')
        lifetime_marketing_cost = customer_acquisition_cost  # Simplified
        
        lifetime_net_profit = lifetime_gross_profit - lifetime_marketing_cost
        
        # Segment
        if total_spent >= 10000:
            segment = 'vip'
        elif total_spent >= 5000:
            segment = 'high'
        elif total_spent >= 1000:
            segment = 'medium'
        elif total_spent >= 100:
            segment = 'low'
        else:
            segment = 'at_risk'
        
        # Calculate growth potential
        growth_potential = CLVOptimizer.calculate_growth_potential(customer)
        
        # Update or create CLV record
        clv, created = CustomerValue.objects.get_or_create(customer=customer)
        
        clv.total_spent = total_spent
        clv.total_orders = total_orders
        clv.avg_order_value = avg_order_value
        clv.purchase_frequency = purchase_frequency
        clv.predicted_clv = predicted_clv
        clv.predicted_clv_3yr = predicted_clv_3yr
        clv.lifetime_gross_profit = lifetime_gross_profit
        clv.lifetime_net_profit = lifetime_net_profit
        clv.value_segment = segment
        clv.growth_potential = growth_potential
        
        clv.save()
        
        logger.info(f'CLV calculated for {customer.email}: ${predicted_clv:.2f}')
        
        return clv
    
    @staticmethod
    def calculate_growth_potential(customer):
        """Calculate customer's growth potential"""
        from apps.recommendations.models import Recommendation
        from apps.products.models import Product
        
        potential = 0
        
        # Upsell opportunity
        avg_order = customer.order_set.aggregate(models.Avg('total_amount'))['total_amount__avg'] or 0
        max_order = customer.order_set.aggregate(models.Max('total_amount'))['total_amount__max'] or 0
        
        if max_order > avg_order * 1.5:
            potential += 20  # Customer capable of higher orders
        
        # Cross-sell opportunity
        purchased_categories = set(
            customer.order_set.values_list('orderitem__product__category_id', flat=True)
        )
        
        total_categories = Product.objects.values('category_id').distinct().count()
        category_diversity = len(purchased_categories) / max(total_categories, 1)
        
        if category_diversity < 0.5:
            potential += 30  # Opportunity to cross-sell to new categories
        
        # Engagement opportunity
        email_engagement = getattr(customer, 'email_engagement', 0)
        if email_engagement < 50:
            potential += 25  # Low engagement = high growth potential through engagement
        
        # Review opportunity
        review_count = customer.productreview_set.count()
        order_count = customer.order_set.count()
        
        if review_count < order_count * 0.3:
            potential += 15  # Opportunity to increase reviews/engagement
        
        return min(100, potential)
    
    @staticmethod
    def recommend_clv_actions(customer):
        """Recommend actions to increase CLV"""
        from apps.clv.models import CLVAction, CustomerValue
        from apps.products.models import Product
        
        try:
            clv = CustomerValue.objects.get(customer=customer)
        except CustomerValue.DoesNotExist:
            return []
        
        actions = []
        
        # Upsell recommendation
        if clv.avg_order_value > 0:
            actions.append({
                'type': 'upsell',
                'description': 'Upsell higher-value items',
                'target_value': clv.avg_order_value * 1.25,
            })
        
        # Cross-sell recommendation
        if clv.value_segment in ['high', 'vip']:
            actions.append({
                'type': 'cross_sell',
                'description': 'Cross-sell complementary products',
                'target_value': clv.avg_order_value * 0.5,
            })
        
        # Referral recommendation
        if clv.predicted_clv > 5000:
            actions.append({
                'type': 'referral',
                'description': 'Encourage referrals',
                'target_value': clv.avg_order_value,
            })
        
        # Retention recommendation
        from apps.churn.models import CustomerRiskScore
        try:
            risk = CustomerRiskScore.objects.get(customer=customer)
            if risk.risk_level in ['high', 'critical']:
                actions.append({
                    'type': 'retention',
                    'description': 'Retention offer for at-risk customer',
                    'target_value': clv.avg_order_value * 0.2,
                })
        except:
            pass
        
        return actions
    
    @staticmethod
    def optimize_customer_segment(segment):
        """Optimize actions for customer segment"""
        from apps.customers_value.models import CustomerValue
        
        customers = CustomerValue.objects.filter(value_segment=segment)
        
        actions = []
        
        for customer in customers:
            segment_actions = CLVOptimizer.recommend_clv_actions(customer.customer)
            
            for action in segment_actions:
                clv_action = CLVAction.objects.create(
                    customer=customer.customer,
                    action_type=action['type'],
                    description=action['description'],
                    target_value=Decimal(str(action['target_value'])),
                )
                
                actions.append(clv_action)
        
        return actions
    
    @staticmethod
    def forecast_segment_clv(segment, period='1_year'):
        """Forecast CLV for segment"""
        from apps.customers_value.models import CustomerValue, CLVForecast
        
        customers = CustomerValue.objects.filter(value_segment=segment)
        
        if not customers.exists():
            return None
        
        avg_clv = customers.aggregate(models.Avg('predicted_clv'))['predicted_clv__avg'] or 0
        total_value = customers.aggregate(models.Sum('predicted_clv'))['predicted_clv__sum'] or 0
        
        forecast = CLVForecast.objects.create(
            period=period,
            segment=segment,
            avg_predicted_clv=avg_clv,
            customer_count=customers.count(),
            total_potential_value=total_value,
        )
        
        return forecast


# ============================================================
# CELERY TASKS
# ============================================================

"""
from celery import shared_task

@shared_task
def calculate_all_clv():
    '''Calculate CLV for all customers'''
    from apps.users.models import CustomUser
    
    customers = CustomUser.objects.filter(is_active=True)
    
    for customer in customers:
        CLVOptimizer.calculate_clv(customer)

@shared_task
def optimize_clv_actions():
    '''Generate CLV optimization actions'''
    for segment in ['vip', 'high', 'medium', 'low', 'at_risk']:
        CLVOptimizer.optimize_customer_segment(segment)

@shared_task
def forecast_segment_clv():
    '''Forecast CLV by segment'''
    for segment in ['vip', 'high', 'medium']:
        CLVOptimizer.forecast_segment_clv(segment, period='1_year')

# Add to CELERY_BEAT_SCHEDULE:
'calculate-clv': {
    'task': 'apps.clv.tasks.calculate_all_clv',
    'schedule': 604800.0,  # Weekly
},
'optimize-clv-actions': {
    'task': 'apps.clv.tasks.optimize_clv_actions',
    'schedule': 604800.0,  # Weekly
},
'forecast-clv': {
    'task': 'apps.clv.tasks.forecast_segment_clv',
    'schedule': 2592000.0,  # Monthly
},
"""