# Multivendor Marketplace Platform System

from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import logging

logger = logging.getLogger('marketplace')

# ============================================================
# MULTIVENDOR MODELS
# ============================================================

class Vendor(models.Model):
    """Marketplace vendors/sellers"""
    VENDOR_TYPE = [
        ('individual', 'Individual'),
        ('business', 'Business'),
        ('enterprise', 'Enterprise'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('closed', 'Closed'),
    ]
    
    # Account
    user = models.OneToOneField('users.CustomUser', on_delete=models.CASCADE)
    vendor_name = models.CharField(max_length=255)
    vendor_type = models.CharField(max_length=20, choices=VENDOR_TYPE)
    
    # Details
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to='vendor_logos/')
    banner = models.ImageField(upload_to='vendor_banners/', blank=True)
    
    # Contact
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=20)
    
    # Address
    address = models.TextField()
    city = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    
    # Commission
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=15)  # %
    
    # Rating & Reviews
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    review_count = models.IntegerField(default=0)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Verification
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    
    # Stats
    total_products = models.IntegerField(default=0)
    total_orders = models.IntegerField(default=0)
    total_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'marketplace_vendor'
        ordering = ['-rating', '-created_at']


class VendorProduct(models.Model):
    """Products listed by vendors"""
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE)
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    
    # Pricing
    vendor_price = models.DecimalField(max_digits=10, decimal_places=2)
    vendor_sku = models.CharField(max_length=100, unique=True)
    
    # Stock
    vendor_stock = models.IntegerField()
    reserved_stock = models.IntegerField(default=0)
    available_stock = models.IntegerField()
    
    # Details
    vendor_description = models.TextField(blank=True)
    
    # Fulfillment
    fulfillment_type = models.CharField(
        max_length=20,
        choices=[
            ('vendor', 'Vendor Fulfilled'),
            ('fba', 'Marketplace Fulfilled'),
        ]
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Performance
    sales_count = models.IntegerField(default=0)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'vendor_product'
        unique_together = ['vendor', 'product']


class MarketplaceOrder(models.Model):
    """Orders from marketplace"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('returned', 'Returned'),
    ]
    
    # Order
    order = models.OneToOneField('orders.Order', on_delete=models.CASCADE)
    
    # Vendor
    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT)
    vendor_product = models.ForeignKey(VendorProduct, on_delete=models.SET_NULL, null=True)
    
    # Pricing
    vendor_price = models.DecimalField(max_digits=10, decimal_places=2)
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2)
    vendor_payout = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Fulfillment
    is_fulfilled_by_marketplace = models.BooleanField(default=False)
    tracking_number = models.CharField(max_length=100, blank=True)
    
    # Dates
    confirmed_at = models.DateTimeField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'marketplace_order'
        ordering = ['-created_at']


class VendorPayout(models.Model):
    """Vendor payouts"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE)
    
    # Period
    period_start = models.DateField()
    period_end = models.DateField()
    
    # Amounts
    total_sales = models.DecimalField(max_digits=12, decimal_places=2)
    commissions = models.DecimalField(max_digits=12, decimal_places=2)
    fees = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payout_amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Payment
    payment_method = models.CharField(
        max_length=50,
        choices=[('bank_transfer', 'Bank Transfer'), ('mpesa', 'M-Pesa'), ('check', 'Check')]
    )
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Dates
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'vendor_payout'
        ordering = ['-created_at']


class VendorReview(models.Model):
    """Reviews for vendors"""
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='reviews')
    customer = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE)
    
    # Review
    rating = models.IntegerField(choices=[(i, str(i)) for i in range(1, 6)])
    title = models.CharField(max_length=255)
    content = models.TextField()
    
    # Aspects
    communication_rating = models.IntegerField(null=True, blank=True)
    delivery_rating = models.IntegerField(null=True, blank=True)
    quality_rating = models.IntegerField(null=True, blank=True)
    
    # Status
    is_verified_purchase = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'vendor_review'
        unique_together = ['vendor', 'customer']


# ============================================================
# MARKETPLACE ENGINE
# ============================================================

class MarketplaceEngine:
    """Manage marketplace operations"""
    
    @staticmethod
    def register_vendor(user, vendor_data):
        """Register new vendor"""
        from apps.marketplace.models import Vendor
        
        vendor = Vendor.objects.create(
            user=user,
            vendor_name=vendor_data['name'],
            vendor_type=vendor_data.get('type', 'individual'),
            description=vendor_data.get('description', ''),
            contact_email=vendor_data['email'],
            contact_phone=vendor_data['phone'],
            address=vendor_data['address'],
            city=vendor_data['city'],
            country=vendor_data['country'],
        )
        
        logger.info(f'Vendor registered: {vendor.vendor_name}')
        
        return vendor
    
    @staticmethod
    def approve_vendor(vendor):
        """Approve vendor"""
        vendor.status = 'active'
        vendor.is_verified = True
        vendor.verified_at = timezone.now()
        vendor.save()
        
        logger.info(f'Vendor approved: {vendor.vendor_name}')
    
    @staticmethod
    def list_vendor_product(vendor, product, price, stock):
        """List product for vendor"""
        from apps.marketplace.models import VendorProduct
        import uuid
        
        vendor_product = VendorProduct.objects.create(
            vendor=vendor,
            product=product,
            vendor_price=Decimal(str(price)),
            vendor_sku=f"VSK-{uuid.uuid4().hex[:8].upper()}",
            vendor_stock=stock,
            available_stock=stock,
        )
        
        return vendor_product
    
    @staticmethod
    def process_marketplace_order(order):
        """Process order from marketplace"""
        from apps.marketplace.models import MarketplaceOrder, VendorProduct
        
        for item in order.orderitem_set.all():
            # Find vendor product
            try:
                vendor_product = VendorProduct.objects.filter(
                    product=item.product,
                    is_active=True
                ).order_by('-sales_count').first()
                
                if not vendor_product:
                    continue
                
                vendor = vendor_product.vendor
                
                # Calculate commission
                commission = item.unit_price * item.quantity * (vendor.commission_rate / 100)
                payout = (item.unit_price * item.quantity) - commission
                
                # Create marketplace order
                marketplace_order = MarketplaceOrder.objects.create(
                    order=order,
                    vendor=vendor,
                    vendor_product=vendor_product,
                    vendor_price=item.unit_price,
                    commission_amount=commission,
                    vendor_payout=payout,
                )
                
                # Update vendor stats
                vendor.total_orders += 1
                vendor.total_revenue += marketplace_order.vendor_price * item.quantity
                vendor.save()
                
                # Update stock
                vendor_product.available_stock -= item.quantity
                vendor_product.reserved_stock += item.quantity
                vendor_product.sales_count += 1
                vendor_product.save()
                
            except Exception as e:
                logger.error(f'Failed to process marketplace order: {e}')
    
    @staticmethod
    def calculate_vendor_payouts():
        """Calculate payouts for vendors"""
        from apps.marketplace.models import Vendor, VendorPayout, MarketplaceOrder
        from django.db.models import Sum
        
        vendors = Vendor.objects.filter(status='active')
        
        for vendor in vendors:
            # Get orders from last month
            month_start = (timezone.now() - timedelta(days=30)).date()
            month_end = timezone.now().date()
            
            orders = MarketplaceOrder.objects.filter(
                vendor=vendor,
                created_at__date__gte=month_start,
                created_at__date__lte=month_end,
                status='delivered'
            )
            
            if not orders.exists():
                continue
            
            total_sales = orders.aggregate(Sum('vendor_price'))['vendor_price__sum'] or 0
            commission = orders.aggregate(Sum('commission_amount'))['commission_amount__sum'] or 0
            
            payout = total_sales - commission
            
            # Create payout
            payout_obj = VendorPayout.objects.create(
                vendor=vendor,
                period_start=month_start,
                period_end=month_end,
                total_sales=total_sales,
                commissions=commission,
                payout_amount=payout,
                payment_method='mpesa',
            )
            
            logger.info(f'Payout calculated for {vendor.vendor_name}: KES {payout}')
    
    @staticmethod
    def update_vendor_rating(vendor):
        """Update vendor rating"""
        from apps.marketplace.models import VendorReview
        
        reviews = VendorReview.objects.filter(vendor=vendor)
        
        if reviews.exists():
            avg_rating = reviews.aggregate(models.Avg('rating'))['rating__avg']
            vendor.rating = avg_rating
            vendor.review_count = reviews.count()
            vendor.save()


# ============================================================
# CELERY TASKS
# ============================================================

"""
from celery import shared_task

@shared_task
def process_vendor_orders():
    '''Process vendor orders'''
    from apps.marketplace.models import MarketplaceOrder
    
    pending = MarketplaceOrder.objects.filter(status='pending')
    
    for order in pending:
        order.status = 'confirmed'
        order.confirmed_at = timezone.now()
        order.save()

@shared_task
def calculate_vendor_payouts():
    '''Calculate vendor payouts'''
    MarketplaceEngine.calculate_vendor_payouts()

@shared_task
def update_vendor_ratings():
    '''Update vendor ratings'''
    from apps.marketplace.models import Vendor
    
    vendors = Vendor.objects.filter(status='active')
    
    for vendor in vendors:
        MarketplaceEngine.update_vendor_rating(vendor)

# Add to CELERY_BEAT_SCHEDULE:
'process-vendor-orders': {
    'task': 'apps.marketplace.tasks.process_vendor_orders',
    'schedule': 3600.0,  # Hourly
},
'calculate-payouts': {
    'task': 'apps.marketplace.tasks.calculate_vendor_payouts',
    'schedule': 2592000.0,  # Monthly
},
'update-ratings': {
    'task': 'apps.marketplace.tasks.update_vendor_ratings',
    'schedule': 86400.0,  # Daily
},
"""