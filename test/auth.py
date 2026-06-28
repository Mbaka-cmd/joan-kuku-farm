import pytest
from django.contrib.auth import get_user_model
from rest_framework import status

User = get_user_model()


@pytest.mark.django_db
class TestUserRegistration:
    """Test user registration endpoint"""
    
    def test_register_success(self, api_client):
        """Test successful user registration"""
        data = {
            'email': 'newuser@example.com',
            'phone_number': '0712345679',
            'first_name': 'John',
            'last_name': 'Doe',
            'password': 'TestPass123',
            'password_confirm': 'TestPass123',
            'address': '123 Main St',
            'city': 'Nairobi',
            'county': 'Nairobi County'
        }
        
        response = api_client.post('/api/auth/register/', data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert 'access' in response.data
        assert 'refresh' in response.data
        assert User.objects.filter(email='newuser@example.com').exists()
    
    def test_register_duplicate_email(self, api_client, user):
        """Test registration with duplicate email"""
        data = {
            'email': user.email,
            'phone_number': '0712345679',
            'first_name': 'Jane',
            'last_name': 'Doe',
            'password': 'TestPass123',
            'password_confirm': 'TestPass123'
        }
        
        response = api_client.post('/api/auth/register/', data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_register_password_mismatch(self, api_client):
        """Test registration with mismatched passwords"""
        data = {
            'email': 'newuser@example.com',
            'phone_number': '0712345679',
            'first_name': 'John',
            'last_name': 'Doe',
            'password': 'TestPass123',
            'password_confirm': 'DifferentPass456'
        }
        
        response = api_client.post('/api/auth/register/', data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestUserLogin:
    """Test user login endpoint"""
    
    def test_login_success(self, api_client, user):
        """Test successful login"""
        user.email_verified = True
        user.save()
        
        data = {
            'email': 'test@example.com',
            'password': 'testpass123'
        }
        
        response = api_client.post('/api/auth/login/', data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert 'access' in response.data
        assert 'refresh' in response.data
    
    def test_login_unverified_email(self, api_client, user):
        """Test login with unverified email"""
        user.email_verified = False
        user.save()
        
        data = {
            'email': 'test@example.com',
            'password': 'testpass123'
        }
        
        response = api_client.post('/api/auth/login/', data, format='json')
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_login_invalid_credentials(self, api_client, user):
        """Test login with invalid credentials"""
        data = {
            'email': 'test@example.com',
            'password': 'wrongpassword'
        }
        
        response = api_client.post('/api/auth/login/', data, format='json')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestUserProfile:
    """Test user profile endpoint"""
    
    def test_get_profile(self, authenticated_client, user):
        """Test getting user profile"""
        response = authenticated_client.get('/api/auth/profile/')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['email'] == user.email
        assert response.data['username'] == user.username
    
    def test_update_profile(self, authenticated_client, user):
        """Test updating user profile"""
        data = {
            'first_name': 'Jane',
            'last_name': 'Smith',
            'address': 'New Address',
            'city': 'Mombasa'
        }
        
        response = authenticated_client.put('/api/auth/profile/update/', data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['user']['first_name'] == 'Jane'
        
        # Verify in database
        user.refresh_from_db()
        assert user.first_name == 'Jane'
    
    def test_change_password(self, authenticated_client, user):
        """Test changing password"""
        data = {
            'old_password': 'testpass123',
            'new_password': 'NewPass456',
            'new_password_confirm': 'NewPass456'
        }
        
        response = authenticated_client.post('/api/auth/password/change/', data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify password changed
        user.refresh_from_db()
        assert user.check_password('NewPass456')
        assert not user.check_password('testpass123')