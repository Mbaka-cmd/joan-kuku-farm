from django.contrib import admin
from .models import Payment, PaymentRefund, MpesaTransaction, PaymentLog


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Payment admin"""
    
    list_display = (
        'order', 'amount', 'method', 'status', 'transaction_id', 'created_at'
    )
    list_filter = ('method', 'status', 'created_at')
    search_fields = ('transaction_id', 'order__order_id', 'order__customer__email')
    readonly_fields = ('created_at', 'updated_at', 'completed_at', 'transaction_id')
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Order & Amount', {
            'fields': ('order', 'amount')
        }),
        ('Payment Details', {
            'fields': (
                'method', 'status', 'transaction_id', 'payment_reference'
            )
        }),
        ('Metadata', {
            'fields': ('payment_data',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'completed_at')
        }),
    )
    
    actions = ['mark_as_completed', 'mark_as_failed']
    
    def mark_as_completed(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(status='completed', completed_at=timezone.now())
        self.message_user(request, f'{updated} payments marked as completed')
    mark_as_completed.short_description = 'Mark as completed'
    
    def mark_as_failed(self, request, queryset):
        updated = queryset.update(status='failed')
        self.message_user(request, f'{updated} payments marked as failed')
    mark_as_failed.short_description = 'Mark as failed'


@admin.register(PaymentRefund)
class PaymentRefundAdmin(admin.ModelAdmin):
    """Payment refund admin"""
    
    list_display = (
        'payment', 'amount', 'reason', 'status', 'initiated_by', 'created_at'
    )
    list_filter = ('status', 'created_at')
    search_fields = (
        'payment__order__order_id', 'payment__transaction_id', 'reason'
    )
    readonly_fields = ('created_at', 'completed_at', 'payment')
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Payment & Refund', {
            'fields': ('payment', 'amount')
        }),
        ('Details', {
            'fields': ('reason', 'notes')
        }),
        ('Status', {
            'fields': ('status', 'refund_transaction_id')
        }),
        ('Process', {
            'fields': ('initiated_by',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'completed_at')
        }),
    )
    
    actions = ['mark_as_completed', 'mark_as_processing', 'mark_as_failed']
    
    def mark_as_completed(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(status='completed', completed_at=timezone.now())
        self.message_user(request, f'{updated} refunds marked as completed')
    mark_as_completed.short_description = 'Mark as completed'
    
    def mark_as_processing(self, request, queryset):
        updated = queryset.update(status='processing')
        self.message_user(request, f'{updated} refunds marked as processing')
    mark_as_processing.short_description = 'Mark as processing'
    
    def mark_as_failed(self, request, queryset):
        updated = queryset.update(status='failed')
        self.message_user(request, f'{updated} refunds marked as failed')
    mark_as_failed.short_description = 'Mark as failed'


@admin.register(MpesaTransaction)
class MpesaTransactionAdmin(admin.ModelAdmin):
    """M-Pesa transaction admin"""
    
    list_display = (
        'checkout_request_id', 'phone_number', 'amount', 'status',
        'mpesa_receipt_number', 'created_at'
    )
    list_filter = ('status', 'created_at')
    search_fields = (
        'checkout_request_id', 'phone_number', 'mpesa_receipt_number',
        'payment__order__order_id'
    )
    readonly_fields = (
        'created_at', 'updated_at', 'payment', 'checkout_request_id',
        'merchant_request_id'
    )
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Payment', {
            'fields': ('payment',)
        }),
        ('M-Pesa Request', {
            'fields': ('checkout_request_id', 'merchant_request_id')
        }),
        ('Customer Info', {
            'fields': ('phone_number', 'amount')
        }),
        ('Response', {
            'fields': (
                'response_code', 'response_description',
                'mpesa_receipt_number', 'transaction_date'
            )
        }),
        ('Status', {
            'fields': ('status',)
        }),
        ('Raw Response', {
            'fields': ('raw_response',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(PaymentLog)
class PaymentLogAdmin(admin.ModelAdmin):
    """Payment log admin"""
    
    list_display = ('payment', 'level', 'message', 'created_at')
    list_filter = ('level', 'created_at')
    search_fields = ('payment__order__order_id', 'message')
    readonly_fields = ('created_at', 'payment', 'level', 'message', 'data')
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Payment', {
            'fields': ('payment',)
        }),
        ('Log Entry', {
            'fields': ('level', 'message', 'data')
        }),
        ('Timestamp', {
            'fields': ('created_at',)
        }),
    )
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False