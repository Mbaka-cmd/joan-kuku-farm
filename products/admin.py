from django.contrib import admin
from .models import Category, Product, ProductReview, PriceHistory


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Category admin"""
    
    list_display = ('name', 'product_count', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at', 'product_count')
    prepopulated_fields = {'slug': ('name',)}
    
    fieldsets = (
        ('Category Information', {
            'fields': ('name', 'slug', 'description', 'image')
        }),
        ('Statistics', {
            'fields': ('product_count',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """Product admin"""
    
    list_display = (
        'name', 'SKU', 'category', 'price', 'stock',
        'is_low_stock', 'is_vaccinated', 'is_active', 'is_featured'
    )
    list_filter = (
        'category', 'is_active', 'is_featured', 'is_vaccinated',
        'created_at', 'updated_at'
    )
    search_fields = ('name', 'SKU', 'description', 'category__name')
    readonly_fields = (
        'created_at', 'updated_at', 'get_available_stock',
        'get_review_count', 'get_average_rating'
    )
    prepopulated_fields = {'slug': ('name',)}
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('SKU', 'name', 'slug', 'category')
        }),
        ('Description', {
            'fields': ('description', 'description_long')
        }),
        ('Pricing', {
            'fields': ('price', 'unit')
        }),
        ('Inventory', {
            'fields': ('stock', 'min_stock', 'reserved_quantity', 'get_available_stock')
        }),
        ('Product Details', {
            'fields': ('is_vaccinated', 'specifications')
        }),
        ('Media', {
            'fields': ('image', 'images')
        }),
        ('Status', {
            'fields': ('is_active', 'is_featured')
        }),
        ('Reviews & Ratings', {
            'fields': ('get_review_count', 'get_average_rating'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    actions = ['activate_products', 'deactivate_products', 'mark_as_featured']
    
    def get_available_stock(self, obj):
        return f"{obj.get_available_stock()} units"
    get_available_stock.short_description = 'Available Stock'
    
    def get_review_count(self, obj):
        return obj.reviews.filter(is_approved=True).count()
    get_review_count.short_description = 'Approved Reviews'
    
    def get_average_rating(self, obj):
        from django.db.models import Avg
        avg = obj.reviews.filter(is_approved=True).aggregate(
            Avg('rating')
        )['rating__avg']
        return f"{avg:.1f} ★" if avg else "No ratings"
    get_average_rating.short_description = 'Average Rating'
    
    def activate_products(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} products activated')
    activate_products.short_description = 'Activate selected products'
    
    def deactivate_products(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} products deactivated')
    deactivate_products.short_description = 'Deactivate selected products'
    
    def mark_as_featured(self, request, queryset):
        updated = queryset.update(is_featured=True)
        self.message_user(request, f'{updated} products marked as featured')
    mark_as_featured.short_description = 'Mark selected as featured'


@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    """Product review admin"""
    
    list_display = (
        'product', 'user', 'rating', 'is_verified_purchase',
        'is_approved', 'helpful_count', 'created_at'
    )
    list_filter = (
        'rating', 'is_approved', 'is_verified_purchase', 'created_at'
    )
    search_fields = ('product__name', 'user__username', 'title', 'comment')
    readonly_fields = ('created_at', 'updated_at', 'helpful_count', 'unhelpful_count')
    
    fieldsets = (
        ('Review Information', {
            'fields': ('product', 'user', 'rating', 'title', 'comment')
        }),
        ('Verification', {
            'fields': ('is_verified_purchase',)
        }),
        ('Moderation', {
            'fields': ('is_approved',)
        }),
        ('Engagement', {
            'fields': ('helpful_count', 'unhelpful_count')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    actions = ['approve_reviews', 'reject_reviews']
    
    def approve_reviews(self, request, queryset):
        updated = queryset.update(is_approved=True)
        self.message_user(request, f'{updated} reviews approved')
    approve_reviews.short_description = 'Approve selected reviews'
    
    def reject_reviews(self, request, queryset):
        updated = queryset.update(is_approved=False)
        self.message_user(request, f'{updated} reviews rejected')
    reject_reviews.short_description = 'Reject selected reviews'


@admin.register(PriceHistory)
class PriceHistoryAdmin(admin.ModelAdmin):
    """Price history admin"""
    
    list_display = (
        'product', 'old_price', 'new_price', 'reason', 'created_at'
    )
    list_filter = ('product__category', 'created_at')
    search_fields = ('product__name', 'reason')
    readonly_fields = ('created_at', 'product')
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Product', {
            'fields': ('product',)
        }),
        ('Price Change', {
            'fields': ('old_price', 'new_price', 'reason')
        }),
        ('Timestamp', {
            'fields': ('created_at',)
        }),
    )