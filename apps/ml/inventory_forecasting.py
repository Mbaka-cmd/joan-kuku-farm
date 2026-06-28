# Inventory Management & Sales Forecasting

from django.db import models
from django.db.models import Sum, Count, Avg, F
from datetime import datetime, timedelta
from decimal import Decimal
import numpy as np
from scipy import stats

# ============================================================
# INVENTORY MODELS
# ============================================================

class InventoryLog(models.Model):
    """Track inventory changes"""
    ACTION_CHOICES = [
        ('in', 'Stock In'),
        ('out', 'Stock Out'),
        ('adjust', 'Adjustment'),
        ('return', 'Return'),
        ('damage', 'Damage'),
    ]
    
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    quantity = models.IntegerField()
    reason = models.TextField(blank=True)
    
    # Reference
    order = models.ForeignKey('orders.Order', null=True, blank=True, on_delete=models.SET_NULL)
    user = models.ForeignKey('users.CustomUser', on_delete=models.SET_NULL, null=True)
    
    # Timestamp
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'inventory_log'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['product', 'created_at']),
        ]


class InventoryForecast(models.Model):
    """Store sales forecasts"""
    product = models.OneToOneField('products.Product', on_delete=models.CASCADE)
    
    # Forecast data
    daily_average_sales = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    weekly_average_sales = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    monthly_average_sales = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Trend
    trend = models.CharField(
        max_length=20,
        choices=[('up', 'Increasing'), ('down', 'Decreasing'), ('stable', 'Stable')],
        default='stable'
    )
    trend_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Predictions
    estimated_stockout_days = models.IntegerField(null=True)  # Days until stock runs out
    recommended_reorder_quantity = models.IntegerField(default=0)
    reorder_point = models.IntegerField(default=0)
    
    # Seasonality
    is_seasonal = models.BooleanField(default=False)
    peak_months = models.JSONField(default=list)
    
    # Metadata
    accuracy_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # 0-100
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'inventory_forecast'


class StockAlert(models.Model):
    """Alert when stock threshold reached"""
    ALERT_TYPES = [
        ('low', 'Low Stock'),
        ('out', 'Out of Stock'),
        ('overstock', 'Overstock'),
        ('slow_moving', 'Slow Moving'),
    ]
    
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES)
    threshold_value = models.IntegerField()
    is_active = models.BooleanField(default=True)
    
    # Notification
    notify_admin = models.BooleanField(default=True)
    notify_email = models.EmailField(blank=True)
    
    # Tracking
    triggered_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'stock_alert'


# ============================================================
# INVENTORY MANAGEMENT
# ============================================================

class InventoryManager:
    """Manage inventory operations"""
    
    @staticmethod
    def update_stock(product, quantity, action, reason='', order=None, user=None):
        """Update product stock and log change"""
        
        # Update stock
        if action == 'in':
            product.stock += quantity
        elif action == 'out':
            product.stock = max(0, product.stock - quantity)
        elif action == 'adjust':
            product.stock = quantity
        elif action == 'damage':
            product.stock = max(0, product.stock - quantity)
        
        product.save()
        
        # Log change
        InventoryLog.objects.create(
            product=product,
            action=action,
            quantity=quantity,
            reason=reason,
            order=order,
            user=user,
        )
        
        # Check alerts
        InventoryManager.check_stock_alerts(product)
        
        return product
    
    @staticmethod
    def check_stock_alerts(product):
        """Check if any alerts should be triggered"""
        alerts = StockAlert.objects.filter(product=product, is_active=True)
        
        for alert in alerts:
            should_trigger = False
            
            if alert.alert_type == 'low' and product.stock <= alert.threshold_value:
                should_trigger = True
            elif alert.alert_type == 'out' and product.stock == 0:
                should_trigger = True
            elif alert.alert_type == 'overstock' and product.stock >= alert.threshold_value:
                should_trigger = True
            
            if should_trigger and alert.triggered_at is None:
                alert.triggered_at = datetime.now()
                alert.save()
                
                # Send notification
                if alert.notify_admin:
                    InventoryManager.notify_alert(alert)
    
    @staticmethod
    def notify_alert(alert):
        """Send alert notification"""
        # TODO: Implement email/SMS notification
        pass
    
    @staticmethod
    def get_inventory_value(product):
        """Calculate total inventory value"""
        return float(product.price) * product.stock
    
    @staticmethod
    def get_total_inventory_value():
        """Get total value of all inventory"""
        from apps.products.models import Product
        
        total = 0
        for product in Product.objects.all():
            total += InventoryManager.get_inventory_value(product)
        
        return total
    
    @staticmethod
    def get_inventory_turnover_ratio(product, days=30):
        """Calculate inventory turnover ratio"""
        from apps.orders.models import OrderItem
        
        # Get orders in period
        start_date = datetime.now() - timedelta(days=days)
        orders = OrderItem.objects.filter(
            product=product,
            order__created_at__gte=start_date
        ).aggregate(total=Sum('quantity'))
        
        units_sold = orders['total'] or 0
        avg_inventory = (product.stock + (product.stock * 0.5)) / 2  # Simplified
        
        if avg_inventory == 0:
            return 0
        
        return units_sold / avg_inventory


# ============================================================
# SALES FORECASTING
# ============================================================

class SalesForecaster:
    """Predict future sales and inventory needs"""
    
    @staticmethod
    def generate_forecast(product, lookback_days=90):
        """Generate sales forecast using time series analysis"""
        from apps.orders.models import OrderItem
        
        # Get historical sales data
        end_date = datetime.now()
        start_date = end_date - timedelta(days=lookback_days)
        
        daily_sales = {}
        for i in range(lookback_days):
            date = start_date + timedelta(days=i)
            sales = OrderItem.objects.filter(
                product=product,
                order__created_at__date=date.date()
            ).aggregate(total=Sum('quantity'))['total'] or 0
            
            daily_sales[date.date()] = sales
        
        # Convert to array
        sales_array = np.array(list(daily_sales.values()))
        
        if len(sales_array) < 7:
            return None  # Not enough data
        
        # Calculate statistics
        daily_avg = float(np.mean(sales_array))
        weekly_avg = float(np.mean(sales_array.reshape(-1, 7).sum(axis=1)))
        monthly_avg = float(np.mean(sales_array.reshape(-1, 30).sum(axis=1)))
        
        # Calculate trend
        x = np.arange(len(sales_array))
        slope, intercept, r_value, p_value, std_err = stats.linregress(x, sales_array)
        
        trend = 'stable'
        trend_percentage = 0
        if slope > 0:
            trend = 'up'
            trend_percentage = (slope / daily_avg * 100) if daily_avg > 0 else 0
        elif slope < 0:
            trend = 'down'
            trend_percentage = abs(slope / daily_avg * 100) if daily_avg > 0 else 0
        
        # Calculate days until stockout
        current_stock = product.stock
        estimated_stockout_days = None
        if daily_avg > 0:
            estimated_stockout_days = int(current_stock / daily_avg)
        
        # Recommend reorder
        lead_time_days = 7  # Assume 7-day lead time
        reorder_point = int(daily_avg * lead_time_days)
        safety_stock = int(daily_avg * 3)  # 3 days safety stock
        recommended_quantity = int(daily_avg * 30) - current_stock  # 30-day supply
        
        # Detect seasonality (simplified)
        is_seasonal = False
        peak_months = []
        
        if len(sales_array) >= 60:
            monthly_data = sales_array.reshape(-1, 30)
            monthly_avg_sales = monthly_data.sum(axis=1)
            
            # Check if std dev is > 20% of mean
            if monthly_data.std() > (monthly_data.mean() * 0.2):
                is_seasonal = True
                peak_months = [i for i, v in enumerate(monthly_avg_sales) if v > monthly_data.mean()]
        
        # Store forecast
        forecast, created = InventoryForecast.objects.get_or_create(product=product)
        forecast.daily_average_sales = Decimal(str(daily_avg))
        forecast.weekly_average_sales = Decimal(str(weekly_avg))
        forecast.monthly_average_sales = Decimal(str(monthly_avg))
        forecast.trend = trend
        forecast.trend_percentage = Decimal(str(trend_percentage))
        forecast.estimated_stockout_days = estimated_stockout_days
        forecast.reorder_point = reorder_point
        forecast.recommended_reorder_quantity = recommended_quantity
        forecast.is_seasonal = is_seasonal
        forecast.peak_months = peak_months
        forecast.accuracy_score = Decimal(str(r_value ** 2 * 100))  # R-squared as accuracy
        forecast.save()
        
        return forecast
    
    @staticmethod
    def forecast_all_products():
        """Generate forecasts for all products"""
        from apps.products.models import Product
        
        products = Product.objects.filter(is_active=True)
        
        for product in products:
            try:
                SalesForecaster.generate_forecast(product)
            except Exception as e:
                print(f"Error forecasting {product.name}: {e}")


# ============================================================
# CELERY TASKS
# ============================================================

"""
from celery import shared_task

@shared_task
def update_sales_forecasts():
    '''Update forecasts daily'''
    SalesForecaster.forecast_all_products()
    return 'Forecasts updated'

@shared_task
def check_inventory_alerts():
    '''Check alerts hourly'''
    from apps.products.models import Product
    
    for product in Product.objects.all():
        InventoryManager.check_stock_alerts(product)
    
    return 'Alerts checked'

# Add to CELERY_BEAT_SCHEDULE:
'update-sales-forecasts': {
    'task': 'apps.inventory.tasks.update_sales_forecasts',
    'schedule': 86400.0,  # Daily
},
'check-inventory-alerts': {
    'task': 'apps.inventory.tasks.check_inventory_alerts',
    'schedule': 3600.0,  # Hourly
},
"""

# ============================================================
# API ENDPOINTS
# ============================================================

"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

class InventoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = InventoryLog.objects.all()
    
    @action(detail=False)
    def dashboard(self, request):
        '''Get inventory dashboard'''
        return Response({
            'total_value': InventoryManager.get_total_inventory_value(),
            'low_stock_count': StockAlert.objects.filter(
                alert_type='low',
                triggered_at__isnull=False
            ).count(),
            'stockouts': StockAlert.objects.filter(
                alert_type='out',
                triggered_at__isnull=False
            ).count(),
        })
    
    @action(detail=False)
    def forecasts(self, request):
        '''Get all forecasts'''
        forecasts = InventoryForecast.objects.all()
        return Response({
            'forecasts': [
                {
                    'product_id': f.product.id,
                    'daily_avg': str(f.daily_average_sales),
                    'trend': f.trend,
                    'stockout_days': f.estimated_stockout_days,
                }
                for f in forecasts
            ]
        })
"""