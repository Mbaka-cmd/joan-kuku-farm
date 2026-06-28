from rest_framework import serializers
from .models import Category, Product, ProductReview, PriceHistory


class CategorySerializer(serializers.ModelSerializer):
    """Category serializer with product count"""
    product_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description', 'image', 'product_count']
    
    def get_product_count(self, obj):
        return obj.get_product_count()


class CategoryDetailSerializer(serializers.ModelSerializer):
    """Detailed category with products"""
    products = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description', 'image', 'products']
    
    def get_products(self, obj):
        """Get active products in category"""
        products = obj.products.filter(is_active=True)
        return ProductListSerializer(products, many=True).data


class PriceHistorySerializer(serializers.ModelSerializer):
    """Price history serializer"""
    
    class Meta:
        model = PriceHistory
        fields = ['old_price', 'new_price', 'reason', 'created_at']
        read_only_fields = fields


class ProductReviewSerializer(serializers.ModelSerializer):
    """Product review serializer"""
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    rating_display = serializers.CharField(source='get_rating_display', read_only=True)
    
    class Meta:
        model = ProductReview
        fields = [
            'id', 'rating', 'rating_display', 'title', 'comment',
            'user_name', 'is_verified_purchase', 'helpful_count',
            'unhelpful_count', 'created_at'
        ]
        read_only_fields = [
            'id', 'user_name', 'rating_display', 'helpful_count',
            'unhelpful_count', 'created_at'
        ]


class ProductListSerializer(serializers.ModelSerializer):
    """Product list serializer (summary)"""
    category_name = serializers.CharField(source='category.name', read_only=True)
    available_stock = serializers.SerializerMethodField()
    is_low_stock = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = [
            'id', 'SKU', 'name', 'slug', 'price', 'unit',
            'category_name', 'is_featured', 'is_vaccinated',
            'image', 'available_stock', 'is_low_stock',
            'average_rating', 'review_count', 'is_active'
        ]
    
    def get_available_stock(self, obj):
        return obj.get_available_stock()
    
    def get_is_low_stock(self, obj):
        return obj.is_low_stock()
    
    def get_average_rating(self, obj):
        reviews = obj.reviews.filter(is_approved=True)
        if not reviews.exists():
            return 0
        return reviews.aggregate(
            models.Avg('rating')
        )['rating__avg'] or 0
    
    def get_review_count(self, obj):
        return obj.reviews.filter(is_approved=True).count()


class ProductDetailSerializer(serializers.ModelSerializer):
    """Detailed product serializer with reviews and history"""
    category = CategorySerializer(read_only=True)
    reviews = ProductReviewSerializer(many=True, read_only=True)
    price_history = serializers.SerializerMethodField()
    available_stock = serializers.SerializerMethodField()
    is_low_stock = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    can_order = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = [
            'id', 'SKU', 'name', 'slug', 'description', 'description_long',
            'price', 'unit', 'category', 'is_vaccinated', 'specifications',
            'image', 'images', 'available_stock', 'is_low_stock',
            'average_rating', 'review_count', 'reviews',
            'price_history', 'can_order', 'is_featured', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'SKU', 'created_at', 'updated_at', 'reviews',
            'available_stock', 'is_low_stock', 'average_rating',
            'review_count', 'price_history', 'can_order'
        ]
    
    def get_available_stock(self, obj):
        return obj.get_available_stock()
    
    def get_is_low_stock(self, obj):
        return obj.is_low_stock()
    
    def get_average_rating(self, obj):
        from django.db import models
        reviews = obj.reviews.filter(is_approved=True)
        if not reviews.exists():
            return 0
        return float(reviews.aggregate(
            models.Avg('rating')
        )['rating__avg'] or 0)
    
    def get_review_count(self, obj):
        return obj.reviews.filter(is_approved=True).count()
    
    def get_price_history(self, obj):
        """Get last 5 price changes"""
        history = obj.price_history.all()[:5]
        return PriceHistorySerializer(history, many=True).data
    
    def get_can_order(self, obj):
        """Check if product can be ordered"""
        return obj.get_available_stock() > 0


class ProductCreateUpdateSerializer(serializers.ModelSerializer):
    """Create/update product (admin only)"""
    
    class Meta:
        model = Product
        fields = [
            'SKU', 'name', 'slug', 'description', 'description_long',
            'price', 'unit', 'category', 'stock', 'min_stock',
            'is_vaccinated', 'specifications', 'image', 'images',
            'is_active', 'is_featured'
        ]
    
    def validate_SKU(self, value):
        """Check SKU uniqueness"""
        instance = self.instance
        if instance:
            # Update - exclude current product
            if Product.objects.filter(SKU=value).exclude(id=instance.id).exists():
                raise serializers.ValidationError('This SKU already exists')
        else:
            # Create
            if Product.objects.filter(SKU=value).exists():
                raise serializers.ValidationError('This SKU already exists')
        return value
    
    def validate_price(self, value):
        """Validate price is positive"""
        if value <= 0:
            raise serializers.ValidationError('Price must be greater than 0')
        return value


class ProductStockUpdateSerializer(serializers.ModelSerializer):
    """Update product stock"""
    
    class Meta:
        model = Product
        fields = ['stock', 'min_stock']


class BulkProductImportSerializer(serializers.Serializer):
    """Bulk import products from CSV/JSON"""
    file = serializers.FileField()
    
    def validate_file(self, value):
        """Validate file format"""
        allowed_formats = ['csv', 'json']
        file_ext = value.name.split('.')[-1].lower()
        
        if file_ext not in allowed_formats:
            raise serializers.ValidationError(
                f'File must be CSV or JSON. Got {file_ext}'
            )
        return value