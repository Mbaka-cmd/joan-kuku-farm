# API Versioning Strategy - Multiple Version Support

from rest_framework.versioning import URLPathVersioning, AcceptHeaderVersioning, NamespaceVersioning
from rest_framework import viewsets, serializers, status
from rest_framework.decorators import api_view, versioning_classes
from rest_framework.response import Response

# ============================================================
# VERSIONING STRATEGIES
# ============================================================

class URLPathVersioningStrategy(URLPathVersioning):
    """
    API versioning via URL path
    Example: /api/v1/products/, /api/v2/products/
    """
    default_version = 'v1'
    allowed_versions = ['v1', 'v2', 'v3']
    version_param = 'version'


class HeaderVersioningStrategy(AcceptHeaderVersioning):
    """
    API versioning via Accept header
    Example: Accept: application/json; version=1.0
    """
    default_version = '1.0'
    allowed_versions = ['1.0', '2.0', '3.0']


class NamespaceVersioningStrategy(NamespaceVersioning):
    """
    API versioning via URL namespace
    Example: /api/v1/, /api/v2/
    """
    default_version = 'v1'
    allowed_versions = ['v1', 'v2', 'v3']


# ============================================================
# V1 API (CURRENT)
# ============================================================

class ProductSerializerV1(serializers.Serializer):
    """Product serializer for API v1"""
    id = serializers.IntegerField()
    name = serializers.CharField(max_length=255)
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    stock = serializers.IntegerField()
    description = serializers.CharField()


class OrderSerializerV1(serializers.Serializer):
    """Order serializer for API v1"""
    id = serializers.IntegerField()
    order_id = serializers.CharField()
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    status = serializers.CharField()
    created_at = serializers.DateTimeField()


# ============================================================
# V2 API (ENHANCED)
# ============================================================

class ProductSerializerV2(serializers.Serializer):
    """
    Enhanced product serializer for API v2
    - Added: category, ratings, availability
    - Removed: raw stock number (now availability status)
    """
    id = serializers.IntegerField()
    name = serializers.CharField(max_length=255)
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    
    # New fields in V2
    category = serializers.SerializerMethodField()
    average_rating = serializers.DecimalField(max_digits=3, decimal_places=2)
    review_count = serializers.IntegerField()
    availability = serializers.SerializerMethodField()
    
    description = serializers.CharField()
    image_url = serializers.SerializerMethodField()
    
    def get_category(self, obj):
        return {'id': obj.category.id, 'name': obj.category.name}
    
    def get_availability(self, obj):
        return 'in_stock' if obj.stock > 0 else 'out_of_stock'
    
    def get_image_url(self, obj):
        request = self.context.get('request')
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        return None


class OrderSerializerV2(serializers.Serializer):
    """
    Enhanced order serializer for API v2
    - Added: items detail, tracking, estimated delivery
    - Changed: status now includes more info
    """
    id = serializers.IntegerField()
    order_id = serializers.CharField()
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    
    # Enhanced status in V2
    status = serializers.DictField()
    status_history = serializers.ListField()
    
    items = serializers.ListField()
    tracking_number = serializers.CharField(allow_null=True)
    estimated_delivery_date = serializers.DateField()
    
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


# ============================================================
# V3 API (LATEST - BREAKING CHANGES)
# ============================================================

class ProductSerializerV3(serializers.Serializer):
    """
    Product serializer for API v3
    - Completely redesigned API
    - New structure for better organization
    """
    id = serializers.IntegerField()
    
    # Core info
    basic = serializers.SerializerMethodField()
    
    # Pricing
    pricing = serializers.SerializerMethodField()
    
    # Availability
    availability = serializers.SerializerMethodField()
    
    # Metadata
    metadata = serializers.SerializerMethodField()
    
    def get_basic(self, obj):
        return {
            'name': obj.name,
            'description': obj.description,
            'sku': obj.SKU,
            'category_id': obj.category.id,
            'category_name': obj.category.name,
        }
    
    def get_pricing(self, obj):
        return {
            'amount': float(obj.price),
            'currency': 'KES',
            'discounted': False,
            'discount_percentage': 0,
        }
    
    def get_availability(self, obj):
        return {
            'in_stock': obj.stock > 0,
            'quantity': obj.stock,
            'status': 'in_stock' if obj.stock > 0 else 'out_of_stock',
        }
    
    def get_metadata(self, obj):
        return {
            'created_at': obj.created_at.isoformat(),
            'updated_at': obj.updated_at.isoformat(),
            'is_featured': obj.is_featured,
            'is_active': obj.is_active,
        }


# ============================================================
# VERSIONED VIEWSETS
# ============================================================

class VersionedProductViewSet(viewsets.ViewSet):
    """Product viewset with version support"""
    
    def get_serializer(self, version):
        """Get appropriate serializer based on API version"""
        serializers_map = {
            'v1': ProductSerializerV1,
            'v2': ProductSerializerV2,
            'v3': ProductSerializerV3,
        }
        return serializers_map.get(version, ProductSerializerV1)
    
    def list(self, request, version=None):
        """List products with version-appropriate response"""
        # Fetch products
        from apps.products.models import Product
        products = Product.objects.filter(is_active=True)[:10]
        
        # Get serializer for version
        serializer_class = self.get_serializer(version or 'v1')
        serializer = serializer_class(products, many=True, context={'request': request})
        
        # Format response based on version
        if version == 'v3':
            return Response({
                'data': serializer.data,
                'pagination': {
                    'total': len(products),
                    'page': 1,
                    'per_page': 10,
                }
            })
        else:
            return Response({
                'results': serializer.data,
                'count': len(products),
            })


# ============================================================
# VERSION-SPECIFIC ENDPOINTS
# ============================================================

@api_view(['GET'])
def api_v1_docs(request):
    """Documentation for API v1"""
    return Response({
        'version': 'v1',
        'status': 'stable',
        'endpoints': {
            'products': '/api/v1/products/',
            'orders': '/api/v1/orders/',
            'payments': '/api/v1/payments/',
        },
        'changes': [],
        'deprecation_notice': None,
    })


@api_view(['GET'])
def api_v2_docs(request):
    """Documentation for API v2"""
    return Response({
        'version': 'v2',
        'status': 'stable',
        'endpoints': {
            'products': '/api/v2/products/',
            'orders': '/api/v2/orders/',
            'payments': '/api/v2/payments/',
        },
        'changes': [
            'Products now include ratings and reviews',
            'Orders include estimated delivery dates',
            'New availability status instead of raw stock',
        ],
        'deprecation_notice': None,
    })


@api_view(['GET'])
def api_v3_docs(request):
    """Documentation for API v3"""
    return Response({
        'version': 'v3',
        'status': 'beta',
        'endpoints': {
            'products': '/api/v3/products/',
            'orders': '/api/v3/orders/',
            'payments': '/api/v3/payments/',
        },
        'changes': [
            'Complete API redesign with better organization',
            'Response grouped by: basic, pricing, availability, metadata',
            'New structured approach to data',
        ],
        'deprecation_notice': 'v1 will be deprecated on 2025-01-01',
    })


# ============================================================
# MIGRATION GUIDE
# ============================================================

"""
API VERSIONING MIGRATION GUIDE

1. URL-Based Versioning (Recommended):
   - /api/v1/products/
   - /api/v2/products/
   - /api/v3/products/
   
   Settings.py:
   REST_FRAMEWORK = {
       'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.URLPathVersioning',
   }

2. Header-Based Versioning:
   - Accept: application/json; version=1.0
   
   Settings.py:
   REST_FRAMEWORK = {
       'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.AcceptHeaderVersioning',
   }

3. Namespace Versioning:
   - urls.py includes:
       path('v1/', include(v1_urls)),
       path('v2/', include(v2_urls)),

MIGRATION PATH:
- v1: Current production (stable)
- v2: New features (6 month support)
- v3: Breaking changes (beta, 1 year support)
- v1 deprecated: After 2-year support period

BREAKING CHANGES:
v1 → v2:
  - product.stock → product.availability
  - response format changes
  - new required fields

v2 → v3:
  - Complete API restructuring
  - Grouped responses (basic, pricing, availability)
  - All fields reorganized

DEPRECATION TIMELINE:
- v1: Deprecated 2025-01-01, removed 2025-01-01
- v2: Deprecated 2026-01-01, removed 2027-01-01
- v3: Current stable version

CLIENT MIGRATION STEPS:
1. Monitor deprecation notices
2. Update API endpoints in code
3. Update request/response parsing
4. Test thoroughly before production
5. Update to new version
"""

# ============================================================
# VERSION DETECTION MIDDLEWARE
# ============================================================

from django.utils.deprecation import MiddlewareMixin
import logging

logger = logging.getLogger('api')

class APIVersionLoggingMiddleware(MiddlewareMixin):
    """Log API version usage for monitoring"""
    
    def process_request(self, request):
        # Extract version from URL or header
        version = self.get_api_version(request)
        request.api_version = version
        
        # Log version usage
        logger.info(
            f'API {version} request: {request.method} {request.path}',
            extra={'api_version': version}
        )
        
        return None
    
    @staticmethod
    def get_api_version(request):
        """Extract API version from request"""
        # From URL: /api/v1/...
        path_parts = request.path.split('/')
        for part in path_parts:
            if part.startswith('v') and part[1:].isdigit():
                return part
        
        # From header
        version = request.META.get('HTTP_ACCEPT_VERSION')
        if version:
            return version
        
        return 'unknown'


# ============================================================
# SUNSET HEADERS
# ============================================================

"""
Add sunset headers to deprecated API versions:

class DeprecatedAPIMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        # Add sunset headers for deprecated versions
        if hasattr(request, 'api_version'):
            if request.api_version == 'v1':
                response['Sunset'] = 'Sun, 01 Jan 2025 00:00:00 GMT'
                response['Deprecation'] = 'true'
                response['Warning'] = '299 - "API version v1 is deprecated"'
        
        return response
"""