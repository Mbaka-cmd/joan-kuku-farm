# Advanced Search & Filtering System - Elasticsearch Integration

from django.db import models
from django_filters import rest_framework as filters
from rest_framework import serializers, viewsets
import logging

logger = logging.getLogger('search')

# ============================================================
# SEARCH MODELS
# ============================================================

class SearchQuery(models.Model):
    """Track search queries"""
    query = models.CharField(max_length=255)
    result_count = models.IntegerField(default=0)
    
    # Stats
    clicked_result = models.BooleanField(default=False)
    clicked_product = models.ForeignKey('products.Product', null=True, blank=True, on_delete=models.SET_NULL)
    
    # User info
    user = models.ForeignKey('users.CustomUser', null=True, blank=True, on_delete=models.SET_NULL)
    ip_address = models.GenericIPAddressField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'search_query'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['query']),
            models.Index(fields=['user']),
        ]


class SearchFilter(models.Model):
    """Saved search filters"""
    name = models.CharField(max_length=255)
    user = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE)
    
    # Filter criteria
    filters = models.JSONField(default=dict)
    
    # Stats
    use_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'search_filter'


# ============================================================
# ELASTICSEARCH INTEGRATION
# ============================================================

class ElasticsearchManager:
    """Manage Elasticsearch indexing"""
    
    @staticmethod
    def init_elasticsearch():
        """Initialize Elasticsearch connection"""
        from elasticsearch import Elasticsearch
        
        es = Elasticsearch(['localhost:9200'])
        return es
    
    @staticmethod
    def create_product_index():
        """Create product index"""
        es = ElasticsearchManager.init_elasticsearch()
        
        index_settings = {
            'settings': {
                'number_of_shards': 1,
                'number_of_replicas': 0,
                'analysis': {
                    'analyzer': {
                        'custom_analyzer': {
                            'type': 'standard',
                            'stopwords': '_english_',
                        }
                    }
                }
            },
            'mappings': {
                'properties': {
                    'id': {'type': 'integer'},
                    'name': {
                        'type': 'text',
                        'analyzer': 'custom_analyzer',
                        'fields': {
                            'keyword': {'type': 'keyword'}
                        }
                    },
                    'description': {
                        'type': 'text',
                        'analyzer': 'custom_analyzer',
                    },
                    'price': {'type': 'float'},
                    'category': {'type': 'keyword'},
                    'tags': {'type': 'keyword'},
                    'rating': {'type': 'float'},
                    'stock': {'type': 'integer'},
                    'is_active': {'type': 'boolean'},
                    'created_at': {'type': 'date'},
                }
            }
        }
        
        es.indices.create(index='products', body=index_settings, ignore=400)
    
    @staticmethod
    def index_product(product):
        """Index single product"""
        es = ElasticsearchManager.init_elasticsearch()
        
        doc = {
            'id': product.id,
            'name': product.name,
            'description': product.description,
            'price': float(product.price),
            'category': product.category.name,
            'tags': [tag.name for tag in product.tags.all()],
            'rating': float(product.get_average_rating() or 0),
            'stock': product.stock,
            'is_active': product.is_active,
            'created_at': product.created_at.isoformat(),
        }
        
        es.index(index='products', id=product.id, body=doc)
    
    @staticmethod
    def search_products(query, filters=None):
        """Search products"""
        es = ElasticsearchManager.init_elasticsearch()
        
        # Build query
        search_query = {
            'bool': {
                'must': [
                    {
                        'multi_match': {
                            'query': query,
                            'fields': ['name^2', 'description', 'tags'],
                        }
                    }
                ],
                'filter': []
            }
        }
        
        # Add filters
        if filters:
            if 'category' in filters:
                search_query['bool']['filter'].append({
                    'term': {'category': filters['category']}
                })
            
            if 'min_price' in filters or 'max_price' in filters:
                price_filter = {'range': {'price': {}}}
                if 'min_price' in filters:
                    price_filter['range']['price']['gte'] = filters['min_price']
                if 'max_price' in filters:
                    price_filter['range']['price']['lte'] = filters['max_price']
                search_query['bool']['filter'].append(price_filter)
            
            if 'in_stock' in filters and filters['in_stock']:
                search_query['bool']['filter'].append({
                    'range': {'stock': {'gt': 0}}
                })
            
            if 'min_rating' in filters:
                search_query['bool']['filter'].append({
                    'range': {'rating': {'gte': filters['min_rating']}}
                })
        
        # Execute search
        results = es.search(
            index='products',
            body={
                'query': search_query,
                'size': filters.get('limit', 20) if filters else 20,
                'from': filters.get('offset', 0) if filters else 0,
            }
        )
        
        return results


# ============================================================
# ADVANCED FILTERING
# ============================================================

class ProductFilterSet(filters.FilterSet):
    """Advanced product filters"""
    
    # Text search
    search = filters.CharFilter(field_name='name', lookup_expr='icontains')
    
    # Price range
    min_price = filters.NumberFilter(field_name='price', lookup_expr='gte')
    max_price = filters.NumberFilter(field_name='price', lookup_expr='lte')
    
    # Category
    category = filters.CharFilter(field_name='category__slug', lookup_expr='exact')
    
    # Stock
    in_stock = filters.BooleanFilter(field_name='stock', method='filter_in_stock')
    
    # Rating
    min_rating = filters.NumberFilter(field_name='productreview__rating', lookup_expr='gte')
    
    # Date range
    created_after = filters.DateFilter(field_name='created_at', lookup_expr='gte')
    created_before = filters.DateFilter(field_name='created_at', lookup_expr='lte')
    
    # Sorting
    ordering = filters.OrderingFilter(
        fields=(
            ('price', 'price'),
            ('-price', 'price_desc'),
            ('-created_at', 'newest'),
            ('name', 'name'),
        )
    )
    
    class Meta:
        model = 'products.Product'
        fields = []
    
    def filter_in_stock(self, queryset, name, value):
        if value:
            return queryset.filter(stock__gt=0)
        return queryset


# ============================================================
# AUTOCOMPLETE / SUGGESTIONS
# ============================================================

class SearchSuggestions:
    """Generate search suggestions"""
    
    @staticmethod
    def get_suggestions(query, limit=10):
        """Get search suggestions"""
        from apps.products.models import Product
        from django.db.models import Q
        
        products = Product.objects.filter(
            Q(name__icontains=query) | Q(description__icontains=query),
            is_active=True
        ).values_list('name', flat=True).distinct()[:limit]
        
        return list(products)
    
    @staticmethod
    def get_trending_searches(days=7, limit=10):
        """Get trending search queries"""
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff = timezone.now() - timedelta(days=days)
        
        trending = SearchQuery.objects.filter(
            created_at__gte=cutoff
        ).values('query').annotate(
            count=models.Count('id')
        ).order_by('-count')[:limit]
        
        return [item['query'] for item in trending]
    
    @staticmethod
    def get_related_searches(query, limit=5):
        """Get related searches"""
        from apps.products.models import Product
        from django.db.models import Q
        
        products = Product.objects.filter(
            Q(name__icontains=query) | Q(category__name__icontains=query)
        )
        
        # Get tags from related products
        related_tags = set()
        for product in products[:5]:
            related_tags.update(product.tags.values_list('name', flat=True))
        
        return list(related_tags)[:limit]


# ============================================================
# FACETED NAVIGATION
# ============================================================

class FacetedNavigation:
    """Generate facets for search"""
    
    @staticmethod
    def get_facets(query=None):
        """Get facets for navigation"""
        from apps.products.models import Product, Category
        from django.db.models import Count, Avg
        
        facets = {}
        
        products = Product.objects.filter(is_active=True)
        
        if query:
            from django.db.models import Q
            products = products.filter(
                Q(name__icontains=query) | Q(description__icontains=query)
            )
        
        # Categories
        facets['categories'] = list(
            products.values('category__name', 'category__slug')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        
        # Price ranges
        facets['price_ranges'] = [
            {'name': 'Under KES 500', 'min': 0, 'max': 500},
            {'name': 'KES 500 - 1000', 'min': 500, 'max': 1000},
            {'name': 'KES 1000 - 2000', 'min': 1000, 'max': 2000},
            {'name': 'Over KES 2000', 'min': 2000, 'max': None},
        ]
        
        # Ratings
        facets['ratings'] = [
            {'name': '5 Stars', 'min': 5},
            {'name': '4+ Stars', 'min': 4},
            {'name': '3+ Stars', 'min': 3},
        ]
        
        # Stock availability
        facets['availability'] = [
            {'name': 'In Stock', 'count': products.filter(stock__gt=0).count()},
            {'name': 'Out of Stock', 'count': products.filter(stock=0).count()},
        ]
        
        return facets


# ============================================================
# CELERY TASKS
# ============================================================

"""
from celery import shared_task

@shared_task
def reindex_all_products():
    '''Reindex all products in Elasticsearch'''
    from apps.products.models import Product
    
    ElasticsearchManager.create_product_index()
    
    products = Product.objects.filter(is_active=True)
    
    for product in products:
        ElasticsearchManager.index_product(product)
    
    logger.info(f'Reindexed {products.count()} products')

@shared_task
def cleanup_old_searches():
    '''Delete old search queries'''
    from apps.search.models import SearchQuery
    from datetime import timedelta
    from django.utils import timezone
    
    cutoff = timezone.now() - timedelta(days=30)
    SearchQuery.objects.filter(created_at__lt=cutoff).delete()

# Add to CELERY_BEAT_SCHEDULE:
'reindex-elasticsearch': {
    'task': 'apps.search.tasks.reindex_all_products',
    'schedule': 86400.0,  # Daily
},
'cleanup-search-queries': {
    'task': 'apps.search.tasks.cleanup_old_searches',
    'schedule': 604800.0,  # Weekly
},
"""