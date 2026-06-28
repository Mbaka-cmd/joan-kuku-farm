# Bulk Operations & Data Import/Export System

from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta
import csv
import json
import logging

logger = logging.getLogger('bulk_ops')

# ============================================================
# BULK OPERATION MODELS
# ============================================================

class BulkOperation(models.Model):
    """Track bulk operations"""
    OPERATION_TYPE = [
        ('import_products', 'Import Products'),
        ('import_orders', 'Import Orders'),
        ('export_products', 'Export Products'),
        ('export_orders', 'Export Orders'),
        ('price_update', 'Price Update'),
        ('stock_update', 'Stock Update'),
        ('delete_products', 'Delete Products'),
        ('update_categories', 'Update Categories'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('partially_failed', 'Partially Failed'),
    ]
    
    # Operation
    operation_type = models.CharField(max_length=30, choices=OPERATION_TYPE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # File
    input_file = models.FileField(upload_to='bulk_operations/%Y/%m/%d/', null=True, blank=True)
    output_file = models.FileField(upload_to='bulk_operations/%Y/%m/%d/', null=True, blank=True)
    
    # Stats
    total_rows = models.IntegerField(default=0)
    successful_rows = models.IntegerField(default=0)
    failed_rows = models.IntegerField(default=0)
    
    # User
    initiated_by = models.ForeignKey('users.CustomUser', on_delete=models.SET_NULL, null=True)
    
    # Dates
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Error log
    error_log = models.TextField(blank=True)
    
    class Meta:
        db_table = 'bulk_operation'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['initiated_by']),
        ]


class BulkOperationLog(models.Model):
    """Log for individual bulk operation items"""
    operation = models.ForeignKey(BulkOperation, on_delete=models.CASCADE, related_name='logs')
    
    # Row info
    row_number = models.IntegerField()
    status = models.CharField(
        max_length=20,
        choices=[('success', 'Success'), ('failed', 'Failed'), ('skipped', 'Skipped')]
    )
    
    # Data
    original_data = models.JSONField()
    processed_data = models.JSONField(blank=True)
    
    # Error
    error_message = models.TextField(blank=True)
    
    # Reference
    reference_id = models.CharField(max_length=100, blank=True)  # Product ID, Order ID, etc
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'bulk_operation_log'
        ordering = ['row_number']


class ImportTemplate(models.Model):
    """Templates for bulk import"""
    name = models.CharField(max_length=255)
    operation_type = models.CharField(max_length=30, choices=BulkOperation.OPERATION_TYPE)
    
    # Template
    column_mapping = models.JSONField()  # Maps CSV columns to model fields
    field_validators = models.JSONField(default=dict)
    
    # Usage
    created_by = models.ForeignKey('users.CustomUser', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'import_template'


# ============================================================
# BULK OPERATIONS PROCESSOR
# ============================================================

class BulkOperationProcessor:
    """Process bulk operations"""
    
    @staticmethod
    def import_products(file_path, user):
        """Import products from CSV"""
        from apps.products.models import Product, Category
        from apps.bulk_operations.models import BulkOperation, BulkOperationLog
        
        # Create operation record
        operation = BulkOperation.objects.create(
            operation_type='import_products',
            initiated_by=user,
        )
        
        try:
            rows = BulkOperationProcessor.read_csv(file_path)
            operation.total_rows = len(rows)
            operation.started_at = timezone.now()
            operation.status = 'processing'
            operation.save()
            
            for idx, row in enumerate(rows, 1):
                try:
                    # Validate data
                    errors = BulkOperationProcessor.validate_product_row(row)
                    
                    if errors:
                        BulkOperationLog.objects.create(
                            operation=operation,
                            row_number=idx,
                            status='failed',
                            original_data=row,
                            error_message='; '.join(errors)
                        )
                        operation.failed_rows += 1
                        continue
                    
                    # Get or create category
                    category = None
                    if row.get('category'):
                        category, _ = Category.objects.get_or_create(name=row['category'])
                    
                    # Create product
                    product = Product.objects.create(
                        name=row['name'],
                        description=row.get('description', ''),
                        price=Decimal(row['price']),
                        sku=row.get('sku', ''),
                        category=category,
                        stock=int(row.get('stock', 0)),
                        is_active=row.get('is_active', 'true').lower() == 'true',
                    )
                    
                    BulkOperationLog.objects.create(
                        operation=operation,
                        row_number=idx,
                        status='success',
                        original_data=row,
                        processed_data={'product_id': product.id},
                        reference_id=str(product.id)
                    )
                    operation.successful_rows += 1
                
                except Exception as e:
                    BulkOperationLog.objects.create(
                        operation=operation,
                        row_number=idx,
                        status='failed',
                        original_data=row,
                        error_message=str(e)
                    )
                    operation.failed_rows += 1
            
            operation.status = 'completed' if operation.failed_rows == 0 else 'partially_failed'
            operation.completed_at = timezone.now()
            operation.save()
            
        except Exception as e:
            operation.status = 'failed'
            operation.error_log = str(e)
            operation.completed_at = timezone.now()
            operation.save()
            logger.error(f'Bulk import failed: {e}')
        
        return operation
    
    @staticmethod
    def export_products(filters=None, user=None):
        """Export products to CSV"""
        from apps.products.models import Product
        from apps.bulk_operations.models import BulkOperation
        from io import StringIO
        
        operation = BulkOperation.objects.create(
            operation_type='export_products',
            initiated_by=user,
        )
        
        try:
            # Get products
            products = Product.objects.filter(is_active=True)
            
            if filters:
                if 'category' in filters:
                    products = products.filter(category_id=filters['category'])
                if 'min_price' in filters:
                    products = products.filter(price__gte=filters['min_price'])
            
            operation.total_rows = products.count()
            operation.started_at = timezone.now()
            operation.status = 'processing'
            operation.save()
            
            # Generate CSV
            output = StringIO()
            writer = csv.DictWriter(
                output,
                fieldnames=['id', 'name', 'sku', 'description', 'price', 'category', 'stock', 'rating']
            )
            writer.writeheader()
            
            for product in products:
                writer.writerow({
                    'id': product.id,
                    'name': product.name,
                    'sku': product.sku,
                    'description': product.description[:100],
                    'price': product.price,
                    'category': product.category.name if product.category else '',
                    'stock': product.stock,
                    'rating': product.rating,
                })
            
            # Save file
            from django.core.files.base import ContentFile
            operation.output_file = ContentFile(
                output.getvalue().encode('utf-8'),
                name=f'products_export_{timezone.now().timestamp()}.csv'
            )
            
            operation.successful_rows = operation.total_rows
            operation.status = 'completed'
            operation.completed_at = timezone.now()
            operation.save()
            
        except Exception as e:
            operation.status = 'failed'
            operation.error_log = str(e)
            operation.completed_at = timezone.now()
            operation.save()
            logger.error(f'Bulk export failed: {e}')
        
        return operation
    
    @staticmethod
    def bulk_price_update(product_ids, price_adjustment, adjustment_type='percentage'):
        """Update prices in bulk"""
        from apps.products.models import Product
        from apps.bulk_operations.models import BulkOperation
        from decimal import Decimal
        
        operation = BulkOperation.objects.create(
            operation_type='price_update',
        )
        
        try:
            products = Product.objects.filter(id__in=product_ids)
            operation.total_rows = products.count()
            operation.started_at = timezone.now()
            operation.status = 'processing'
            operation.save()
            
            adjustment = Decimal(str(price_adjustment))
            
            for product in products:
                try:
                    if adjustment_type == 'percentage':
                        product.price = product.price * (1 + adjustment / 100)
                    else:  # fixed
                        product.price += adjustment
                    
                    product.save()
                    operation.successful_rows += 1
                
                except Exception as e:
                    operation.failed_rows += 1
                    logger.error(f'Failed to update price for product {product.id}: {e}')
            
            operation.status = 'completed'
            operation.completed_at = timezone.now()
            operation.save()
            
        except Exception as e:
            operation.status = 'failed'
            operation.error_log = str(e)
            operation.completed_at = timezone.now()
            operation.save()
            logger.error(f'Bulk price update failed: {e}')
        
        return operation
    
    @staticmethod
    def validate_product_row(row):
        """Validate product import row"""
        errors = []
        
        # Required fields
        if not row.get('name'):
            errors.append('Name is required')
        
        if not row.get('price'):
            errors.append('Price is required')
        else:
            try:
                float(row['price'])
            except ValueError:
                errors.append('Invalid price format')
        
        # Optional validations
        if row.get('stock'):
            try:
                int(row['stock'])
            except ValueError:
                errors.append('Invalid stock format')
        
        return errors
    
    @staticmethod
    def read_csv(file_path):
        """Read CSV file"""
        rows = []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
        
        return rows


# ============================================================
# CELERY TASKS
# ============================================================

"""
from celery import shared_task

@shared_task
def process_bulk_operation(operation_id):
    '''Process bulk operation asynchronously'''
    from apps.bulk_operations.models import BulkOperation
    
    operation = BulkOperation.objects.get(id=operation_id)
    
    if operation.operation_type == 'import_products':
        BulkOperationProcessor.import_products(operation.input_file.path, operation.initiated_by)
    elif operation.operation_type == 'export_products':
        BulkOperationProcessor.export_products(user=operation.initiated_by)

@shared_task
def cleanup_old_operations():
    '''Delete old bulk operations'''
    from apps.bulk_operations.models import BulkOperation
    
    cutoff = timezone.now() - timedelta(days=90)
    BulkOperation.objects.filter(created_at__lt=cutoff).delete()

# Add to CELERY_BEAT_SCHEDULE:
'cleanup-bulk-operations': {
    'task': 'apps.bulk_operations.tasks.cleanup_old_operations',
    'schedule': 604800.0,  # Weekly
},
"""