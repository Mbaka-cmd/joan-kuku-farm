import django_filters
from rest_framework import filters
from .models import Product, Category


class ProductFilter(django_filters.FilterSet):
    """Advanced filtering for products"""
    
    # Price range
    min_price = django_filters.NumberFilter(
        field_name='price',
        lookup_expr='gte',
        label='Minimum price'
    )
    max_price = django_filters.NumberFilter(
        field_name='price',
        lookup_expr='lte',
        label='Maximum price'
    )
    
    # Category
    category = django_filters.ModelChoiceFilter(
        queryset=Category.objects.all(),
        field_name='category',
        to_field_name='id'
    )
    
    # Stock status
    in_stock = django_filters.BooleanFilter(
        method='filter_in_stock',
        label='In stock'
    )
    
    # Vaccination status
    is_vaccinated = django_filters.BooleanFilter()
    
    # Featured
    is_featured = django_filters.BooleanFilter()
    
    # Status
    is_active = django_filters.BooleanFilter()
    
    # Search
    search = django_filters.CharFilter(
        method='search_filter',
        label='Search products'
    )
    
    class Meta:
        model = Product
        fields = []
    
    def filter_in_stock(self, queryset, name, value):
        """Filter by stock status"""
        if value:
            return queryset.filter(stock__gt=0)
        return queryset
    
    def search_filter(self, queryset, name, value):
        """Search in name, description, SKU"""
        if value:
            return queryset.filter(
                models.Q(name__icontains=value) |
                models.Q(description__icontains=value) |
                models.Q(SKU__icontains=value) |
                models.Q(category__name__icontains=value)
            )
        return queryset


class CategoryFilter(django_filters.FilterSet):
    """Filter for categories"""
    
    search = django_filters.CharFilter(
        field_name='name',
        lookup_expr='icontains',
        label='Search categories'
    )
    
    class Meta:
        model = Category
        fields = ['name']


class ProductSearchFilter(filters.SearchFilter):
    """Custom search filter for products"""
    
    def get_search_fields(self, view, request):
        """Define searchable fields"""
        return ['name', 'description', 'SKU', 'category__name']


class ProductOrderingFilter(filters.OrderingFilter):
    """Custom ordering filter for products"""
    
    def get_valid_fields(self, queryset, view, request):
        """Define orderable fields"""
        return [
            ('price', 'price'),
            ('-price', 'Price: High to Low'),
            ('created_at', 'Newest'),
            ('-created_at', 'Oldest'),
            ('name', 'Name: A-Z'),
            ('-name', 'Name: Z-A'),
            ('stock', 'Stock: Low to High'),
            ('-stock', 'Stock: High to Low'),
        ]


# Import models at the end to avoid circular imports
from django.db import models