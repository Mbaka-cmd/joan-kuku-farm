# Warehouse Management System (WMS)

from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta
import logging

logger = logging.getLogger('wms')

# ============================================================
# WAREHOUSE MODELS
# ============================================================

class Warehouse(models.Model):
    """Warehouse locations"""
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)
    
    # Location
    address = models.TextField()
    city = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    
    # Capacity
    total_capacity = models.IntegerField()  # SKUs
    available_capacity = models.IntegerField()
    
    # Manager
    manager = models.ForeignKey('users.CustomUser', null=True, blank=True, on_delete=models.SET_NULL)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'warehouse'


class StorageLocation(models.Model):
    """Physical storage locations in warehouse"""
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE)
    
    # Location
    aisle = models.CharField(max_length=20)
    rack = models.CharField(max_length=20)
    shelf = models.CharField(max_length=20)
    bin = models.CharField(max_length=20)
    
    location_code = models.CharField(max_length=50, unique=True)
    
    # Capacity
    capacity = models.IntegerField()
    current_quantity = models.IntegerField(default=0)
    
    # Product
    product = models.ForeignKey('products.Product', null=True, blank=True, on_delete=models.SET_NULL)
    
    is_available = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'storage_location'
        unique_together = ['warehouse', 'aisle', 'rack', 'shelf', 'bin']


class InventoryMovement(models.Model):
    """Track inventory movements"""
    MOVEMENT_TYPE = [
        ('inbound', 'Inbound'),
        ('outbound', 'Outbound'),
        ('transfer', 'Transfer'),
        ('adjustment', 'Adjustment'),
        ('return', 'Return'),
    ]
    
    # Movement
    movement_id = models.CharField(max_length=50, unique=True)
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPE)
    
    # Product
    product = models.ForeignKey('products.Product', on_delete=models.PROTECT)
    quantity = models.IntegerField()
    
    # Locations
    source_location = models.ForeignKey(StorageLocation, null=True, blank=True, 
                                       on_delete=models.SET_NULL, related_name='outbound')
    destination_location = models.ForeignKey(StorageLocation, null=True, blank=True, 
                                            on_delete=models.SET_NULL, related_name='inbound')
    
    # Reference
    order = models.ForeignKey('orders.Order', null=True, blank=True, on_delete=models.SET_NULL)
    purchase_order = models.ForeignKey('supply_chain.PurchaseOrder', null=True, blank=True, on_delete=models.SET_NULL)
    
    # Status
    is_processed = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'inventory_movement'
        ordering = ['-created_at']


class PickingTask(models.Model):
    """Picking tasks for orders"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    # Task
    task_id = models.CharField(max_length=50, unique=True)
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE)
    
    # Items
    items = models.JSONField(default=list)  # [{product_id, qty, location}]
    
    # Assignment
    assigned_to = models.ForeignKey('users.CustomUser', null=True, blank=True, on_delete=models.SET_NULL)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Timing
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'picking_task'
        ordering = ['status', 'created_at']


class PackingTask(models.Model):
    """Packing tasks for shipment"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    ]
    
    picking_task = models.OneToOneField(PickingTask, on_delete=models.CASCADE)
    
    # Packing
    package_weight = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    package_dimensions = models.JSONField(default=dict)  # {length, width, height}
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Assigned
    assigned_to = models.ForeignKey('users.CustomUser', null=True, blank=True, on_delete=models.SET_NULL)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'packing_task'


class WarehouseReceipt(models.Model):
    """Goods receipt"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('receiving', 'Receiving'),
        ('quality_check', 'Quality Check'),
        ('stocked', 'Stocked'),
        ('rejected', 'Rejected'),
    ]
    
    # Receipt
    receipt_id = models.CharField(max_length=50, unique=True)
    purchase_order = models.ForeignKey('supply_chain.PurchaseOrder', on_delete=models.CASCADE)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT)
    
    # Items
    items = models.JSONField(default=list)  # Items received
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Quality
    quality_check_passed = models.BooleanField(null=True, blank=True)
    quality_notes = models.TextField(blank=True)
    
    # Timestamps
    received_at = models.DateTimeField()
    stocked_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'warehouse_receipt'
        ordering = ['-created_at']


# ============================================================
# WAREHOUSE ENGINE
# ============================================================

class WarehouseEngine:
    """Warehouse operations"""
    
    @staticmethod
    def create_picking_task(order):
        """Create picking task for order"""
        from apps.warehouse.models import PickingTask, StorageLocation
        import uuid
        
        picking_task = PickingTask.objects.create(
            task_id=f"PICK-{uuid.uuid4().hex[:8].upper()}",
            order=order,
        )
        
        # Find storage locations for each item
        items = []
        for item in order.orderitem_set.all():
            location = StorageLocation.objects.filter(
                product=item.product,
                current_quantity__gte=item.quantity
            ).first()
            
            if location:
                items.append({
                    'product_id': item.product.id,
                    'product_name': item.product.name,
                    'quantity': item.quantity,
                    'location': location.location_code,
                })
        
        picking_task.items = items
        picking_task.save()
        
        logger.info(f'Picking task created: {picking_task.task_id}')
        
        return picking_task
    
    @staticmethod
    def complete_picking_task(picking_task):
        """Mark picking task complete"""
        picking_task.status = 'completed'
        picking_task.completed_at = timezone.now()
        picking_task.save()
        
        # Update storage locations
        for item in picking_task.items:
            location = StorageLocation.objects.get(location_code=item['location'])
            location.current_quantity -= item['quantity']
            location.save()
        
        logger.info(f'Picking task completed: {picking_task.task_id}')
    
    @staticmethod
    def process_warehouse_receipt(purchase_order, warehouse):
        """Process incoming goods"""
        from apps.warehouse.models import WarehouseReceipt, StorageLocation
        import uuid
        
        receipt = WarehouseReceipt.objects.create(
            receipt_id=f"RCPT-{uuid.uuid4().hex[:8].upper()}",
            purchase_order=purchase_order,
            warehouse=warehouse,
            received_at=timezone.now(),
        )
        
        # Process each item
        for po_item in purchase_order.items:
            # Find or allocate storage location
            location = WarehouseEngine.find_storage_location(
                warehouse,
                po_item.get('product_id'),
                po_item.get('quantity')
            )
            
            if location:
                location.current_quantity += po_item.get('quantity', 0)
                location.save()
        
        receipt.status = 'stocked'
        receipt.stocked_at = timezone.now()
        receipt.save()
        
        logger.info(f'Receipt processed: {receipt.receipt_id}')
        
        return receipt
    
    @staticmethod
    def find_storage_location(warehouse, product_id, quantity):
        """Find best storage location for product"""
        from apps.warehouse.models import StorageLocation
        
        # Prefer existing location for product
        location = StorageLocation.objects.filter(
            warehouse=warehouse,
            product_id=product_id,
            is_available=True
        ).exclude(
            current_quantity__gte=models.F('capacity')
        ).first()
        
        # Otherwise find empty location
        if not location:
            location = StorageLocation.objects.filter(
                warehouse=warehouse,
                product__isnull=True,
                is_available=True
            ).exclude(
                current_quantity__gte=models.F('capacity')
            ).first()
            
            if location:
                location.product_id = product_id
                location.save()
        
        return location
    
    @staticmethod
    def get_warehouse_metrics(warehouse):
        """Get warehouse performance metrics"""
        from apps.warehouse.models import PickingTask, WarehouseReceipt
        
        # Picking efficiency
        completed_picks = PickingTask.objects.filter(
            warehouse=warehouse,
            status='completed',
            completed_at__gte=timezone.now() - timedelta(days=7)
        ).count()
        
        avg_pick_time = PickingTask.objects.filter(
            warehouse=warehouse,
            status='completed'
        ).aggregate(
            avg_time=(models.F('completed_at') - models.F('created_at'))
        )
        
        # Receipts
        total_receipts = WarehouseReceipt.objects.filter(
            warehouse=warehouse,
            created_at__gte=timezone.now() - timedelta(days=30)
        ).count()
        
        rejected_receipts = WarehouseReceipt.objects.filter(
            warehouse=warehouse,
            status='rejected'
        ).count()
        
        metrics = {
            'completed_picks_week': completed_picks,
            'total_receipts_month': total_receipts,
            'rejected_receipts': rejected_receipts,
            'capacity_utilization': (warehouse.total_capacity - warehouse.available_capacity) / warehouse.total_capacity * 100 if warehouse.total_capacity > 0 else 0,
        }
        
        return metrics


# ============================================================
# CELERY TASKS
# ============================================================

"""
from celery import shared_task

@shared_task
def create_picking_tasks():
    '''Create picking tasks for new orders'''
    from apps.orders.models import Order
    from apps.warehouse.models import PickingTask
    
    orders = Order.objects.filter(
        status='confirmed',
        pickingTasks__isnull=True
    )
    
    for order in orders:
        WarehouseEngine.create_picking_task(order)

@shared_task
def process_warehouse_receipts():
    '''Process pending receipts'''
    from apps.warehouse.models import WarehouseReceipt
    
    pending = WarehouseReceipt.objects.filter(status='pending')
    
    for receipt in pending:
        receipt.status = 'receiving'
        receipt.save()

# Add to CELERY_BEAT_SCHEDULE:
'create-picking-tasks': {
    'task': 'apps.warehouse.tasks.create_picking_tasks',
    'schedule': 1800.0,  # Every 30 minutes
},
'process-receipts': {
    'task': 'apps.warehouse.tasks.process_warehouse_receipts',
    'schedule': 3600.0,  # Hourly
},
"""