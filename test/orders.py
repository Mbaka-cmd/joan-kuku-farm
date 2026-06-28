import pytest
from rest_framework import status


@pytest.mark.django_db
class TestOrderCreation:
    """Test order creation"""
    
    def test_create_order_success(self, authenticated_client, product):
        """Test creating an order"""
        data = {
            'items': [
                {
                    'product_id': product.id,
                    'quantity': 5
                }
            ],
            'delivery_phone': '0712345678',
            'delivery_address': '123 Main St',
            'delivery_city': 'Nairobi',
            'payment_method': 'mpesa'
        }
        
        response = authenticated_client.post('/api/orders/', data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert 'order_id' in response.data
        assert response.data['total_amount'] == '500.00'
    
    def test_create_order_insufficient_stock(self, authenticated_client, product):
        """Test creating order with insufficient stock"""
        product.stock = 2
        product.save()
        
        data = {
            'items': [
                {
                    'product_id': product.id,
                    'quantity': 5
                }
            ],
            'delivery_phone': '0712345678',
            'delivery_address': '123 Main St',
            'delivery_city': 'Nairobi'
        }
        
        response = authenticated_client.post('/api/orders/', data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_create_order_unauthenticated(self, api_client, product):
        """Test creating order without authentication"""
        data = {
            'items': [
                {
                    'product_id': product.id,
                    'quantity': 5
                }
            ],
            'delivery_phone': '0712345678',
            'delivery_address': '123 Main St',
            'delivery_city': 'Nairobi'
        }
        
        response = api_client.post('/api/orders/', data, format='json')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestOrderList:
    """Test order listing"""
    
    def test_list_user_orders(self, authenticated_client, order):
        """Test listing user's orders"""
        response = authenticated_client.get('/api/orders/')
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) >= 1
    
    def test_list_orders_filter_by_status(self, authenticated_client, order):
        """Test filtering orders by status"""
        response = authenticated_client.get('/api/orders/?status=pending')
        
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestOrderDetail:
    """Test order detail"""
    
    def test_get_order_detail(self, authenticated_client, order):
        """Test getting order details"""
        response = authenticated_client.get(f'/api/orders/{order.id}/')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['order_id'] == order.order_id
        assert len(response.data['items']) == 1
    
    def test_get_other_user_order(self, authenticated_client, order, user):
        """Test accessing another user's order"""
        from django.contrib.auth import get_user_model
        other_user = get_user_model().objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='pass123',
            phone_number='0700000000'
        )
        order.customer = other_user
        order.save()
        
        response = authenticated_client.get(f'/api/orders/{order.id}/')
        
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestOrderTracking:
    """Test order tracking"""
    
    def test_track_order(self, api_client, order):
        """Test tracking order by order_id"""
        response = api_client.get(f'/api/orders/track/{order.order_id}/')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['order_id'] == order.order_id


@pytest.mark.django_db
class TestOrderCancellation:
    """Test order cancellation"""
    
    def test_cancel_order(self, authenticated_client, order):
        """Test cancelling an order"""
        data = {
            'reason': 'Changed my mind'
        }
        
        response = authenticated_client.post(f'/api/orders/{order.id}/cancel/', data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['order']['status'] == 'cancelled'
    
    def test_cancel_delivered_order(self, authenticated_client, order):
        """Test cancelling a delivered order (should fail)"""
        order.status = 'delivered'
        order.save()
        
        data = {
            'reason': 'Changed my mind'
        }
        
        response = authenticated_client.post(f'/api/orders/{order.id}/cancel/', data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST