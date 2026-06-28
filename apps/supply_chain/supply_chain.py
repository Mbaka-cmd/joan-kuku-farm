# Supply Chain Optimization System - Vendor Management & Logistics

from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import logging

logger = logging.getLogger('supply_chain')

# ============================================================
# SUPPLY CHAIN MODELS
# ============================================================

class Vendor(models.Model):
    """Vendor/supplier information"""
    RATING_CHOICES = [(i, str(i)) for i in range(1, 6)]
    
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Contact
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    address = models.TextField()
    
    # Performance metrics
    on_time_rate = models.DecimalField(max_digits=5, decimal_places=2, default=95)  # %
    quality_score = models.IntegerField(choices=RATING_CHOICES, default=5)
    price_competitiveness = models.IntegerField(choices=RATING_CHOICES, default=3)
    
    # Financial
    average_lead_time = models.IntegerField()  # days
    min_order_qty = models.IntegerField(default=1)
    payment_terms = models.CharField(max_length=100)  # e.g., Net 30
    
    # Status
    is_preferred = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    # Ratings
    overall_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    review_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'vendor'
        ordering = ['-overall_rating', 'name']


class PurchaseOrder(models.Model):
    """Purchase orders to vendors"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('confirmed', 'Confirmed'),
        ('shipped', 'Shipped'),
        ('received', 'Received'),
        ('invoiced', 'Invoiced'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
    ]
    
    po_number = models.CharField(max_length=50, unique=True)
    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT)
    
    # Items
    items = models.JSONField(default=list)  # [{product_id, sku, qty, unit_price}]
    
    # Costs
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Dates
    order_date = models.DateTimeField()
    expected_delivery = models.DateTimeField()
    actual_delivery = models.DateTimeField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Tracking
    tracking_number = models.CharField(max_length=100, blank=True)
    shipping_carrier = models.CharField(max_length=100, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'purchase_order'
        ordering = ['-created_at']


class Shipment(models.Model):
    """Incoming/outgoing shipments"""
    DIRECTION_CHOICES = [
        ('inbound', 'Inbound (Vendor)'),
        ('outbound', 'Outbound (Customer)'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_transit', 'In Transit'),
        ('delivered', 'Delivered'),
        ('delayed', 'Delayed'),
        ('cancelled', 'Cancelled'),
    ]
    
    shipment_id = models.CharField(max_length=50, unique=True)
    direction = models.CharField(max_length=20, choices=DIRECTION_CHOICES)
    
    # Reference
    purchase_order = models.ForeignKey(PurchaseOrder, null=True, blank=True, on_delete=models.SET_NULL)
    order = models.ForeignKey('orders.Order', null=True, blank=True, on_delete=models.SET_NULL)
    
    # Details
    origin = models.CharField(max_length=255)
    destination = models.CharField(max_length=255)
    carrier = models.CharField(max_length=100)
    tracking_number = models.CharField(max_length=100)
    
    # Dates
    dispatch_date = models.DateTimeField()
    expected_delivery = models.DateTimeField()
    actual_delivery = models.DateTimeField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Updates
    last_update = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'shipment'
        ordering = ['-dispatch_date']


class SupplierPerformance(models.Model):
    """Track vendor performance"""
    vendor = models.OneToOneField(Vendor, on_delete=models.CASCADE)
    
    # Metrics (Last 90 days)
    total_orders = models.IntegerField(default=0)
    on_time_orders = models.IntegerField(default=0)
    quality_issues = models.IntegerField(default=0)
    price_variance = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # %
    
    # Scores
    reliability_score = models.DecimalField(max_digits=5, decimal_places=2)
    quality_score = models.DecimalField(max_digits=5, decimal_places=2)
    cost_score = models.DecimalField(max_digits=5, decimal_places=2)
    
    # Trend
    score_trend = models.CharField(
        max_length=20,
        choices=[('improving', 'Improving'), ('stable', 'Stable'), ('declining', 'Declining')]
    )
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'supplier_performance'


# ============================================================
# SUPPLY CHAIN ENGINE
# ============================================================

class SupplyChainOptimizer:
    """Optimize supply chain"""
    
    @staticmethod
    def select_best_vendor(product, quantity):
        """Select best vendor for purchase"""
        from apps.products.models import Product
        from apps.supply_chain.models import Vendor, SupplierProductPrice
        
        vendors = Vendor.objects.filter(is_active=True).order_by('-overall_rating')
        
        best_vendor = None
        best_score = -1
        
        for vendor in vendors:
            # Get price for this product
            try:
                price_info = SupplierProductPrice.objects.get(
                    vendor=vendor,
                    product=product
                )
                unit_price = price_info.unit_price
            except:
                continue
            
            # Calculate score
            score = (
                vendor.on_time_rate * 0.4 +  # 40% on-time delivery
                (vendor.quality_score * 20) * 0.3 +  # 30% quality
                ((100 - vendor.price_competitiveness * 20)) * 0.3  # 30% price
            )
            
            if score > best_score:
                best_score = score
                best_vendor = vendor
        
        return best_vendor
    
    @staticmethod
    def optimize_purchase_orders():
        """Generate optimized purchase orders"""
        from apps.inventory.models import InventorySKU
        from apps.supply_chain.models import PurchaseOrder
        
        skus_to_reorder = InventorySKU.objects.filter(
            on_hand__lte=models.F('reorder_point')
        )
        
        pos = []
        
        for sku in skus_to_reorder:
            # Select vendor
            vendor = SupplyChainOptimizer.select_best_vendor(
                sku.product,
                sku.suggested_order_qty
            )
            
            if not vendor:
                continue
            
            # Create PO
            po = PurchaseOrder.objects.create(
                po_number=f"PO-{timezone.now().strftime('%Y%m%d%H%M%S')}",
                vendor=vendor,
                items=[{
                    'product_id': sku.product.id,
                    'sku': sku.product.sku,
                    'quantity': sku.suggested_order_qty,
                    'unit_price': vendor.supplierinventory_set.get(product=sku.product).unit_cost,
                }],
                order_date=timezone.now(),
                expected_delivery=timezone.now() + timedelta(days=vendor.average_lead_time),
            )
            
            # Calculate totals
            po.subtotal = sku.suggested_order_qty * Decimal(str(po.items[0]['unit_price']))
            po.shipping_cost = Decimal('100')  # Estimate
            po.total = po.subtotal + po.shipping_cost
            po.save()
            
            pos.append(po)
        
        return pos
    
    @staticmethod
    def track_shipment(tracking_number):
        """Track shipment status"""
        # Integration with carrier APIs
        # This would call FedEx, DHL, etc. APIs
        pass
    
    @staticmethod
    def calculate_vendor_score(vendor):
        """Calculate comprehensive vendor score"""
        from apps.supply_chain.models import PurchaseOrder, SupplierPerformance
        
        # Get recent orders
        orders = PurchaseOrder.objects.filter(
            vendor=vendor,
            order_date__gte=timezone.now() - timedelta(days=90)
        )
        
        if not orders.exists():
            return None
        
        # Calculate metrics
        on_time_orders = orders.filter(
            actual_delivery__lte=models.F('expected_delivery')
        ).count()
        
        on_time_rate = (on_time_orders / orders.count()) * 100
        
        # Get quality issues
        quality_issues = orders.filter(quality_issue=True).count()
        quality_score = max(0, 100 - (quality_issues * 10))
        
        # Price variance
        avg_price = orders.aggregate(models.Avg('total'))['total__avg'] or 0
        
        # Update performance
        perf, created = SupplierPerformance.objects.get_or_create(vendor=vendor)
        
        perf.total_orders = orders.count()
        perf.on_time_orders = on_time_orders
        perf.quality_issues = quality_issues
        perf.reliability_score = Decimal(str(on_time_rate))
        perf.quality_score = Decimal(str(quality_score))
        
        # Determine trend
        if perf.reliability_score > 95:
            perf.score_trend = 'improving'
        elif perf.reliability_score < 80:
            perf.score_trend = 'declining'
        else:
            perf.score_trend = 'stable'
        
        perf.save()
        
        return perf


# ============================================================
# CELERY TASKS
# ============================================================

"""
from celery import shared_task

@shared_task
def generate_optimized_purchase_orders():
    '''Generate optimized purchase orders'''
    SupplyChainOptimizer.optimize_purchase_orders()

@shared_task
def update_vendor_scores():
    '''Update vendor performance scores'''
    from apps.supply_chain.models import Vendor
    
    vendors = Vendor.objects.filter(is_active=True)
    
    for vendor in vendors:
        SupplyChainOptimizer.calculate_vendor_score(vendor)

@shared_task
def track_inbound_shipments():
    '''Track inbound shipments'''
    from apps.supply_chain.models import Shipment
    
    in_transit = Shipment.objects.filter(
        direction='inbound',
        status='in_transit'
    )
    
    for shipment in in_transit:
        SupplyChainOptimizer.track_shipment(shipment.tracking_number)

# Add to CELERY_BEAT_SCHEDULE:
'optimize-purchase-orders': {
    'task': 'apps.supply_chain.tasks.generate_optimized_purchase_orders',
    'schedule': 86400.0,  # Daily
},
'update-vendor-scores': {
    'task': 'apps.supply_chain.tasks.update_vendor_scores',
    'schedule': 604800.0,  # Weekly
},
"""