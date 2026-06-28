# Business Intelligence Dashboard - Real-time Analytics & Metrics

from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta
import logging

logger = logging.getLogger('bi')

# ============================================================
# BI MODELS
# ============================================================

class DashboardWidget(models.Model):
    """Customizable dashboard widgets"""
    WIDGET_TYPE_CHOICES = [
        ('kpi', 'Key Performance Indicator'),
        ('chart', 'Chart'),
        ('table', 'Data Table'),
        ('gauge', 'Gauge Chart'),
        ('heat_map', 'Heat Map'),
        ('forecast', 'Forecast'),
    ]
    
    # Widget info
    name = models.CharField(max_length=255)
    widget_type = models.CharField(max_length=20, choices=WIDGET_TYPE_CHOICES)
    
    # Configuration
    metric = models.CharField(max_length=100)  # revenue, orders, customers, etc
    time_period = models.CharField(
        max_length=20,
        choices=[('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly')]
    )
    
    # Display
    position = models.IntegerField(default=0)
    size = models.CharField(max_length=20, choices=[('small', 'Small'), ('medium', 'Medium'), ('large', 'Large')])
    
    # Filters
    filters = models.JSONField(default=dict)
    
    # User
    created_by = models.ForeignKey('users.CustomUser', on_delete=models.SET_NULL, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'dashboard_widget'
        ordering = ['position']


class DashboardSnapshot(models.Model):
    """Cached dashboard data"""
    widget = models.ForeignKey(DashboardWidget, on_delete=models.CASCADE)
    
    # Data
    metric_value = models.DecimalField(max_digits=15, decimal_places=2)
    previous_value = models.DecimalField(max_digits=15, decimal_places=2, null=True)
    
    # Change
    change_percentage = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Trend
    trend_data = models.JSONField(default=list)  # Historical data points
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'dashboard_snapshot'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['widget', '-created_at']),
        ]


class KPIMetric(models.Model):
    """Key Performance Indicators"""
    KPI_CHOICES = [
        ('revenue', 'Total Revenue'),
        ('orders', 'Total Orders'),
        ('customers', 'Total Customers'),
        ('conversion', 'Conversion Rate'),
        ('aov', 'Average Order Value'),
        ('clt', 'Customer Lifetime Value'),
        ('churn', 'Churn Rate'),
        ('nps', 'Net Promoter Score'),
    ]
    
    metric_type = models.CharField(max_length=30, choices=KPI_CHOICES, unique=True)
    
    # Current values
    value_today = models.DecimalField(max_digits=15, decimal_places=2)
    value_week = models.DecimalField(max_digits=15, decimal_places=2)
    value_month = models.DecimalField(max_digits=15, decimal_places=2)
    value_year = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Changes
    change_daily = models.DecimalField(max_digits=10, decimal_places=2)
    change_weekly = models.DecimalField(max_digits=10, decimal_places=2)
    change_monthly = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Target
    target = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    achievement = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # %
    
    # Trend
    trend = models.CharField(
        max_length=10,
        choices=[('up', 'Up'), ('down', 'Down'), ('flat', 'Flat')],
        default='flat'
    )
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'kpi_metric'


class CustomReport(models.Model):
    """Custom BI reports"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('archived', 'Archived'),
    ]
    
    # Report info
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Configuration
    metrics = models.JSONField(default=list)  # List of metrics to include
    filters = models.JSONField(default=dict)  # Filter criteria
    group_by = models.CharField(max_length=100, blank=True)
    
    # Scheduling
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    schedule = models.CharField(
        max_length=20,
        choices=[('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly')],
        blank=True
    )
    recipients = models.JSONField(default=list)  # Email recipients
    
    # Owner
    created_by = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE)
    
    # Dates
    created_at = models.DateTimeField(auto_now_add=True)
    last_run = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'custom_report'
        ordering = ['-created_at']


# ============================================================
# BI ENGINE
# ============================================================

class BIEngine:
    """Business Intelligence engine"""
    
    @staticmethod
    def calculate_kpis():
        """Calculate all KPIs"""
        from apps.orders.models import Order
        from apps.users.models import CustomUser
        from django.db.models import Sum, Count, Avg, Q
        
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=7)
        month_start = today_start - timedelta(days=30)
        year_start = today_start - timedelta(days=365)
        
        # Revenue
        revenue_today = Order.objects.filter(
            created_at__gte=today_start
        ).aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        
        revenue_week = Order.objects.filter(
            created_at__gte=week_start
        ).aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        
        revenue_month = Order.objects.filter(
            created_at__gte=month_start
        ).aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        
        revenue_year = Order.objects.filter(
            created_at__gte=year_start
        ).aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        
        # Orders
        orders_today = Order.objects.filter(created_at__gte=today_start).count()
        orders_week = Order.objects.filter(created_at__gte=week_start).count()
        orders_month = Order.objects.filter(created_at__gte=month_start).count()
        orders_year = Order.objects.filter(created_at__gte=year_start).count()
        
        # Customers
        customers_total = CustomUser.objects.filter(is_active=True).count()
        customers_new_month = CustomUser.objects.filter(
            date_joined__gte=month_start
        ).count()
        
        # AOV
        aov_month = revenue_month / orders_month if orders_month > 0 else 0
        aov_year = revenue_year / orders_year if orders_year > 0 else 0
        
        # Conversion Rate
        unique_visitors_month = Order.objects.filter(
            created_at__gte=month_start
        ).values('customer').distinct().count()
        conversion_rate = (orders_month / max(unique_visitors_month, 1)) * 100 if unique_visitors_month > 0 else 0
        
        # Update metrics
        from apps.bi.models import KPIMetric
        
        metrics = {
            'revenue': (revenue_today, revenue_week, revenue_month, revenue_year),
            'orders': (orders_today, orders_week, orders_month, orders_year),
            'customers': (0, 0, customers_new_month, customers_total),
            'aov': (0, 0, aov_month, aov_year),
            'conversion': (0, 0, conversion_rate, conversion_rate),
        }
        
        for metric_type, values in metrics.items():
            kpi, created = KPIMetric.objects.get_or_create(metric_type=metric_type)
            
            kpi.value_today = values[0]
            kpi.value_week = values[1]
            kpi.value_month = values[2]
            kpi.value_year = values[3]
            
            kpi.save()
    
    @staticmethod
    def get_revenue_trend(days=30):
        """Get revenue trend"""
        from apps.orders.models import Order
        from django.db.models import Sum
        from django.db.models.functions import TruncDate
        
        start_date = timezone.now() - timedelta(days=days)
        
        trend = Order.objects.filter(
            created_at__gte=start_date
        ).annotate(
            date=TruncDate('created_at')
        ).values('date').annotate(
            revenue=Sum('total_amount')
        ).order_by('date')
        
        return list(trend)
    
    @staticmethod
    def get_customer_segments():
        """Get customer segmentation"""
        from apps.orders.models import Order
        from django.db.models import Sum, Count, Q
        
        segments = {
            'vip': Order.objects.filter(
                customer__total_spent__gte=100000
            ).values('customer').distinct().count(),
            
            'regular': Order.objects.filter(
                Q(customer__total_spent__gte=10000) & Q(customer__total_spent__lt=100000)
            ).values('customer').distinct().count(),
            
            'occasional': Order.objects.filter(
                Q(customer__total_spent__gte=1000) & Q(customer__total_spent__lt=10000)
            ).values('customer').distinct().count(),
            
            'new': Order.objects.filter(
                customer__date_joined__gte=timezone.now() - timedelta(days=30)
            ).values('customer').distinct().count(),
        }
        
        return segments
    
    @staticmethod
    def get_product_performance():
        """Get top performing products"""
        from apps.orders.models import OrderItem
        from django.db.models import Count, Sum
        
        products = OrderItem.objects.values('product__name').annotate(
            units_sold=Sum('quantity'),
            revenue=Sum('quantity') * 'unit_price',
            orders=Count('order', distinct=True)
        ).order_by('-revenue')[:10]
        
        return list(products)
    
    @staticmethod
    def generate_forecast(days=30):
        """Generate sales forecast"""
        from apps.orders.models import Order
        from sklearn.linear_model import LinearRegression
        import numpy as np
        
        try:
            # Get historical data
            history = BIEngine.get_revenue_trend(days=90)
            
            if len(history) < 7:
                return None
            
            X = np.array(range(len(history))).reshape(-1, 1)
            y = np.array([item['revenue'] for item in history])
            
            # Fit model
            model = LinearRegression()
            model.fit(X, y)
            
            # Forecast
            forecast_x = np.array(range(len(history), len(history) + days)).reshape(-1, 1)
            forecast_y = model.predict(forecast_x)
            
            return list(forecast_y)
        
        except Exception as e:
            logger.error(f'Forecast generation failed: {e}')
            return None


# ============================================================
# CELERY TASKS
# ============================================================

"""
from celery import shared_task

@shared_task
def update_kpis():
    '''Update KPI metrics hourly'''
    BIEngine.calculate_kpis()

@shared_task
def generate_custom_reports():
    '''Generate and email custom reports'''
    from apps.bi.models import CustomReport
    
    reports = CustomReport.objects.filter(status='scheduled')
    
    for report in reports:
        # Generate report
        # Email to recipients
        report.last_run = timezone.now()
        report.save()

# Add to CELERY_BEAT_SCHEDULE:
'update-kpis': {
    'task': 'apps.bi.tasks.update_kpis',
    'schedule': 3600.0,  # Hourly
},
'generate-reports': {
    'task': 'apps.bi.tasks.generate_custom_reports',
    'schedule': 86400.0,  # Daily
},
"""