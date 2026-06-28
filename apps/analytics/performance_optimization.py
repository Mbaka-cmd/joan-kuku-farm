# Performance Optimization Guide

import time
from functools import wraps
from django.db.models import Prefetch, Q
from django.views.decorators.cache import cache_page
from django.core.paginator import Paginator
import logging

logger = logging.getLogger('performance')

# ============================================================
# PERFORMANCE MONITORING
# ============================================================

class PerformanceMonitor:
    """Monitor application performance"""
    
    @staticmethod
    def measure_time(func):
        """Decorator to measure function execution time"""
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            
            if duration > 1.0:  # Log if over 1 second
                logger.warning(
                    f'Slow function: {func.__name__} took {duration:.2f}s',
                    extra={'function': func.__name__, 'duration': duration}
                )
            
            return result
        return wrapper
    
    @staticmethod
    def log_query_count(view_func):
        """Log database query count"""
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            from django.db import connection, reset_queries
            from django.conf import settings
            
            if settings.DEBUG:
                reset_queries()
            
            response = view_func(request, *args, **kwargs)
            
            if settings.DEBUG:
                logger.debug(
                    f'Query count: {len(connection.queries)} queries',
                    extra={'query_count': len(connection.queries)}
                )
            
            return response
        return wrapper


# ============================================================
# DATABASE QUERY OPTIMIZATION
# ============================================================

class QueryOptimization:
    """Optimize database queries"""
    
    @staticmethod
    def avoid_n_plus_one():
        """
        N+1 Query Problem: Fetching related objects one by one
        
        BAD:
        orders = Order.objects.all()
        for order in orders:
            print(order.customer.name)  # One query per order!
        
        GOOD:
        orders = Order.objects.select_related('customer')
        for order in orders:
            print(order.customer.name)  # One query total
        """
        pass
    
    @staticmethod
    def use_select_related():
        """Use select_related for ForeignKey and OneToOne"""
        from apps.orders.models import Order
        
        # Bad: Multiple queries
        # orders = Order.objects.all()
        
        # Good: Single query with JOIN
        orders = Order.objects.select_related('customer', 'payment')
        return orders
    
    @staticmethod
    def use_prefetch_related():
        """Use prefetch_related for reverse ForeignKey and ManyToMany"""
        from apps.orders.models import Order
        
        # Bad: Multiple queries
        # orders = Order.objects.all()
        # for order in orders:
        #     items = order.orderitem_set.all()
        
        # Good: Two queries total (optimized)
        orders = Order.objects.prefetch_related('orderitem_set')
        return orders
    
    @staticmethod
    def use_only_and_defer():
        """Load only specific fields"""
        from apps.products.models import Product
        
        # Load only name and price (exclude description, image, etc.)
        products = Product.objects.only('id', 'name', 'price', 'stock')
        
        # Defer loading of large fields
        products = Product.objects.defer('description', 'specifications')
        
        return products
    
    @staticmethod
    def use_values_and_values_list():
        """Return dictionaries instead of model instances"""
        from apps.orders.models import Order
        
        # Instead of full Order objects
        orders = Order.objects.values('id', 'order_id', 'total_amount')
        
        # Or as tuples
        orders = Order.objects.values_list('id', 'order_id', flat=False)
        
        return orders
    
    @staticmethod
    def use_aggregation():
        """Use database aggregation"""
        from django.db.models import Sum, Avg, Count
        from apps.orders.models import Order
        
        # Instead of fetching all orders and calculating in Python
        stats = Order.objects.aggregate(
            total_revenue=Sum('total_amount'),
            avg_order_value=Avg('total_amount'),
            total_orders=Count('id'),
        )
        
        return stats
    
    @staticmethod
    def batch_database_operations():
        """Batch write operations"""
        from apps.products.models import Product
        
        # Bad: Multiple saves
        # for product in products:
        #     product.stock -= 1
        #     product.save()  # N queries
        
        # Good: Single bulk update
        Product.objects.filter(stock__gt=0).update(stock=0)
        
        # Bulk create
        products_to_create = [
            Product(name='Product 1', price=100),
            Product(name='Product 2', price=200),
        ]
        Product.objects.bulk_create(products_to_create)


# ============================================================
# CACHING STRATEGIES
# ============================================================

class CachingStrategy:
    """Implement caching at multiple levels"""
    
    @staticmethod
    def query_result_cache():
        """Cache query results"""
        from django.core.cache import cache
        from apps.products.models import Product
        
        cache_key = 'featured_products'
        products = cache.get(cache_key)
        
        if products is None:
            products = Product.objects.filter(is_featured=True)[:10]
            cache.set(cache_key, products, 3600)  # Cache for 1 hour
        
        return products
    
    @staticmethod
    def view_result_cache():
        """Cache entire view response"""
        @cache_page(60 * 5)  # Cache for 5 minutes
        def product_list(request):
            from apps.products.models import Product
            products = Product.objects.all()
            return products
    
    @staticmethod
    def use_cache_warming():
        """Pre-load frequently accessed data"""
        from django.core.cache import cache
        
        # Warm cache on startup
        cache.set('total_products', 1000, None)
        cache.set('total_customers', 500, None)
        cache.set('total_revenue', 50000, None)


# ============================================================
# INDEX OPTIMIZATION
# ============================================================

class IndexOptimization:
    """Database index strategy"""
    
    """
    Add indexes to frequently queried fields:
    
    class Product(models.Model):
        name = models.CharField(max_length=255, db_index=True)
        sku = models.CharField(max_length=50, db_index=True)
        category = models.ForeignKey(Category, db_index=True)
        is_active = models.BooleanField(db_index=True)
        created_at = models.DateTimeField(db_index=True)
        
        class Meta:
            indexes = [
                models.Index(fields=['category', 'is_active']),
                models.Index(fields=['-created_at']),
            ]
    
    CREATE INDEX idx_product_sku ON products(sku);
    CREATE INDEX idx_product_category ON products(category_id);
    CREATE INDEX idx_product_active ON products(is_active);
    CREATE INDEX idx_product_created ON products(created_at DESC);
    CREATE INDEX idx_product_search ON products(name, category_id);
    """
    
    @staticmethod
    def analyze_slow_queries():
        """Analyze slow database queries"""
        from django.db import connection
        from django.test.utils import override_settings
        
        with override_settings(DEBUG=True):
            # Run query
            from apps.orders.models import Order
            orders = Order.objects.all()  # This will be tracked
            
            # Analyze
            for query in connection.queries:
                if query['time'] > 1.0:
                    logger.warning(f"Slow query: {query['sql']}")


# ============================================================
# PAGINATION OPTIMIZATION
# ============================================================

class PaginationOptimization:
    """Optimize paginated queries"""
    
    @staticmethod
    def paginate_efficiently():
        """Paginate large querysets"""
        from apps.products.models import Product
        
        # Bad: Loading all products
        # products = Product.objects.all()
        
        # Good: Paginate
        products = Product.objects.all().order_by('id')
        paginator = Paginator(products, 20)  # 20 per page
        page = paginator.get_page(1)
        
        return page
    
    @staticmethod
    def cursor_based_pagination():
        """Use cursor-based pagination for large datasets"""
        from rest_framework.pagination import CursorPagination
        
        class ProductCursorPagination(CursorPagination):
            page_size = 100
            page_size_query_param = 'page_size'
            max_page_size = 1000
            ordering = '-created_at'
        
        return ProductCursorPagination()


# ============================================================
# API RESPONSE OPTIMIZATION
# ============================================================

class APIResponseOptimization:
    """Optimize API responses"""
    
    @staticmethod
    def minify_json_response():
        """Return only necessary fields"""
        from rest_framework import serializers
        
        class ProductMinimalSerializer(serializers.Serializer):
            """Minimal product data"""
            id = serializers.IntegerField()
            name = serializers.CharField()
            price = serializers.DecimalField(max_digits=10, decimal_places=2)
        
        return ProductMinimalSerializer
    
    @staticmethod
    def compress_response():
        """Use gzip compression"""
        """
        Settings.py:
        
        MIDDLEWARE = [
            'django.middleware.gzip.GZipMiddleware',
            ...
        ]
        
        REST_FRAMEWORK = {
            'DEFAULT_RENDERER_CLASSES': [
                'rest_framework.renderers.JSONRenderer',
            ]
        }
        """
        pass
    
    @staticmethod
    def use_partial_responses():
        """Allow clients to request only needed fields"""
        """
        Usage: /api/products/?fields=id,name,price
        
        class DynamicFieldsSerializer(serializers.ModelSerializer):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                
                request = self.context.get('request')
                if request:
                    fields = request.query_params.get('fields')
                    if fields:
                        allowed = set(fields.split(','))
                        existing = set(self.fields.keys())
                        for field_name in existing - allowed:
                            self.fields.pop(field_name)
        """
        pass


# ============================================================
# FRONTEND OPTIMIZATION
# ============================================================

class FrontendOptimization:
    """Optimize frontend performance"""
    
    """
    1. MINIFY & BUNDLE:
       - Minify CSS, JS
       - Bundle assets
       - Remove unused CSS
    
    2. IMAGE OPTIMIZATION:
       - Use WebP format
       - Lazy load images
       - Responsive images
       - Compress images
    
    3. CACHING:
       - Browser caching (Cache-Control headers)
       - Service workers
       - Local storage
    
    4. CODE SPLITTING:
       - Split by route
       - Load only needed code
       - Async loading
    
    5. CDN:
       - Use CDN for static files
       - CloudFlare
       - AWS CloudFront
    """
    
    @staticmethod
    def set_cache_headers():
        """Set appropriate cache headers"""
        """
        Django settings:
        
        STATIC_URL = '/static/'
        STATIC_ROOT = BASE_DIR / 'staticfiles'
        
        STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'
        
        Add middleware:
        'whitenoise.middleware.WhiteNoiseMiddleware'
        
        Configure WhiteNoise:
        STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
        """
        pass


# ============================================================
# MONITORING & PROFILING
# ============================================================

class PerformanceProfiling:
    """Profile and monitor performance"""
    
    @staticmethod
    def profile_view():
        """Profile view performance"""
        """
        Use django-silk:
        
        pip install django-silk
        
        INSTALLED_APPS = [
            'silk',
        ]
        
        MIDDLEWARE = [
            'silk.middleware.SilkyMiddleware',
        ]
        
        View at: /silk/
        """
        pass
    
    @staticmethod
    def use_new_relic():
        """Monitor with New Relic"""
        """
        pip install newrelic
        
        newrelic-admin run-program python manage.py runserver
        """
        pass
    
    @staticmethod
    def benchmark_endpoints():
        """Benchmark API endpoints"""
        """
        Use Apache Bench:
        
        ab -n 1000 -c 10 http://localhost:8000/api/products/
        
        Or wrk:
        
        wrk -t12 -c400 -d30s http://localhost:8000/api/products/
        """
        pass


# ============================================================
# PERFORMANCE CHECKLIST
# ============================================================

"""
PERFORMANCE OPTIMIZATION CHECKLIST:

Database:
☐ Use select_related() for ForeignKey
☐ Use prefetch_related() for reverse relations
☐ Add database indexes
☐ Use only() and defer() for large fields
☐ Use values() and values_list()
☐ Batch write operations
☐ Use database aggregation
☐ Analyze slow queries
☐ Paginate large querysets

Caching:
☐ Cache frequently accessed data
☐ Use query result caching
☐ Implement view caching
☐ Cache warming on startup
☐ Set appropriate TTLs

API:
☐ Minimize response size
☐ Compress responses (gzip)
☐ Use partial responses
☐ Implement pagination
☐ Add appropriate caching headers

Frontend:
☐ Minify CSS, JS
☐ Bundle assets
☐ Optimize images
☐ Lazy load images
☐ Use CDN
☐ Browser caching
☐ Code splitting

Infrastructure:
☐ Use production database
☐ Configure Redis
☐ Load balancing
☐ CDN for static files
☐ Monitor performance
☐ Profile regularly

Monitoring:
☐ Track response times
☐ Monitor error rates
☐ Track database queries
☐ Monitor memory usage
☐ Set up alerts
☐ Regular performance reviews
"""

# ============================================================
# PERFORMANCE TARGETS
# ============================================================

PERFORMANCE_TARGETS = {
    'api_response_time': 200,  # ms
    'page_load_time': 2000,  # ms
    'database_query_time': 100,  # ms
    'cache_hit_rate': 80,  # %
    'error_rate': 0.1,  # %
    'uptime': 99.9,  # %
}