import pytest
from rest_framework import status


@pytest.mark.django_db
class TestProductList:
    """Test product listing endpoints"""
    
    def test_list_products(self, api_client, product):
        """Test listing products"""
        response = api_client.get('/api/products/')
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) >= 1
    
    def test_list_products_filter_by_category(self, api_client, product, category):
        """Test filtering products by category"""
        response = api_client.get(f'/api/products/?category={category.id}')
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_list_products_search(self, api_client, product):
        """Test searching products"""
        response = api_client.get('/api/products/?search=Test')
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_list_products_price_filter(self, api_client, product):
        """Test filtering products by price"""
        response = api_client.get('/api/products/?min_price=50&max_price=150')
        
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestProductDetail:
    """Test product detail endpoint"""
    
    def test_get_product_detail(self, api_client, product):
        """Test getting product details"""
        response = api_client.get(f'/api/products/{product.id}/')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == 'Test Product'
        assert response.data['price'] == '100.00'
    
    def test_product_not_found(self, api_client):
        """Test 404 for non-existent product"""
        response = api_client.get('/api/products/99999/')
        
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestProductSpecialViews:
    """Test special product views"""
    
    def test_featured_products(self, api_client, product):
        """Test getting featured products"""
        product.is_featured = True
        product.save()
        
        response = api_client.get('/api/products/featured/')
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_trending_products(self, api_client, product, order):
        """Test getting trending products"""
        response = api_client.get('/api/products/trending/')
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_top_rated_products(self, api_client, product):
        """Test getting top rated products"""
        response = api_client.get('/api/products/top_rated/')
        
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestCategoryList:
    """Test category endpoints"""
    
    def test_list_categories(self, api_client, category):
        """Test listing categories"""
        response = api_client.get('/api/products/categories/')
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_get_category_detail(self, api_client, category):
        """Test getting category detail"""
        response = api_client.get(f'/api/products/categories/{category.id}/')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == 'Test Category'