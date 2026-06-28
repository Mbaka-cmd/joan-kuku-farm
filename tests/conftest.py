import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.products.models import Category, Product
from apps.orders.models import Order

User = get_user_model()


@pytest.fixture
def api_client():
    """API client for testing"""
    return APIClient()


@pytest.fixture
def user(db):
    """Create a test user"""
    return User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123',
        phone_number='0712345678',
        is_verified=True,
        email_verified=True
    )


@pytest.fixture
def authenticated_client(api_client, user):
    """API client with authenticated user"""
    refresh = RefreshToken.for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    api_client.user = user
    return api_client


@pytest.fixture
def admin_user(db):
    """Create a test admin user"""
    return User.objects.create_superuser(
        username='admin',
        email='admin@example.com',
        password='admin123',
        phone_number='0700000000'
    )


@pytest.fixture
def admin_client(api_client, admin_user):
    """API client with admin user"""
    refresh = RefreshToken.for_user(admin_user)
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    api_client.user = admin_user
    return api_client


@pytest.fixture
def category(db):
    """Create a test category"""
    return Category.objects.create(
        name='Test Category',
        slug='test-category',
        description='Test description'
    )


@pytest.fixture
def product(db, category):
    """Create a test product"""
    return Product.objects.create(
        SKU='TEST-001',
        name='Test Product',
        slug='test-product',
        description='Test product description',
        category=category,
        price=100.00,
        unit='per unit',
        stock=50,
        is_active=True
    )


@pytest.fixture
def order(db, user, product):
    """Create a test order"""
    order = Order.objects.create(
        customer=user,
        subtotal=500.00,
        total_amount=500.00,
        delivery_phone='0712345678',
        delivery_address='Test Address',
        delivery_city='Nairobi',
        status='pending'
    )
    from apps.orders.models import OrderItem
    OrderItem.objects.create(
        order=order,
        product=product,
        quantity=5,
        unit_price=100.00
    )
    return order


@pytest.mark.django_db
class TestSetup:
    """Test that fixtures are set up correctly"""
    
    def test_user_created(self, user):
        assert user.username == 'testuser'
        assert user.email == 'test@example.com'
    
    def test_product_created(self, product):
        assert product.name == 'Test Product'
        assert product.price == 100.00
    
    def test_order_created(self, order):
        assert order.customer.username == 'testuser'
        assert order.total_amount == 500.00