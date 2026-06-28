# Inventory Optimization Engine - AI-Powered Stock Management

from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import logging

logger = logging.getLogger('inventory')

# ============================================================
# INVENTORY OPTIMIZATION MODELS
# ============================================================

class InventorySKU(models.Model):
    """Individual SKU tracking"""
    product = models.OneToOneField('products.Product', on_delete=models.CASCADE)
    
    # Current levels
    on_hand = models.IntegerField()
    on_order = models.IntegerField(default=0)
    available = models.IntegerField()
    
    # Targets
    min_stock = models.IntegerField()
    max_stock = models.IntegerField()
    reorder_point = models.IntegerField()
    safety_stock = models.IntegerField()
    
    # Costs
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)
    holding_cost_per_unit = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # Annual
    ordering_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Lead time
    lead_time_days = models.IntegerField(default=7)
    lead_time_std_dev = models.IntegerField(default=2)  # days
    
    # Turnover
    annual_turnover = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # units
    
    # Optimization
    eoq = models.IntegerField(default=0)  # Economic order quantity
    suggested_order_qty = models.IntegerField(default=0)
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'inventory_sku'


class SupplierInventory(models.Model):
    """Supplier information for ordering"""
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    supplier = models.CharField(max_length=255)
    
    # Pricing & lead time
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)
    min_order_qty = models.IntegerField()
    lead_time_days = models.IntegerField()
    
    # Reliability
    on_time_delivery_rate = models.DecimalField(max_digits=5, decimal_places=2)  # %
    quality_score = models.DecimalField(max_digits=3, decimal_places=2)  # 0-5
    
    # Status
    is_preferred = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'supplier_inventory'
        unique_together = ['product', 'supplier']


class InventoryForecast(models.Model):
    """AI-generated inventory forecast"""
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    
    # Forecast
    forecast_date = models.DateField()
    predicted_demand = models.IntegerField()
    confidence_interval = models.JSONField()  # [low, high]
    
    # Recommendations
    recommended_stock = models.IntegerField()
    recommended_order_qty = models.IntegerField()
    
    # Accuracy
    actual_demand = models.IntegerField(null=True, blank=True)
    forecast_error = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'inventory_forecast'
        unique_together = ['product', 'forecast_date']


class InventoryAlert(models.Model):
    """Inventory alerts and recommendations"""
    ALERT_TYPE_CHOICES = [
        ('low_stock', 'Low Stock'),
        ('overstock', 'Overstock'),
        ('slow_moving', 'Slow Moving'),
        ('dead_stock', 'Dead Stock'),
        ('forecast_spike', 'Forecast Spike'),
        ('supply_risk', 'Supply Risk'),
    ]
    
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    
    # Alert
    alert_type = models.CharField(max_length=30, choices=ALERT_TYPE_CHOICES)
    description = models.TextField()
    
    # Recommendation
    recommended_action = models.CharField(max_length=255)
    potential_savings = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    is_acknowledged = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'inventory_alert'
        ordering = ['-created_at']


# ============================================================
# INVENTORY OPTIMIZATION ENGINE
# ============================================================

class InventoryOptimizer:
    """Optimize inventory levels"""
    
    @staticmethod
    def calculate_eoq(annual_demand, ordering_cost, holding_cost):
        """Calculate Economic Order Quantity"""
        import math
        
        if holding_cost == 0:
            return 0
        
        eoq = math.sqrt((2 * annual_demand * ordering_cost) / holding_cost)
        return int(eoq)
    
    @staticmethod
    def calculate_safety_stock(lead_time_demand_std_dev, service_level=0.95):
        """Calculate safety stock"""
        from scipy import stats
        
        # Z-score for service level
        z_score = stats.norm.ppf(service_level)
        safety_stock = z_score * lead_time_demand_std_dev
        
        return int(safety_stock)
    
    @staticmethod
    def calculate_reorder_point(daily_demand, lead_time_days, safety_stock):
        """Calculate reorder point"""
        reorder_point = (daily_demand * lead_time_days) + safety_stock
        return int(reorder_point)
    
    @staticmethod
    def optimize_sku(product):
        """Optimize individual SKU"""
        from apps.orders.models import Order, OrderItem
        from apps.inventory.models import InventorySKU
        
        try:
            sku = InventorySKU.objects.get(product=product)
        except InventorySKU.DoesNotExist:
            return None
        
        # Calculate annual turnover
        year_ago = timezone.now() - timedelta(days=365)
        annual_items_sold = OrderItem.objects.filter(
            product=product,
            order__created_at__gte=year_ago
        ).aggregate(models.Sum('quantity'))['quantity__sum'] or 0
        
        sku.annual_turnover = annual_items_sold
        
        # Calculate daily demand
        daily_demand = annual_items_sold / 365
        
        # Calculate EOQ
        if sku.holding_cost_per_unit > 0:
            sku.eoq = InventoryOptimizer.calculate_eoq(
                annual_items_sold,
                sku.ordering_cost,
                sku.holding_cost_per_unit
            )
        
        # Calculate safety stock
        lead_time_demand_std_dev = daily_demand * sku.lead_time_std_dev
        sku.safety_stock = InventoryOptimizer.calculate_safety_stock(lead_time_demand_std_dev)
        
        # Calculate reorder point
        sku.reorder_point = InventoryOptimizer.calculate_reorder_point(
            daily_demand,
            sku.lead_time_days,
            sku.safety_stock
        )
        
        # Suggested order quantity
        sku.suggested_order_qty = sku.eoq if sku.eoq > 0 else int(daily_demand * sku.lead_time_days)
        
        sku.save()
        
        logger.info(f'SKU optimized: {product.name}')
        
        return sku
    
    @staticmethod
    def generate_orders():
        """Generate purchase orders based on optimization"""
        from apps.products.models import Product
        from apps.inventory.models import InventorySKU
        
        purchase_orders = []
        
        skus = InventorySKU.objects.filter(product__is_active=True)
        
        for sku in skus:
            # Check if reorder needed
            available = sku.on_hand + sku.on_order
            
            if available <= sku.reorder_point:
                # Find best supplier
                suppliers = sku.product.supplierinventory_set.filter(is_active=True).order_by('-on_time_delivery_rate')
                
                if suppliers.exists():
                    supplier = suppliers.first()
                    
                    order = {
                        'product': sku.product.name,
                        'quantity': max(sku.suggested_order_qty, supplier.min_order_qty),
                        'supplier': supplier.supplier,
                        'unit_cost': supplier.unit_cost,
                        'lead_time': supplier.lead_time_days,
                    }
                    
                    purchase_orders.append(order)
        
        return purchase_orders
    
    @staticmethod
    def forecast_demand(product, days=30):
        """Forecast future demand"""
        from apps.orders.models import Order, OrderItem
        from sklearn.ensemble import RandomForestRegressor
        import numpy as np
        
        # Get historical sales
        history = []
        for i in range(90, 0, -1):
            date = timezone.now().date() - timedelta(days=i)
            sales = OrderItem.objects.filter(
                product=product,
                order__created_at__date=date
            ).aggregate(models.Sum('quantity'))['quantity__sum'] or 0
            
            history.append({
                'date': date,
                'sales': sales,
                'day_of_week': date.weekday(),
                'is_weekend': 1 if date.weekday() >= 5 else 0,
            })
        
        if len(history) < 14:
            return None
        
        X = np.array([[h['day_of_week'], h['is_weekend']] for h in history])
        y = np.array([h['sales'] for h in history])
        
        # Train model
        model = RandomForestRegressor(n_estimators=10, random_state=42)
        model.fit(X, y)
        
        # Forecast
        forecasts = []
        for i in range(days):
            future_date = timezone.now().date() + timedelta(days=i+1)
            X_pred = np.array([[future_date.weekday(), 1 if future_date.weekday() >= 5 else 0]])
            pred = model.predict(X_pred)[0]
            
            forecasts.append({
                'date': future_date,
                'predicted_demand': max(0, int(pred)),
            })
        
        return forecasts
    
    @staticmethod
    def detect_slow_moving_items():
        """Detect slow-moving inventory"""
        from apps.products.models import Product
        from apps.orders.models import OrderItem
        
        slow_movers = []
        
        products = Product.objects.filter(is_active=True)
        
        for product in products:
            # Check sales in last 90 days
            sales_90 = OrderItem.objects.filter(
                product=product,
                order__created_at__gte=timezone.now() - timedelta(days=90)
            ).aggregate(models.Sum('quantity'))['quantity__sum'] or 0
            
            # Check stock age
            if sales_90 < 10:  # Less than 10 units sold
                slow_movers.append({
                    'product': product.name,
                    'sales_90d': sales_90,
                    'current_stock': product.stock,
                    'estimated_stock_out_months': (product.stock / max(sales_90 / 90, 0.01)) if sales_90 > 0 else float('inf'),
                })
        
        return slow_movers


# ============================================================
# CELERY TASKS
# ============================================================

"""
from celery import shared_task

@shared_task
def optimize_all_inventory():
    '''Optimize all SKUs'''
    from apps.products.models import Product
    
    products = Product.objects.filter(is_active=True)
    
    for product in products:
        try:
            InventoryOptimizer.optimize_sku(product)
        except Exception as e:
            logger.error(f'SKU optimization failed for {product.id}: {e}')

@shared_task
def generate_purchase_orders():
    '''Generate purchase orders based on optimization'''
    orders = InventoryOptimizer.generate_orders()
    
    for order in orders:
        # Create PO in system
        pass

@shared_task
def update_demand_forecasts():
    '''Update demand forecasts'''
    from apps.products.models import Product
    from apps.inventory.models import InventoryForecast
    
    products = Product.objects.filter(is_active=True)
    
    for product in products:
        forecasts = InventoryOptimizer.forecast_demand(product)
        
        if forecasts:
            for fc in forecasts:
                InventoryForecast.objects.get_or_create(
                    product=product,
                    forecast_date=fc['date'],
                    defaults={'predicted_demand': fc['predicted_demand']}
                )

# Add to CELERY_BEAT_SCHEDULE:
'optimize-inventory': {
    'task': 'apps.inventory.tasks.optimize_all_inventory',
    'schedule': 86400.0,  # Daily
},
'generate-purchase-orders': {
    'task': 'apps.inventory.tasks.generate_purchase_orders',
    'schedule': 3600.0,  # Hourly
},
'update-forecasts': {
    'task': 'apps.inventory.tasks.update_demand_forecasts',
    'schedule': 604800.0,  # Weekly
},
"""