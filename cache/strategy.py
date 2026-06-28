# Advanced Caching Strategy for Joan Kuku Farm

from django.core.cache import cache
from django.views.decorators.cache import cache_page
from rest_framework.decorators import api_view
from rest_framework.response import Response
from functools import wraps
import json
import hashlib

# Cache key patterns
CACHE_KEYS = {
    'products_list': 'products:list:{page}:{search}:{category}',
    'product_detail': 'product:{id}',
    'product_reviews': 'product:{id}:reviews',
    'orders_list': 'orders:{user_id}:{status}',
    'order_detail': 'order:{id}',
    'analytics_dashboard': 'analytics:dashboard:{period}',
    'revenue_analytics': 'analytics:revenue:{period}',
    'user_profile': 'user:{id}:profile',
    'featured_products': 'products:featured',
    'trending_products': 'products:trending',
    'low_stock_products': 'products:low_stock',
}

# Cache TTL (Time To Live) in seconds
CACHE_TTL = {
    'products_list': 300,  # 5 minutes
    'product_detail': 600,  # 10 minutes
    'product_reviews': 600,  # 10 minutes
    'orders_list': 60,  # 1 minute
    'order_detail': 60,  # 1 minute
    'analytics_dashboard': 3600,  # 1 hour
    'featured_products': 1800,  # 30 minutes
    'trending_products': 1800,  # 30 minutes
    'low_stock_products': 300,  # 5 minutes
    'user_profile': 1800,  # 30 minutes
}

# ============================================================
# CACHE DECORATORS
# ============================================================

def cache_response(key_pattern: str, ttl: int = 300):
    """
    Decorator to cache API responses
    
    Usage:
        @cache_response('products:list:{page}', ttl=300)
        def get_products(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Generate cache key from pattern
            params = {**request.query_params, **kwargs}
            cache_key = key_pattern.format(**params)
            
            # Try to get from cache
            cached_response = cache.get(cache_key)
            if cached_response is not None:
                return Response(cached_response)
            
            # Get fresh response
            response = view_func(request, *args, **kwargs)
            
            # Cache the response data
            if response.status_code == 200:
                cache.set(cache_key, response.data, ttl)
            
            return response
        
        return wrapper
    return decorator


def cache_with_user(key_pattern: str, ttl: int = 300):
    """Cache response per user"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user_id = request.user.id if request.user.is_authenticated else 'anonymous'
            cache_key = f"{key_pattern}:user:{user_id}"
            
            cached = cache.get(cache_key)
            if cached:
                return Response(cached)
            
            response = view_func(request, *args, **kwargs)
            if response.status_code == 200:
                cache.set(cache_key, response.data, ttl)
            
            return response
        return wrapper
    return decorator


def conditional_cache(key_pattern: str, ttl: int = 300, condition=None):
    """Cache with conditional logic"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            should_cache = condition(request) if condition else True
            
            if should_cache:
                cache_key = key_pattern.format(**request.query_params)
                cached = cache.get(cache_key)
                if cached:
                    return Response(cached)
            
            response = view_func(request, *args, **kwargs)
            
            if should_cache and response.status_code == 200:
                cache.set(cache_key, response.data, ttl)
            
            return response
        return wrapper
    return decorator

# ============================================================
# CACHE INVALIDATION
# ============================================================

def invalidate_product_cache(product_id: int):
    """Invalidate product-related caches when product changes"""
    cache.delete(f'product:{product_id}')
    cache.delete(f'product:{product_id}:reviews')
    cache.delete('products:featured')
    cache.delete('products:trending')
    cache.delete('products:low_stock')
    # Invalidate paginated lists
    for i in range(1, 10):
        cache.delete(f'products:list:{i}:*')


def invalidate_order_cache(user_id: int):
    """Invalidate order caches when order is placed/updated"""
    # Delete all order caches for this user
    for status in ['pending', 'confirmed', 'processing', 'in_transit', 'delivered', 'cancelled']:
        cache.delete(f'orders:{user_id}:{status}')


def invalidate_analytics_cache():
    """Invalidate analytics caches"""
    for period in ['today', 'week', 'month', 'year']:
        cache.delete(f'analytics:dashboard:{period}')
        cache.delete(f'analytics:revenue:{period}')


def clear_all_caches():
    """Emergency: clear all caches"""
    cache.clear()

# ============================================================
# CACHE IMPLEMENTATION EXAMPLES
# ============================================================

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated

@api_view(['GET'])
@permission_classes([AllowAny])
@cache_response('products:list:{page}', ttl=300)
def product_list_cached(request):
    """Get products with caching"""
    from apps.products.models import Product
    from apps.products.serializers import ProductListSerializer
    
    page = request.query_params.get('page', 1)
    products = Product.objects.filter(is_active=True)[:20]
    serializer = ProductListSerializer(products, many=True)
    
    return Response({
        'count': products.count(),
        'results': serializer.data
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def product_detail_cached(request, pk):
    """Get product detail with caching"""
    from apps.products.models import Product
    from apps.products.serializers import ProductDetailSerializer
    
    cache_key = f'product:{pk}'
    cached = cache.get(cache_key)
    
    if cached:
        return Response(cached)
    
    try:
        product = Product.objects.get(pk=pk)
        serializer = ProductDetailSerializer(product)
        cache.set(cache_key, serializer.data, CACHE_TTL['product_detail'])
        return Response(serializer.data)
    except Product.DoesNotExist:
        return Response({'error': 'Product not found'}, status=404)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@cache_with_user('orders:list', ttl=60)
def user_orders_cached(request):
    """Get user orders with per-user caching"""
    from apps.orders.models import Order
    from apps.orders.serializers import OrderListSerializer
    
    orders = Order.objects.filter(customer=request.user).order_by('-created_at')
    serializer = OrderListSerializer(orders, many=True)
    
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([AllowAny])
def analytics_dashboard_cached(request):
    """Get analytics with caching"""
    from apps.analytics.views import get_dashboard_data
    
    period = request.query_params.get('period', 'month')
    cache_key = f'analytics:dashboard:{period}'
    
    cached = cache.get(cache_key)
    if cached:
        return Response(cached)
    
    data = get_dashboard_data(period)
    cache.set(cache_key, data, CACHE_TTL['analytics_dashboard'])
    
    return Response(data)

# ============================================================
# CACHE WARMING (Preload popular data)
# ============================================================

from django.core.management.base import BaseCommand
from django.db.models import Count

def warm_cache():
    """Preload hot data into cache"""
    from apps.products.models import Product
    from apps.products.serializers import ProductListSerializer
    
    print('🔥 Warming up cache...')
    
    # Featured products
    featured = Product.objects.filter(is_featured=True, is_active=True)[:10]
    cache.set('products:featured', ProductListSerializer(featured, many=True).data, 1800)
    print('✅ Featured products cached')
    
    # Trending products
    trending = Product.objects.annotate(
        order_count=Count('orderitem')
    ).order_by('-order_count')[:10]
    cache.set('products:trending', ProductListSerializer(trending, many=True).data, 1800)
    print('✅ Trending products cached')
    
    # Low stock products (for admin)
    low_stock = Product.objects.filter(stock__lt=10)[:20]
    cache.set('products:low_stock', ProductListSerializer(low_stock, many=True).data, 300)
    print('✅ Low stock products cached')
    
    print('✅ Cache warming complete!')


# ============================================================
# CACHE STATS & MONITORING
# ============================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def cache_stats(request):
    """Get cache statistics (admin only)"""
    if not request.user.is_staff:
        return Response({'error': 'Unauthorized'}, status=403)
    
    # Redis info
    try:
        from django.core.cache import cache
        stats = cache.client.get_connection().info()
        
        return Response({
            'redis_version': stats.get('redis_version'),
            'used_memory': stats.get('used_memory_human'),
            'connected_clients': stats.get('connected_clients'),
            'total_commands_processed': stats.get('total_commands_processed'),
            'keyspace_hits': stats.get('keyspace_hits'),
            'keyspace_misses': stats.get('keyspace_misses'),
        })
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def clear_cache(request):
    """Clear all caches (admin only)"""
    if not request.user.is_staff:
        return Response({'error': 'Unauthorized'}, status=403)
    
    pattern = request.data.get('pattern')
    
    if pattern == 'all':
        cache.clear()
        message = 'All caches cleared'
    else:
        # Delete specific pattern
        cache.delete(pattern)
        message = f'Cache cleared: {pattern}'
    
    return Response({'message': message})

# ============================================================
# SETTINGS.PY CONFIGURATION
# ============================================================

"""
Add to settings.py:

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/0'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'PARSER_KWARGS': {'encoding': 'utf8'},
            'POOL_KWARGS': {
                'max_connections': 50,
                'retry_on_timeout': True,
            },
            'CONNECTION_POOL_CLASS_KWARGS': {
                'max_connections': 50,
                'retry_on_timeout': True,
            },
        },
        'KEY_PREFIX': 'jkf',
        'TIMEOUT': 300,  # 5 minutes default
    }
}

# Cache invalidation via Celery
CELERY_BEAT_SCHEDULE = {
    'warm-cache-every-hour': {
        'task': 'apps.cache.tasks.warm_cache',
        'schedule': 3600.0,
    },
    'clear-expired-cache': {
        'task': 'apps.cache.tasks.clear_expired_cache',
        'schedule': 600.0,
    },
}
"""

# ============================================================
# CELERY TASK FOR CACHE WARMING
# ============================================================

"""
Add to apps/cache/tasks.py:

from celery import shared_task
from django.core.cache import cache

@shared_task
def warm_cache():
    # Preload popular data
    from apps.products.models import Product
    from apps.products.serializers import ProductListSerializer
    
    featured = Product.objects.filter(is_featured=True, is_active=True)[:10]
    cache.set('products:featured', ProductListSerializer(featured, many=True).data, 1800)
    
    return 'Cache warmed'

@shared_task
def clear_expired_cache():
    # Clear old cache entries
    cache.clear()
    return 'Expired cache cleared'
"""