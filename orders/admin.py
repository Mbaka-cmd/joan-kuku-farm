from django.contrib import admin
from .models import Order, OrderItem, OrderStatusHistory, OrderCancellation


class OrderItemInline(admin.TabularInline):
    """Inline order items"""
    model = OrderItem
    extra = 0
    readonly_fields = ('product_name_snapshot', 'product_unit_snapshot', 'subtotal', 'created_at')
    fields = ('product', 'quantity', 'unit_price', 'subtotal')


class OrderStatusHistoryInline(admin.TabularInline):
    """Inline order status history"""
    model = OrderStatusHistory
    extra = 0
    readonly_fields = ('from_status', 'to_status', 'changed_by', 'created_at')
    fields = ('from_status', 'to_status', 'reason', 'changed_by', 'created_at')
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Order admin"""
    
    list_display = (
        'order_id', 'customer', 'total_amount', 'status',
        'is_paid', 'payment_method', 'created_at'
    )
    list_filter = (
        'status', 'is_paid', 'payment_method', 'created_at', 'updated_at'
    )
    search_fields = (
        'order_id', 'customer__username', 'customer__email',
        'customer__phone_number', 'delivery_phone', 'delivery_address'
    )
    readonly_fields = (
        'order_id', 'created_at', 'updated_at',
        'shipped_date', 'delivered_date'
    )
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Order Information', {
            'fields': ('order_id', 'customer', 'status', 'notes')
        }),
        ('Items Summary', {
            'fields': ('subtotal', 'tax', 'discount', 'total_amount')
        }),
        ('Payment', {
            'fields': ('is_paid', 'payment_method')
        }),
        ('Delivery Information', {
            'fields': (
                'delivery_phone', 'delivery_address', 'delivery_city',
                'delivery_county', 'delivery_postal_code', 'delivery_instructions'
            )
        }),
        ('Shipping & Tracking', {
            'fields': (
                'shipped_date', 'delivered_date', 'tracking_number'
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [OrderItemInline, OrderStatusHistoryInline]
    actions = [
        'mark_as_confirmed', 'mark_as_processing', 'mark_as_shipped',
        'mark_as_delivered', 'mark_as_cancelled'
    ]
    
    def mark_as_confirmed(self, request, queryset):
        updated = queryset.update(status='confirmed')
        self.message_user(request, f'{updated} orders marked as confirmed')
    mark_as_confirmed.short_description = 'Mark as confirmed'
    
    def mark_as_processing(self, request, queryset):
        updated = queryset.update(status='processing')
        self.message_user(request, f'{updated} orders marked as processing')
    mark_as_processing.short_description = 'Mark as processing'
    
    def mark_as_shipped(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(
            status='in_transit',
            shipped_date=timezone.now()
        )
        self.message_user(request, f'{updated} orders marked as shipped')
    mark_as_shipped.short_description = 'Mark as shipped'
    
    def mark_as_delivered(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(
            status='delivered',
            delivered_date=timezone.now()
        )
        self.message_user(request, f'{updated} orders marked as delivered')
    mark_as_delivered.short_description = 'Mark as delivered'
    
    def mark_as_cancelled(self, request, queryset):
        updated = queryset.update(status='cancelled')
        self.message_user(request, f'{updated} orders marked as cancelled')
    mark_as_cancelled.short_description = 'Mark as cancelled'


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    """Order item admin"""
    
    list_display = (
        'order', 'product', 'quantity', 'unit_price', 'subtotal'
    )
    list_filter = ('created_at', 'order__status')
    search_fields = (
        'order__order_id', 'product__name', 'product__SKU'
    )
    readonly_fields = (
        'product_name_snapshot', 'product_unit_snapshot', 'subtotal', 'created_at'
    )
    
    fieldsets = (
        ('Order', {
            'fields': ('order',)
        }),
        ('Product', {
            'fields': ('product', 'product_name_snapshot', 'product_unit_snapshot')
        }),
        ('Pricing', {
            'fields': ('quantity', 'unit_price', 'subtotal')
        }),
        ('Timestamp', {
            'fields': ('created_at',)
        }),
    )


@admin.register(OrderStatusHistory)
class OrderStatusHistoryAdmin(admin.ModelAdmin):
    """Order status history admin"""
    
    list_display = (
        'order', 'from_status', 'to_status', 'changed_by', 'created_at'
    )
    list_filter = ('from_status', 'to_status', 'created_at')
    search_fields = ('order__order_id', 'reason')
    readonly_fields = ('created_at', 'order', 'from_status', 'to_status')
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Order', {
            'fields': ('order',)
        }),
        ('Status Change', {
            'fields': ('from_status', 'to_status', 'reason')
        }),
        ('Changed By', {
            'fields': ('changed_by',)
        }),
        ('Timestamp', {
            'fields': ('created_at',)
        }),
    )
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(OrderCancellation)
class OrderCancellationAdmin(admin.ModelAdmin):
    """Order cancellation admin"""
    
    list_display = (
        'order', 'reason', 'refund_status', 'refund_amount', 'created_at'
    )
    list_filter = ('refund_status', 'created_at')
    search_fields = ('order__order_id', 'reason', 'cancelled_by__username')
    readonly_fields = ('created_at', 'processed_at', 'order')
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Order', {
            'fields': ('order',)
        }),
        ('Cancellation Details', {
            'fields': ('reason', 'details', 'cancelled_by')
        }),
        ('Refund', {
            'fields': ('refund_amount', 'refund_status')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'processed_at')
        }),
    )