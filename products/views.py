from rest_framework import viewsets, status, generics, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend
import logging

from .models import Category, Product, ProductReview, PriceHistory
from .serializers import (
    CategorySerializer,
    CategoryDetailSerializer,
    ProductListSerializer,
    ProductDetailSerializer,
    ProductCreateUpdateSerializer,
    ProductStockUpdateSerializer,
    ProductReviewSerializer,
)
from .filters import ProductFilter, ProductSearchFilter, ProductOrderingFilter
from .permissions import IsAdminOrReadOnly, IsProductAdmin

logger = logging.getLogger(__name__)


class CategoryViewSet(viewsets.ModelViewSet):
    """
    Category ViewSet
    GET /api/products/categories/ - List all categories
    POST /api/products/categories/ - Create category (admin)
    GET /api/products/categories/<id>/ - Get category details
    """
    queryset = Category.objects.all()
    permission_classes = [IsAdminOrReadOnly]
    lookup_field = 'id'
    
    def get_serializer_class(self):
        """Use different serializer for detail vs list"""
        if self.action == 'retrieve':
            return CategoryDetailSerializer
        return CategorySerializer
    
    @action(detail=True, methods=['get'])
    def products(self, request, pk=None):
        """Get all products in a category"""
        category = self.get_object()
        products = category.products.filter(is_active=True)
        serializer = ProductListSerializer(products, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get only active categories with products"""
        categories = Category.objects.filter(products__is_active=True).distinct()
        serializer = CategorySerializer(categories, many=True)
        return Response(serializer.data)


class ProductViewSet(viewsets.ModelViewSet):
    """
    Product ViewSet
    GET /api/products/ - List all products
    POST /api/products/ - Create product (admin)
    GET /api/products/<id>/ - Get product details
    PUT /api/products/<id>/ - Update product (admin)
    DELETE /api/products/<id>/ - Delete product (admin)
    """
    queryset = Product.objects.filter(is_active=True)
    permission_classes = [IsAdminOrReadOnly]
    lookup_field = 'id'
    
    filter_backends = [
        DjangoFilterBackend,
        ProductSearchFilter,
        ProductOrderingFilter
    ]
    filterset_class = ProductFilter
    search_fields = ['name', 'description', 'SKU', 'category__name']
    ordering_fields = ['price', 'created_at', 'stock', 'name']
    ordering = ['-created_at']
    
    pagination_class = None  # Can be configured in settings
    
    def get_serializer_class(self):
        """Use different serializer based on action"""
        if self.action == 'retrieve':
            return ProductDetailSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return ProductCreateUpdateSerializer
        elif self.action == 'update_stock':
            return ProductStockUpdateSerializer
        return ProductListSerializer
    
    def get_queryset(self):
        """Filter queryset based on user permission"""
        if self.request.user.is_staff:
            # Admins see all products including inactive
            return Product.objects.all()
        return Product.objects.filter(is_active=True)
    
    def create(self, request, *args, **kwargs):
        """Create new product (admin only)"""
        if not request.user.is_staff:
            return Response({
                'error': 'Admin access required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        return super().create(request, *args, **kwargs)
    
    @action(detail=True, methods=['get'])
    def reviews(self, request, pk=None):
        """Get reviews for a product"""
        product = self.get_object()
        reviews = product.reviews.filter(is_approved=True).order_by('-created_at')
        serializer = ProductReviewSerializer(reviews, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def price_history(self, request, pk=None):
        """Get price history for a product"""
        product = self.get_object()
        history = product.price_history.all()[:10]
        data = [{
            'old_price': str(h.old_price),
            'new_price': str(h.new_price),
            'reason': h.reason,
            'created_at': h.created_at
        } for h in history]
        return Response(data)
    
    @action(detail=True, methods=['post'])
    def update_stock(self, request, pk=None):
        """Update product stock (admin only)"""
        if not request.user.is_staff:
            return Response({
                'error': 'Admin access required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        product = self.get_object()
        new_stock = request.data.get('stock')
        min_stock = request.data.get('min_stock')
        
        if new_stock is None and min_stock is None:
            return Response({
                'error': 'stock or min_stock is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if new_stock is not None:
            old_stock = product.stock
            product.stock = new_stock
            
            # Create price history log if reason provided
            reason = request.data.get('reason', 'Stock adjustment')
            logger.info(f"Stock updated for {product.name}: {old_stock} → {new_stock}")
        
        if min_stock is not None:
            product.min_stock = min_stock
        
        product.save()
        
        return Response({
            'product': ProductDetailSerializer(product).data,
            'message': 'Stock updated successfully'
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def change_price(self, request, pk=None):
        """Change product price (admin only)"""
        if not request.user.is_staff:
            return Response({
                'error': 'Admin access required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        product = self.get_object()
        new_price = request.data.get('price')
        reason = request.data.get('reason', 'Price adjustment')
        
        if not new_price:
            return Response({
                'error': 'price is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            new_price = float(new_price)
            if new_price <= 0:
                raise ValueError("Price must be positive")
            
            # Record price history
            PriceHistory.objects.create(
                product=product,
                old_price=product.price,
                new_price=new_price,
                reason=reason
            )
            
            product.price = new_price
            product.save()
            
            logger.info(f"Price changed for {product.name}: {product.price} → {new_price}")
            
            return Response({
                'product': ProductDetailSerializer(product).data,
                'message': 'Price updated successfully'
            }, status=status.HTTP_200_OK)
        
        except (ValueError, TypeError):
            return Response({
                'error': 'Invalid price format'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def set_featured(self, request, pk=None):
        """Mark product as featured (admin only)"""
        if not request.user.is_staff:
            return Response({
                'error': 'Admin access required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        product = self.get_object()
        is_featured = request.data.get('is_featured', True)
        
        product.is_featured = is_featured
        product.save()
        
        return Response({
            'product': ProductDetailSerializer(product).data,
            'message': f"Product {'marked as' if is_featured else 'removed from'} featured"
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None):
        """Activate/Deactivate product (admin only)"""
        if not request.user.is_staff:
            return Response({
                'error': 'Admin access required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        product = self.get_object()
        product.is_active = not product.is_active
        product.save()
        
        return Response({
            'product': ProductDetailSerializer(product).data,
            'message': f"Product {'activated' if product.is_active else 'deactivated'}"
        }, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def featured(self, request):
        """Get featured products"""
        products = Product.objects.filter(is_active=True, is_featured=True)
        serializer = ProductListSerializer(products, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        """Get low stock products (admin only)"""
        if not request.user.is_staff:
            return Response({
                'error': 'Admin access required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        products = Product.objects.filter(
            is_active=True,
            stock__lte=10
        )
        serializer = ProductListSerializer(products, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def trending(self, request):
        """Get trending products (most ordered)"""
        from django.db.models import Count
        from apps.orders.models import OrderItem
        
        trending_products = Product.objects.annotate(
            order_count=Count('orderitem')
        ).filter(
            is_active=True,
            order_count__gt=0
        ).order_by('-order_count')[:10]
        
        serializer = ProductListSerializer(trending_products, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def top_rated(self, request):
        """Get top-rated products"""
        from django.db.models import Avg
        
        top_products = Product.objects.annotate(
            avg_rating=Avg('reviews__rating')
        ).filter(
            is_active=True,
            reviews__is_approved=True
        ).order_by('-avg_rating')[:10]
        
        serializer = ProductListSerializer(top_products, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def bulk_import(self, request):
        """Bulk import products from CSV/JSON (admin only)"""
        if not request.user.is_staff:
            return Response({
                'error': 'Admin access required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        file = request.FILES.get('file')
        
        if not file:
            return Response({
                'error': 'File is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            import csv
            import json
            
            file_name = file.name.lower()
            products_created = 0
            
            if file_name.endswith('.csv'):
                # Parse CSV
                decoded = file.read().decode('utf-8').splitlines()
                reader = csv.DictReader(decoded)
                
                for row in reader:
                    category, _ = Category.objects.get_or_create(
                        name=row.get('category', 'Uncategorized')
                    )
                    
                    Product.objects.create(
                        SKU=row.get('sku'),
                        name=row.get('name'),
                        description=row.get('description', ''),
                        category=category,
                        price=float(row.get('price', 0)),
                        unit=row.get('unit', 'per unit'),
                        stock=int(row.get('stock', 0)),
                        is_vaccinated=row.get('is_vaccinated', 'false').lower() == 'true'
                    )
                    products_created += 1
            
            elif file_name.endswith('.json'):
                # Parse JSON
                data = json.loads(file.read().decode('utf-8'))
                
                for item in data:
                    category, _ = Category.objects.get_or_create(
                        name=item.get('category', 'Uncategorized')
                    )
                    
                    Product.objects.create(
                        SKU=item.get('sku'),
                        name=item.get('name'),
                        description=item.get('description', ''),
                        category=category,
                        price=float(item.get('price', 0)),
                        unit=item.get('unit', 'per unit'),
                        stock=int(item.get('stock', 0)),
                        is_vaccinated=item.get('is_vaccinated', False)
                    )
                    products_created += 1
            
            else:
                return Response({
                    'error': 'File must be CSV or JSON'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            return Response({
                'message': f'{products_created} products imported successfully'
            }, status=status.HTTP_201_CREATED)
        
        except Exception as e:
            logger.error(f"Bulk import error: {str(e)}")
            return Response({
                'error': f'Import failed: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)


class ProductReviewViewSet(viewsets.ModelViewSet):
    """
    Product Review ViewSet
    GET /api/products/reviews/ - List all reviews
    POST /api/products/reviews/ - Create review
    GET /api/products/reviews/<id>/ - Get review details
    """
    queryset = ProductReview.objects.filter(is_approved=True)
    serializer_class = ProductReviewSerializer
    permission_classes = [AllowAny]
    lookup_field = 'id'
    
    def get_queryset(self):
        """Filter reviews based on permissions"""
        if self.request.user.is_staff:
            return ProductReview.objects.all()
        return ProductReview.objects.filter(is_approved=True)
    
    def create(self, request, *args, **kwargs):
        """Create product review (authenticated users)"""
        if not request.user.is_authenticated:
            return Response({
                'error': 'Authentication required to post review'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        product_id = request.data.get('product')
        
        # Check if user already reviewed this product
        if ProductReview.objects.filter(
            product_id=product_id,
            user=request.user
        ).exists():
            return Response({
                'error': 'You have already reviewed this product'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if user has purchased this product
        from apps.orders.models import Order
        has_purchased = Order.objects.filter(
            customer=request.user,
            is_paid=True,
            items__product_id=product_id
        ).exists()
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        review = serializer.save(
            user=request.user,
            is_verified_purchase=has_purchased
        )
        
        return Response(
            ProductReviewSerializer(review).data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve review (admin only)"""
        if not request.user.is_staff:
            return Response({
                'error': 'Admin access required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        review = self.get_object()
        review.is_approved = True
        review.save()
        
        return Response({
            'review': ProductReviewSerializer(review).data,
            'message': 'Review approved'
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def mark_helpful(self, request, pk=None):
        """Mark review as helpful"""
        review = self.get_object()
        review.helpful_count += 1
        review.save()
        
        return Response({
            'helpful_count': review.helpful_count,
            'message': 'Marked as helpful'
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def mark_unhelpful(self, request, pk=None):
        """Mark review as unhelpful"""
        review = self.get_object()
        review.unhelpful_count += 1
        review.save()
        
        return Response({
            'unhelpful_count': review.unhelpful_count,
            'message': 'Marked as unhelpful'
        }, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def pending_approval(self, request):
        """Get reviews pending approval (admin only)"""
        if not request.user.is_staff:
            return Response({
                'error': 'Admin access required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        reviews = ProductReview.objects.filter(is_approved=False)
        serializer = ProductReviewSerializer(reviews, many=True)
        return Response(serializer.data)