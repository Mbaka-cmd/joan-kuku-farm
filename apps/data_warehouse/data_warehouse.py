# Advanced Analytics & Data Warehouse System

from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta
import logging

logger = logging.getLogger('analytics')

# ============================================================
# DATA WAREHOUSE MODELS
# ============================================================

class DataWarehouseFact(models.Model):
    """Fact table for analytical queries"""
    # Dimensions
    date = models.DateField()
    hour = models.IntegerField()
    
    customer = models.ForeignKey('users.CustomUser', on_delete=models.SET_NULL, null=True)
    product = models.ForeignKey('products.Product', on_delete=models.SET_NULL, null=True)
    order = models.ForeignKey('orders.Order', on_delete=models.SET_NULL, null=True)
    
    # Metrics
    revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    quantity = models.IntegerField(default=0)
    cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    profit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Dimensions (denormalized)
    category = models.CharField(max_length=255, blank=True)
    region = models.CharField(max_length=255, blank=True)
    
    # Event metrics
    page_views = models.IntegerField(default=0)
    click_count = models.IntegerField(default=0)
    conversion = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'data_warehouse_fact'
        indexes = [
            models.Index(fields=['date', 'customer']),
            models.Index(fields=['product', 'date']),
            models.Index(fields=['date']),
        ]


class AnalyticsMetric(models.Model):
    """Pre-calculated analytics metrics"""
    METRIC_TYPE_CHOICES = [
        ('revenue', 'Revenue'),
        ('orders', 'Orders'),
        ('customers', 'Customers'),
        ('aov', 'Average Order Value'),
        ('roi', 'ROI'),
        ('ltv', 'Lifetime Value'),
        ('cac', 'Customer Acquisition Cost'),
        ('retention', 'Retention Rate'),
    ]
    
    metric_type = models.CharField(max_length=50, choices=METRIC_TYPE_CHOICES)
    
    # Dimensions
    period = models.CharField(max_length=20)  # daily, weekly, monthly
    date = models.DateField()
    
    # Segments
    segment = models.CharField(max_length=100, blank=True)
    category = models.CharField(max_length=255, blank=True)
    region = models.CharField(max_length=255, blank=True)
    
    # Values
    current_value = models.DecimalField(max_digits=15, decimal_places=2)
    previous_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    change = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    change_percent = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    class Meta:
        db_table = 'analytics_metric'
        unique_together = ['metric_type', 'date', 'segment', 'category', 'region']
        indexes = [
            models.Index(fields=['date', 'metric_type']),
        ]


class CohortAnalysis(models.Model):
    """Customer cohort analysis"""
    cohort_date = models.DateField()
    cohort_age = models.IntegerField()  # Days since cohort creation
    
    # Metrics
    cohort_size = models.IntegerField()
    retained = models.IntegerField()
    revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Calculated
    retention_rate = models.DecimalField(max_digits=5, decimal_places=2)
    avg_order_value = models.DecimalField(max_digits=10, decimal_places=2)
    
    class Meta:
        db_table = 'cohort_analysis'
        unique_together = ['cohort_date', 'cohort_age']


class AttributionModel(models.Model):
    """Attribution modeling"""
    ATTRIBUTION_MODELS = [
        ('first_touch', 'First Touch'),
        ('last_touch', 'Last Touch'),
        ('linear', 'Linear'),
        ('time_decay', 'Time Decay'),
        ('position', 'Position Based'),
    ]
    
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE)
    
    # Attribution
    model_type = models.CharField(max_length=50, choices=ATTRIBUTION_MODELS)
    
    # Touchpoints
    touchpoints = models.JSONField(default=list)  # [channel, date, value]
    
    # Attribution
    attributed_revenue = models.DecimalField(max_digits=12, decimal_places=2)
    channel_credits = models.JSONField(default=dict)  # {channel: credit_amount}
    
    class Meta:
        db_table = 'attribution_model'
        unique_together = ['order', 'model_type']


class CustomerJourney(models.Model):
    """Track customer journey"""
    customer = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE)
    
    # Timeline
    first_touch = models.DateTimeField()
    last_touch = models.DateTimeField()
    
    # Journey
    touchpoints = models.JSONField(default=list)  # Timeline of interactions
    conversion_path = models.JSONField(default=list)  # Marketing channels
    
    # Analysis
    journey_length = models.IntegerField()  # Days
    touchpoint_count = models.IntegerField()
    converted = models.BooleanField(default=False)
    
    # Value
    revenue_attributed = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    class Meta:
        db_table = 'customer_journey'
        indexes = [
            models.Index(fields=['customer']),
            models.Index(fields=['converted']),
        ]


# ============================================================
# ANALYTICS ENGINE
# ============================================================

class AnalyticsEngine:
    """Advanced analytics operations"""
    
    @staticmethod
    def calculate_cohort_retention():
        """Calculate cohort retention"""
        from apps.users.models import CustomUser
        from apps.orders.models import Order
        from apps.analytics.models import CohortAnalysis
        
        # Get unique cohorts
        users = CustomUser.objects.filter(is_active=True)
        
        for user in users:
            cohort_date = user.date_joined.date()
            
            # Calculate retention for each age
            for cohort_age in [7, 14, 30, 60, 90]:
                check_date = cohort_date + timedelta(days=cohort_age)
                
                if check_date > timezone.now().date():
                    continue
                
                # Check if user had order by check_date
                had_order = Order.objects.filter(
                    customer=user,
                    created_at__date__lte=check_date
                ).exists()
                
                cohort, created = CohortAnalysis.objects.get_or_create(
                    cohort_date=cohort_date,
                    cohort_age=cohort_age
                )
                
                if had_order:
                    cohort.retained += 1
                
                cohort.save()
    
    @staticmethod
    def build_customer_journey(customer):
        """Build complete customer journey"""
        from apps.analytics.models import CustomerJourney
        from apps.orders.models import Order
        from apps.personalization.models import PersonalizationEvent
        
        # Get all interactions
        events = PersonalizationEvent.objects.filter(
            user=customer
        ).order_by('created_at')
        
        if not events.exists():
            return None
        
        first_touch = events.first().created_at
        last_touch = events.last().created_at
        
        # Build journey
        journey_data = [
            {
                'timestamp': event.created_at.isoformat(),
                'event_type': event.event_type,
                'page': event.page,
            }
            for event in events
        ]
        
        # Calculate conversion
        converted = customer.order_set.exists()
        
        # Revenue attributed
        revenue = customer.order_set.aggregate(models.Sum('total_amount'))['total_amount__sum'] or 0
        
        # Create journey record
        journey, created = CustomerJourney.objects.get_or_create(customer=customer)
        
        journey.first_touch = first_touch
        journey.last_touch = last_touch
        journey.touchpoints = journey_data
        journey.journey_length = (last_touch - first_touch).days
        journey.touchpoint_count = len(journey_data)
        journey.converted = converted
        journey.revenue_attributed = revenue
        
        journey.save()
        
        return journey
    
    @staticmethod
    def calculate_attribution(order):
        """Calculate attribution for order"""
        from apps.analytics.models import AttributionModel
        from apps.marketing.models import Touchpoint
        
        touchpoints = Touchpoint.objects.filter(
            customer=order.customer,
            timestamp__lte=order.created_at
        ).order_by('timestamp')
        
        if not touchpoints.exists():
            return None
        
        # Linear attribution
        credit_per_touch = order.total_amount / touchpoints.count()
        
        channel_credits = {}
        for touch in touchpoints:
            if touch.channel not in channel_credits:
                channel_credits[touch.channel] = 0
            channel_credits[touch.channel] += float(credit_per_touch)
        
        attribution = AttributionModel.objects.create(
            order=order,
            model_type='linear',
            attributed_revenue=order.total_amount,
            channel_credits=channel_credits,
            touchpoints=[{
                'channel': t.channel,
                'date': t.timestamp.isoformat(),
            } for t in touchpoints],
        )
        
        return attribution
    
    @staticmethod
    def get_cohort_report(start_date, end_date):
        """Get cohort retention report"""
        from apps.analytics.models import CohortAnalysis
        
        cohorts = CohortAnalysis.objects.filter(
            cohort_date__gte=start_date,
            cohort_date__lte=end_date
        ).order_by('cohort_date')
        
        report = {}
        
        for cohort in cohorts:
            if cohort.cohort_date not in report:
                report[cohort.cohort_date] = {}
            
            retention_rate = (cohort.retained / max(cohort.cohort_size, 1)) * 100
            
            report[cohort.cohort_date][cohort.cohort_age] = {
                'retained': cohort.retained,
                'cohort_size': cohort.cohort_size,
                'retention_rate': retention_rate,
            }
        
        return report
    
    @staticmethod
    def get_funnel_analysis():
        """Analyze conversion funnel"""
        from apps.personalization.models import PersonalizationEvent
        from apps.orders.models import Order
        from django.db.models import Count
        
        # Define funnel steps
        page_views = PersonalizationEvent.objects.filter(
            event_type='viewed'
        ).values('user').distinct().count()
        
        product_views = PersonalizationEvent.objects.filter(
            event_type='viewed',
            page__contains='product'
        ).values('user').distinct().count()
        
        cart_adds = PersonalizationEvent.objects.filter(
            event_type='clicked',
            page__contains='cart'
        ).values('user').distinct().count()
        
        checkouts = Order.objects.filter(
            status__in=['pending', 'processing', 'completed']
        ).values('customer').distinct().count()
        
        purchases = Order.objects.filter(
            status='completed'
        ).values('customer').distinct().count()
        
        funnel = {
            'page_views': page_views,
            'product_views': product_views,
            'cart_adds': cart_adds,
            'checkouts': checkouts,
            'purchases': purchases,
        }
        
        # Calculate conversion rates
        funnel['pv_to_product'] = (product_views / max(page_views, 1)) * 100
        funnel['product_to_cart'] = (cart_adds / max(product_views, 1)) * 100
        funnel['cart_to_checkout'] = (checkouts / max(cart_adds, 1)) * 100
        funnel['checkout_to_purchase'] = (purchases / max(checkouts, 1)) * 100
        funnel['overall_conversion'] = (purchases / max(page_views, 1)) * 100
        
        return funnel


# ============================================================
# CELERY TASKS
# ============================================================

"""
from celery import shared_task

@shared_task
def build_data_warehouse():
    '''Build data warehouse from transactional data'''
    from apps.orders.models import Order, OrderItem
    from apps.analytics.models import DataWarehouseFact
    
    orders = Order.objects.all()
    
    for order in orders:
        for item in order.orderitem_set.all():
            DataWarehouseFact.objects.get_or_create(
                date=order.created_at.date(),
                customer=order.customer,
                product=item.product,
                order=order,
                defaults={
                    'revenue': item.unit_price * item.quantity,
                    'quantity': item.quantity,
                }
            )

@shared_task
def calculate_cohort_retention():
    '''Calculate cohort retention'''
    AnalyticsEngine.calculate_cohort_retention()

@shared_task
def build_customer_journeys():
    '''Build customer journeys'''
    from apps.users.models import CustomUser
    
    customers = CustomUser.objects.filter(is_active=True)
    
    for customer in customers:
        AnalyticsEngine.build_customer_journey(customer)

# Add to CELERY_BEAT_SCHEDULE:
'build-warehouse': {
    'task': 'apps.analytics.tasks.build_data_warehouse',
    'schedule': 3600.0,  # Hourly
},
'calculate-cohorts': {
    'task': 'apps.analytics.tasks.calculate_cohort_retention',
    'schedule': 604800.0,  # Weekly
},
'build-journeys': {
    'task': 'apps.analytics.tasks.build_customer_journeys',
    'schedule': 604800.0,  # Weekly
},
"""