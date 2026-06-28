from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator


class CustomUser(AbstractUser):
    """
    Extended User model with phone number and location fields
    """
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message='Phone number must be entered in the format: +2547XXXXXXXX'
    )
    
    phone_number = models.CharField(
        validators=[phone_regex],
        max_length=20,
        unique=True
    )
    address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100, default='Nairobi')
    county = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    
    # Account status
    is_verified = models.BooleanField(default=False)
    email_verified = models.BooleanField(default=False)
    phone_verified = models.BooleanField(default=False)
    
    # Profile info
    profile_picture = models.ImageField(upload_to='profiles/', null=True, blank=True)
    bio = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'users_customuser'
        ordering = ['-created_at']
        verbose_name = 'Custom User'
        verbose_name_plural = 'Custom Users'
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.phone_number})"
    
    @property
    def is_profile_complete(self):
        """Check if user has completed their profile"""
        return all([
            self.first_name,
            self.last_name,
            self.phone_number,
            self.address,
            self.city
        ])
    
    def get_total_orders(self):
        """Get count of all orders"""
        return self.orders.count()
    
    def get_total_spent(self):
        """Get total amount spent on orders"""
        from apps.orders.models import Order
        total = Order.objects.filter(
            customer=self,
            is_paid=True
        ).aggregate(models.Sum('total_amount'))['total_amount__sum']
        return total or 0


class UserPreferences(models.Model):
    """
    User notification and communication preferences
    """
    NOTIFICATION_CHOICES = [
        ('email', 'Email Only'),
        ('whatsapp', 'WhatsApp Only'),
        ('sms', 'SMS Only'),
        ('all', 'All Methods'),
    ]
    
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='preferences'
    )
    
    # Notification preferences
    receive_order_updates = models.BooleanField(default=True)
    receive_promotions = models.BooleanField(default=True)
    receive_newsletters = models.BooleanField(default=False)
    preferred_notification = models.CharField(
        max_length=20,
        choices=NOTIFICATION_CHOICES,
        default='whatsapp'
    )
    
    # Privacy settings
    is_public_profile = models.BooleanField(default=False)
    allow_marketing = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = 'User Preferences'
    
    def __str__(self):
        return f"Preferences for {self.user.get_full_name()}"