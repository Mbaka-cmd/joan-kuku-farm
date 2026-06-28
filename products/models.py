from django.db import models
from django.core.validators import MinValueValidator


class Category(models.Model):
    """Product categories"""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='categories/', null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def get_product_count(self):
        """Get count of active products in this category"""
        return self.products.filter(is_active=True).count()


class Product(models.Model):
    """Main product model"""
    
    SKU = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField()
    
    # Category and pricing
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='products'
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    unit = models.CharField(max_length=50)  # "per egg", "per bird", "per chick"
    
    # Inventory
    stock = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    min_stock = models.IntegerField(default=10)  # Alert when low
    reserved_quantity = models.IntegerField(default=0)  # Quantity in pending orders
    
    # Product details
    is_vaccinated = models.BooleanField(default=False)
    description_long = models.TextField(blank=True)
    specifications = models.JSONField(default=dict, blank=True)  # e.g., {'color': 'brown', 'age': '2 weeks'}
    
    # Media
    image = models.ImageField(upload_to='products/', null=True, blank=True)
    images = models.JSONField(default=list, blank=True)  # Additional images
    
    # Status
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Products'
        indexes = [
            models.Index(fields=['category', 'is_active']),
            models.Index(fields=['SKU']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.unit}) - KES {self.price}"
    
    def is_low_stock(self):
        """Check if stock is low"""
        available = self.stock - self.reserved_quantity
        return available <= self.min_stock
    
    def get_available_stock(self):
        """Get actual available stock (total - reserved)"""
        return max(0, self.stock - self.reserved_quantity)
    
    def can_fulfill_order(self, quantity):
        """Check if product can fulfill order quantity"""
        return self.get_available_stock() >= quantity


class ProductReview(models.Model):
    """Product reviews and ratings"""
    RATING_CHOICES = [
        (1, '⭐ Poor'),
        (2, '⭐⭐ Fair'),
        (3, '⭐⭐⭐ Good'),
        (4, '⭐⭐⭐⭐ Very Good'),
        (5, '⭐⭐⭐⭐⭐ Excellent'),
    ]
    
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    user = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.CASCADE,
        related_name='product_reviews'
    )
    
    rating = models.IntegerField(choices=RATING_CHOICES)
    title = models.CharField(max_length=200)
    comment = models.TextField()
    
    # Moderation
    is_verified_purchase = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False)
    
    # Engagement
    helpful_count = models.IntegerField(default=0)
    unhelpful_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['product', 'user']  # One review per user per product
    
    def __str__(self):
        return f"{self.user} - {self.product.name} ({self.rating}★)"
    
    def get_rating_display(self):
        return dict(self.RATING_CHOICES)[self.rating]


class PriceHistory(models.Model):
    """Track price changes for products"""
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='price_history'
    )
    
    old_price = models.DecimalField(max_digits=10, decimal_places=2)
    new_price = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.CharField(
        max_length=100,
        default='Manual update',
        help_text='Reason for price change'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Price Histories'
    
    def __str__(self):
        return f"{self.product.name}: KES {self.old_price} → KES {self.new_price}"