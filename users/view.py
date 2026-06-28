from rest_framework import viewsets, status, generics, views
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.contrib.auth import authenticate
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
import logging

from .models import CustomUser, UserPreferences
from .serializers import (
    UserSerializer,
    RegisterSerializer,
    LoginSerializer,
    ProfileUpdateSerializer,
    UserPreferencesSerializer,
    UserProfileDetailSerializer,
    PasswordChangeSerializer
)
from .permissions import IsOwnerOrReadOnly, IsVerifiedUser

logger = logging.getLogger(__name__)


class RegisterView(generics.CreateAPIView):
    """
    User registration endpoint
    POST /api/auth/register/
    """
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    
    def create(self, request, *args, **kwargs):
        """Register new user and return tokens"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Generate tokens
        refresh = RefreshToken.for_user(user)
        
        # Send verification email
        self._send_verification_email(user)
        
        return Response({
            'user': UserSerializer(user).data,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'message': 'Registration successful! Please verify your email.'
        }, status=status.HTTP_201_CREATED)
    
    def _send_verification_email(self, user):
        """Send email verification link"""
        try:
            verification_link = f"{settings.FRONTEND_URL}/verify-email/?user_id={user.id}"
            
            message = f"""
Welcome to Joan Kuku Farm!

Hello {user.first_name},

Thank you for registering with Joan Kuku Farm. To complete your account setup, please verify your email address.

Verify Email: {verification_link}

This link will expire in 24 hours.

Best regards,
Joan Kuku Farm Team
            """
            
            send_mail(
                subject='Verify Your Email - Joan Kuku Farm',
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,
            )
            
            logger.info(f"Verification email sent to {user.email}")
        except Exception as e:
            logger.error(f"Failed to send verification email: {str(e)}")


class LoginView(views.APIView):
    """
    User login endpoint
    POST /api/auth/login/
    Body: {
        "email": "user@example.com",
        "password": "password123"
    }
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        """Authenticate user and return JWT tokens"""
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = serializer.validated_data.get('user')
        
        # Check if email is verified
        if not user.email_verified:
            return Response({
                'error': 'Email not verified',
                'message': 'Please verify your email before logging in',
                'user_id': user.id
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Generate tokens
        refresh = RefreshToken.for_user(user)
        
        # Update last login
        user.last_login = timezone.now()
        user.save()
        
        return Response({
            'user': UserSerializer(user).data,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'message': 'Login successful'
        }, status=status.HTTP_200_OK)


class LogoutView(views.APIView):
    """
    User logout endpoint
    POST /api/auth/logout/
    Body: {
        "refresh": "refresh_token_here"
    }
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Logout user (blacklist refresh token)"""
        try:
            refresh_token = request.data.get('refresh')
            
            if not refresh_token:
                return Response({
                    'error': 'Refresh token required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            token = RefreshToken(refresh_token)
            token.blacklist()
            
            return Response({
                'message': 'Logout successful'
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class ProfileView(views.APIView):
    """
    Get current user profile
    GET /api/auth/profile/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get current user profile with preferences"""
        serializer = UserProfileDetailSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ProfileUpdateView(generics.UpdateAPIView):
    """
    Update user profile
    PUT/PATCH /api/auth/profile/update/
    """
    serializer_class = ProfileUpdateSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        """Return current user"""
        return self.request.user
    
    def update(self, request, *args, **kwargs):
        """Update user profile"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        return Response({
            'user': UserSerializer(instance).data,
            'message': 'Profile updated successfully'
        }, status=status.HTTP_200_OK)


class ChangePasswordView(views.APIView):
    """
    Change user password
    POST /api/auth/password/change/
    Body: {
        "old_password": "current_password",
        "new_password": "new_password123",
        "new_password_confirm": "new_password123"
    }
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Change password for authenticated user"""
        serializer = PasswordChangeSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response({
            'message': 'Password changed successfully'
        }, status=status.HTTP_200_OK)


class PasswordResetView(views.APIView):
    """
    Request password reset
    POST /api/auth/password/reset/
    Body: {
        "email": "user@example.com"
    }
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        """Send password reset email"""
        email = request.data.get('email')
        
        if not email:
            return Response({
                'error': 'Email is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user = CustomUser.objects.get(email=email)
            
            # Generate reset token (using JWT)
            refresh = RefreshToken.for_user(user)
            reset_token = str(refresh.access_token)
            
            reset_link = f"{settings.FRONTEND_URL}/reset-password/?token={reset_token}"
            
            message = f"""
Password Reset Request

Hello {user.first_name},

We received a request to reset your password. Click the link below to reset it:

Reset Password: {reset_link}

This link will expire in 1 hour.

If you didn't request this, please ignore this email.

Best regards,
Joan Kuku Farm Team
            """
            
            send_mail(
                subject='Password Reset - Joan Kuku Farm',
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )
            
            logger.info(f"Password reset email sent to {user.email}")
            
            return Response({
                'message': 'Password reset link sent to your email'
            }, status=status.HTTP_200_OK)
        
        except CustomUser.DoesNotExist:
            # Don't reveal if email exists (security best practice)
            return Response({
                'message': 'If email exists, password reset link has been sent'
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f"Password reset error: {str(e)}")
            return Response({
                'error': 'Failed to send reset email'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PasswordResetConfirmView(views.APIView):
    """
    Confirm password reset with token
    POST /api/auth/password/reset/confirm/
    Body: {
        "token": "jwt_token",
        "new_password": "new_password123",
        "new_password_confirm": "new_password123"
    }
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        """Reset password using token"""
        token = request.data.get('token')
        new_password = request.data.get('new_password')
        new_password_confirm = request.data.get('new_password_confirm')
        
        if not all([token, new_password, new_password_confirm]):
            return Response({
                'error': 'Token and passwords are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if new_password != new_password_confirm:
            return Response({
                'error': 'Passwords do not match'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if len(new_password) < 8:
            return Response({
                'error': 'Password must be at least 8 characters'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            from rest_framework_simplejwt.tokens import TokenError
            refresh = RefreshToken(token)
            user_id = refresh.get('user_id')
            user = CustomUser.objects.get(id=user_id)
            
            user.set_password(new_password)
            user.save()
            
            logger.info(f"Password reset successful for {user.email}")
            
            return Response({
                'message': 'Password reset successfully. Please login with your new password.'
            }, status=status.HTTP_200_OK)
        
        except TokenError:
            return Response({
                'error': 'Invalid or expired token'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        except CustomUser.DoesNotExist:
            return Response({
                'error': 'User not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        except Exception as e:
            logger.error(f"Password reset confirm error: {str(e)}")
            return Response({
                'error': 'Failed to reset password'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class VerifyEmailView(views.APIView):
    """
    Verify user email
    POST /api/auth/verify/email/
    Body: {
        "user_id": 1
    }
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        """Verify email using user ID"""
        user_id = request.data.get('user_id')
        
        if not user_id:
            # If authenticated, use current user
            if request.user and request.user.is_authenticated:
                user = request.user
            else:
                return Response({
                    'error': 'User ID is required'
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            try:
                user = CustomUser.objects.get(id=user_id)
            except CustomUser.DoesNotExist:
                return Response({
                    'error': 'User not found'
                }, status=status.HTTP_404_NOT_FOUND)
        
        # Mark email as verified
        user.email_verified = True
        user.is_verified = True
        user.save()
        
        logger.info(f"Email verified for {user.email}")
        
        return Response({
            'message': 'Email verified successfully'
        }, status=status.HTTP_200_OK)


class VerifyPhoneView(views.APIView):
    """
    Verify user phone number
    POST /api/auth/verify/phone/
    Body: {
        "phone_number": "0712345678",
        "otp": "123456"
    }
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Verify phone number using OTP"""
        phone_number = request.data.get('phone_number')
        otp = request.data.get('otp')
        
        if not all([phone_number, otp]):
            return Response({
                'error': 'Phone number and OTP are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        user = request.user
        
        # TODO: Implement OTP verification with Twilio
        # For now, we'll accept any OTP and mark as verified
        # In production, verify against OTP sent via SMS
        
        if len(otp) != 6:
            return Response({
                'error': 'OTP must be 6 digits'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        user.phone_number = phone_number
        user.phone_verified = True
        user.is_verified = True
        user.save()
        
        logger.info(f"Phone verified for {user.phone_number}")
        
        return Response({
            'message': 'Phone number verified successfully'
        }, status=status.HTTP_200_OK)


class UserPreferencesView(generics.RetrieveUpdateAPIView):
    """
    Get/Update user notification preferences
    GET/PUT /api/auth/profile/preferences/
    """
    serializer_class = UserPreferencesSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        """Get user preferences, create if doesn't exist"""
        preferences, created = UserPreferences.objects.get_or_create(user=self.request.user)
        return preferences
    
    def retrieve(self, request, *args, **kwargs):
        """Get user preferences"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def update(self, request, *args, **kwargs):
        """Update user preferences"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        return Response({
            'preferences': serializer.data,
            'message': 'Preferences updated successfully'
        }, status=status.HTTP_200_OK)


class UserListView(generics.ListAPIView):
    """
    List all users (admin only)
    GET /api/auth/users/
    """
    queryset = CustomUser.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Only admins can list users"""
        if self.request.user.is_staff:
            return CustomUser.objects.all()
        return CustomUser.objects.none()


class UserDetailView(generics.RetrieveAPIView):
    """
    Get user details by ID (admin only)
    GET /api/auth/users/<id>/
    """
    queryset = CustomUser.objects.all()
    serializer_class = UserProfileDetailSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'
    
    def get_object(self):
        """Allow user to view own profile, admins to view all"""
        user_id = self.kwargs.get('id')
        user = CustomUser.objects.get(id=user_id)
        
        if self.request.user == user or self.request.user.is_staff:
            return user
        
        self.permission_denied(self.request)


class UserSearchView(generics.ListAPIView):
    """
    Search users by name or email (admin only)
    GET /api/auth/users/search/?q=john
    """
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Search users"""
        if not self.request.user.is_staff:
            return CustomUser.objects.none()
        
        query = self.request.query_params.get('q', '')
        
        if query:
            return CustomUser.objects.filter(
                models.Q(first_name__icontains=query) |
                models.Q(last_name__icontains=query) |
                models.Q(email__icontains=query) |
                models.Q(phone_number__icontains=query)
            )
        
        return CustomUser.objects.all()


class UserStatsView(views.APIView):
    """
    Get user statistics (admin only)
    GET /api/auth/stats/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get user statistics"""
        if not request.user.is_staff:
            return Response({
                'error': 'Admin access required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        total_users = CustomUser.objects.count()
        verified_users = CustomUser.objects.filter(is_verified=True).count()
        email_verified = CustomUser.objects.filter(email_verified=True).count()
        phone_verified = CustomUser.objects.filter(phone_verified=True).count()
        
        # Get new users this month
        from datetime import timedelta
        month_ago = timezone.now() - timedelta(days=30)
        new_users_month = CustomUser.objects.filter(created_at__gte=month_ago).count()
        
        return Response({
            'total_users': total_users,
            'verified_users': verified_users,
            'email_verified': email_verified,
            'phone_verified': phone_verified,
            'new_users_month': new_users_month,
        }, status=status.HTTP_200_OK)


# Import at the end to avoid circular imports
from django.db import models