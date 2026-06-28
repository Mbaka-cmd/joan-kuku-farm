from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import CustomUser, UserPreferences


@admin.register(CustomUser)
class CustomUserAdmin(BaseUserAdmin):
    """Custom User admin"""
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Contact Information', {
            'fields': ('phone_number', 'address', 'city', 'county', 'postal_code')
        }),
        ('Verification', {
            'fields': ('is_verified', 'email_verified', 'phone_verified')
        }),
        ('Profile', {
            'fields': ('profile_picture', 'bio')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at')
    
    list_display = (
        'id', 'username', 'email', 'phone_number',
        'is_verified', 'email_verified', 'is_staff', 'created_at'
    )
    list_filter = (
        'is_verified', 'email_verified', 'phone_verified',
        'is_staff', 'is_superuser', 'created_at'
    )
    search_fields = ('username', 'email', 'phone_number', 'first_name', 'last_name')
    ordering = ('-created_at',)
    
    actions = ['mark_as_verified', 'mark_email_verified', 'mark_phone_verified']
    
    def mark_as_verified(self, request, queryset):
        """Mark selected users as verified"""
        updated = queryset.update(is_verified=True)
        self.message_user(request, f'{updated} users marked as verified')
    mark_as_verified.short_description = 'Mark selected users as verified'
    
    def mark_email_verified(self, request, queryset):
        """Mark selected users email as verified"""
        updated = queryset.update(email_verified=True)
        self.message_user(request, f'{updated} users\' emails marked as verified')
    mark_email_verified.short_description = 'Mark selected users\' emails as verified'
    
    def mark_phone_verified(self, request, queryset):
        """Mark selected users phone as verified"""
        updated = queryset.update(phone_verified=True)
        self.message_user(request, f'{updated} users\' phones marked as verified')
    mark_phone_verified.short_description = 'Mark selected users\' phones as verified'


@admin.register(UserPreferences)
class UserPreferencesAdmin(admin.ModelAdmin):
    """User preferences admin"""
    
    list_display = (
        'user', 'preferred_notification', 'receive_order_updates',
        'receive_promotions', 'receive_newsletters'
    )
    list_filter = (
        'preferred_notification', 'receive_order_updates',
        'receive_promotions', 'receive_newsletters'
    )
    search_fields = ('user__username', 'user__email', 'user__phone_number')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Notification Preferences', {
            'fields': (
                'receive_order_updates', 'receive_promotions',
                'receive_newsletters', 'preferred_notification'
            )
        }),
        ('Privacy', {
            'fields': ('is_public_profile', 'allow_marketing')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )