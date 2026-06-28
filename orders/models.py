from django.db import models
from django.core.validators import MinValueValidator
import uuid


class Order(models.Model):
    """Main order model"""
    STATUS_CHOICES = [
        ('pending', 'Pending Payment'),
        ('confirmed', 'Confirmed'),
        ('processing', 'Processing'),
        ('in_transit', 'In Transit'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]
    
    order_id = models.CharField(max_length=50, unique=True, db_index=True)
    customer = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.PROTECT,
        related_name='orders'
    )
    
    # Order details
    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    subtotal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)]
    )
    tax = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)]
    )
    discount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)]
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    notes = models.TextField(blank=True)
    
    # Delivery information
    delivery_phone = models.CharField(max_length=20)
    delivery_address = models.TextField()
    delivery_city = models.CharField(max_length=100)
    delivery_county = models.CharField(max_length=100, blank=True)
    delivery_postal_code = models.CharField(max_length=20, blank=True)
    delivery_instructions = models.TextField(blank=True)
    
    # Tracking
    shipped_date = models.DateTimeField(null=True, blank=True)
    delivered_date = models.DateTimeField(null=True, blank=True)
    tracking_number = models.CharField(max_length=100, blank=True)
    
    # Payment status
    is_paid = models.BooleanField(default=False)
    payment_method = models.CharField(
        max_length=50,
        blank=True,
        choices=[
            ('mpesa', 'M-Pesa'),
            ('card', 'Card/Stripe'),
            ('bank_transfer', 'Bank Transfer'),
            ('cash_on_delivery', 'Cash on Delivery'),
        ]
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer', 'created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['order_id']),
        ]
    
    def __str__(self):
        return f"{self.order_id} - {self.customer.get_full_name()}"
    
    def save(self, *args, **kwargs):
        """Generate order ID if not exists"""
        if not self.order_id:
            timestamp = timezone.now().strftime('%Y%m%d')
            random_suffix = str(uuid.uuid4().hex[:6]).upper()
            self.order_id = f"JKF-{timestamp}-{random_suffix}"
        
        # Calculate total
        if not self.total_amount and self.subtotal:
            self.total_amount = self.subtotal + self.tax - self.discount
        
        super().save(*args, **kwargs)
    
    def get_item_count(self):
        """Get total number of items in order"""
        return sum(item.quantity for item in self.items.all())
    
    def can_be_cancelled(self):
        """Check if order can be cancelled"""
        non_cancellable_statuses = ['in_transit', 'delivered', 'cancelled']
        return self.status not in non_cancellable_statuses
    
    def get_status_display_verbose(self):
        """Get user-friendly status"""
        status_messages = {
            'pending': '⏳ Awaiting Payment',
            'confirmed': '✅ Order Confirmed',
            'processing': '📦 Processing',
            'in_transit': '🚚 On the Way',
            'delivered': '📍 Delivered',
            'cancelled': '❌ Cancelled',
        }
        return status_messages.get(self.status, self.get_status_display())


class OrderItem(models.Model):
    """Items within an order"""
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items'
    )
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.PROTECT
    )
    
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text='Price at time of order'
    )
    subtotal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    
    # Product snapshot (in case product is deleted)
    product_name_snapshot = models.CharField(max_length=200, blank=True)
    product_unit_snapshot = models.CharField(max_length=50, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.product.name} x {self.quantity}"
    
    def save(self, *args, **kwargs):
        """Calculate subtotal and capture product snapshot"""
        self.subtotal = self.unit_price * self.quantity
        
        if not self.product_name_snapshot:
            self.product_name_snapshot = self.product.name
        if not self.product_unit_snapshot:
            self.product_unit_snapshot = self.product.unit
        
        super().save(*args, **kwargs)


class OrderStatusHistory(models.Model):
    """Track order status changes"""
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='status_history'
    )
    
    from_status = models.CharField(max_length=20)
    to_status = models.CharField(max_length=20)
    reason = models.TextField(blank=True)
    changed_by = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='order_status_changes'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Order Status Histories'
    
    def __str__(self):
        return f"{self.order.order_id}: {self.from_status} → {self.to_status}"


class OrderCancellation(models.Model):
    """Track order cancellations"""
    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name='cancellation'
    )
    
    reason = models.CharField(max_length=200)
    details = models.TextField(blank=True)
    refund_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    refund_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('processed', 'Processed'),
            ('failed', 'Failed'),
        ],
        default='pending'
    )
    
    cancelled_by = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        related_name='order_cancellations'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Cancellation of {self.order.order_id}"


# Import timezone at the top
from django.utils import timezone