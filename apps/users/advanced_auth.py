# Advanced Authentication: 2FA, OAuth2, Social Login

import os
import qrcode
import secrets
import string
from io import BytesIO
import base64
from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.conf import settings
from rest_framework import serializers, viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.core.cache import cache

User = get_user_model()

# ============================================================
# TWO-FACTOR AUTHENTICATION (2FA)
# ============================================================

class TwoFactorAuthenticationModel:
    """
    2FA implementation using TOTP (Time-based One-Time Password)
    """
    
    @staticmethod
    def generate_secret():
        """Generate a 32-character secret key"""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def generate_qr_code(user, secret):
        """Generate QR code for authenticator app"""
        import pyotp
        
        totp = pyotp.TOTP(secret)
        uri = totp.provisioning_uri(
            name=user.email,
            issuer_name='Joan Kuku Farm'
        )
        
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        return base64.b64encode(buffer.getvalue()).decode()
    
    @staticmethod
    def verify_token(secret, token):
        """Verify TOTP token"""
        import pyotp
        
        totp = pyotp.TOTP(secret)
        # Allow 30-second window before and after
        return totp.verify(token, valid_window=1)
    
    @staticmethod
    def generate_backup_codes(count=10):
        """Generate backup codes for account recovery"""
        codes = []
        for _ in range(count):
            code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
            codes.append(f'{code[:4]}-{code[4:]}')
        return codes


class Enable2FASerializer(serializers.Serializer):
    """Enable 2FA for user account"""
    token = serializers.CharField(required=False)
    
    def validate_token(self, value):
        if value and len(value) != 6:
            raise serializers.ValidationError("Token must be 6 digits")
        return value


class Verify2FASerializer(serializers.Serializer):
    """Verify 2FA token during login"""
    token = serializers.CharField(max_length=6)
    remember_device = serializers.BooleanField(default=False)
    
    def validate_token(self, value):
        if not value.isdigit() or len(value) != 6:
            raise serializers.ValidationError("Invalid token format")
        return value


class TwoFactorViewSet(viewsets.ViewSet):
    """2FA endpoints"""
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def setup(self, request):
        """
        Setup 2FA for user
        Returns QR code to scan with authenticator app
        """
        user = request.user
        
        # Generate secret
        secret = TwoFactorAuthenticationModel.generate_secret()
        
        # Generate QR code
        qr_code = TwoFactorAuthenticationModel.generate_qr_code(user, secret)
        
        # Store temporary secret in cache
        cache.set(f'2fa_setup_{user.id}', secret, 3600)  # 1 hour
        
        return Response({
            'qr_code': f'data:image/png;base64,{qr_code}',
            'secret': secret,
            'message': 'Scan QR code with Google Authenticator or Authy app'
        })
    
    @action(detail=False, methods=['post'])
    def verify_setup(self, request):
        """Verify 2FA setup with token"""
        user = request.user
        serializer = Enable2FASerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        token = serializer.validated_data.get('token')
        secret = cache.get(f'2fa_setup_{user.id}')
        
        if not secret:
            return Response(
                {'error': '2FA setup expired. Start over.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verify token
        if not TwoFactorAuthenticationModel.verify_token(secret, token):
            return Response(
                {'error': 'Invalid token'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Generate backup codes
        backup_codes = TwoFactorAuthenticationModel.generate_backup_codes()
        
        # Save 2FA to user (implement custom field)
        # user.two_factor_enabled = True
        # user.two_factor_secret = secret
        # user.backup_codes = backup_codes
        # user.save()
        
        cache.delete(f'2fa_setup_{user.id}')
        
        return Response({
            'message': '2FA enabled successfully',
            'backup_codes': backup_codes,
            'warning': 'Save these codes in a safe place for account recovery'
        })
    
    @action(detail=False, methods=['post'])
    def disable(self, request):
        """Disable 2FA"""
        user = request.user
        # user.two_factor_enabled = False
        # user.save()
        
        return Response({'message': '2FA disabled'})
    
    @action(detail=False, methods=['get'])
    def status(self, request):
        """Check 2FA status"""
        user = request.user
        # is_enabled = getattr(user, 'two_factor_enabled', False)
        
        return Response({
            'enabled': False,  # Replace with actual status
            'backup_codes_remaining': 0,  # Replace with actual count
        })


# ============================================================
# OAUTH2 INTEGRATION
# ============================================================

class OAuth2Provider:
    """OAuth2 provider integration (Google, Facebook, GitHub)"""
    
    @staticmethod
    def verify_google_token(id_token):
        """Verify Google OAuth2 token"""
        try:
            from google.auth.transport import requests
            from google.oauth2 import id_token as google_id_token
            
            request = requests.Request()
            payload = google_id_token.verify_oauth2_token(
                id_token,
                request,
                settings.GOOGLE_OAUTH_CLIENT_ID
            )
            
            return payload
        except Exception as e:
            return None
    
    @staticmethod
    def verify_github_token(access_token):
        """Verify GitHub OAuth2 token"""
        import requests
        
        headers = {'Authorization': f'token {access_token}'}
        response = requests.get('https://api.github.com/user', headers=headers)
        
        if response.status_code == 200:
            return response.json()
        return None
    
    @staticmethod
    def verify_facebook_token(access_token):
        """Verify Facebook OAuth2 token"""
        import requests
        
        response = requests.get(
            'https://graph.facebook.com/me',
            params={'access_token': access_token, 'fields': 'id,email,name'}
        )
        
        if response.status_code == 200:
            return response.json()
        return None


class GoogleLoginSerializer(serializers.Serializer):
    """Google OAuth2 login"""
    id_token = serializers.CharField()


class GitHubLoginSerializer(serializers.Serializer):
    """GitHub OAuth2 login"""
    access_token = serializers.CharField()


class OAuth2ViewSet(viewsets.ViewSet):
    """OAuth2 endpoints"""
    permission_classes = [AllowAny]
    
    @action(detail=False, methods=['post'])
    def google_login(self, request):
        """Login/register with Google"""
        serializer = GoogleLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        id_token = serializer.validated_data['id_token']
        payload = OAuth2Provider.verify_google_token(id_token)
        
        if not payload:
            return Response(
                {'error': 'Invalid token'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get or create user
        user, created = User.objects.get_or_create(
            email=payload['email'],
            defaults={
                'username': payload['email'].split('@')[0],
                'first_name': payload.get('given_name', ''),
                'last_name': payload.get('family_name', ''),
                'email_verified': True,
            }
        )
        
        if created:
            user.set_unusable_password()
            user.save()
        
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
            }
        })
    
    @action(detail=False, methods=['post'])
    def github_login(self, request):
        """Login/register with GitHub"""
        serializer = GitHubLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        access_token = serializer.validated_data['access_token']
        github_user = OAuth2Provider.verify_github_token(access_token)
        
        if not github_user:
            return Response(
                {'error': 'Invalid token'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get or create user
        email = github_user.get('email', f'{github_user["login"]}@github.local')
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'username': github_user['login'],
                'first_name': github_user.get('name', '').split()[0],
                'email_verified': bool(github_user.get('email')),
            }
        )
        
        if created:
            user.set_unusable_password()
            user.save()
        
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': {
                'id': user.id,
                'email': user.email,
                'username': user.username,
            }
        })


# ============================================================
# SETTINGS.PY ADDITIONS
# ============================================================

"""
Add to requirements.txt:
pyotp==2.8.0
qrcode==7.4.2
google-auth==2.20.0
PyGithub==1.58.0

Add to settings.py:

# 2FA Settings
TWO_FACTOR_PATCH_ADMIN = True
OTP_TOTP_ISSUER = 'Joan Kuku Farm'

# OAuth2 Settings
GOOGLE_OAUTH_CLIENT_ID = os.getenv('GOOGLE_OAUTH_CLIENT_ID')
GOOGLE_OAUTH_CLIENT_SECRET = os.getenv('GOOGLE_OAUTH_CLIENT_SECRET')

GITHUB_OAUTH_CLIENT_ID = os.getenv('GITHUB_OAUTH_CLIENT_ID')
GITHUB_OAUTH_CLIENT_SECRET = os.getenv('GITHUB_OAUTH_CLIENT_SECRET')

FACEBOOK_OAUTH_CLIENT_ID = os.getenv('FACEBOOK_OAUTH_CLIENT_ID')
FACEBOOK_OAUTH_CLIENT_SECRET = os.getenv('FACEBOOK_OAUTH_CLIENT_SECRET')

# Add to .env:
GOOGLE_OAUTH_CLIENT_ID=your-client-id
GOOGLE_OAUTH_CLIENT_SECRET=your-secret
GITHUB_OAUTH_CLIENT_ID=your-client-id
GITHUB_OAUTH_CLIENT_SECRET=your-secret
"""

# ============================================================
# BACKUP CODES VALIDATION
# ============================================================

class BackupCodeValidator:
    """Validate and use backup codes for account recovery"""
    
    @staticmethod
    def use_backup_code(user, code):
        """Use a backup code (one-time use)"""
        # Implement with your user model
        # if code in user.backup_codes:
        #     user.backup_codes.remove(code)
        #     user.save()
        #     return True
        return False
    
    @staticmethod
    def generate_new_backup_codes(user):
        """Generate new backup codes"""
        codes = TwoFactorAuthenticationModel.generate_backup_codes(10)
        # user.backup_codes = codes
        # user.save()
        return codes


# ============================================================
# TRUSTED DEVICES
# ============================================================

class TrustedDeviceManager:
    """Manage trusted devices to skip 2FA on trusted browsers"""
    
    @staticmethod
    def get_device_fingerprint(request):
        """Generate device fingerprint from request"""
        import hashlib
        
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        accept_language = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
        
        fingerprint_string = f'{user_agent}:{accept_language}'
        return hashlib.sha256(fingerprint_string.encode()).hexdigest()
    
    @staticmethod
    def trust_device(user, request, duration_days=30):
        """Mark device as trusted"""
        fingerprint = TrustedDeviceManager.get_device_fingerprint(request)
        expiry = datetime.now() + timedelta(days=duration_days)
        
        cache_key = f'trusted_device_{user.id}_{fingerprint}'
        cache.set(cache_key, True, duration_days * 86400)
        
        return fingerprint
    
    @staticmethod
    def is_device_trusted(user, request):
        """Check if device is trusted"""
        fingerprint = TrustedDeviceManager.get_device_fingerprint(request)
        cache_key = f'trusted_device_{user.id}_{fingerprint}'
        
        return cache.get(cache_key) is not None


# ============================================================
# SESSION MANAGEMENT
# ============================================================

class SessionSecurityManager:
    """Manage secure sessions"""
    
    @staticmethod
    def invalidate_all_sessions(user):
        """Invalidate all user sessions (logout everywhere)"""
        from rest_framework_simplejwt.models import BlacklistedToken
        
        # Blacklist all existing tokens
        # Implementation depends on your token setup
        pass
    
    @staticmethod
    def limit_concurrent_sessions(user, max_sessions=3):
        """Limit number of concurrent sessions"""
        cache_key = f'active_sessions_{user.id}'
        sessions = cache.get(cache_key, [])
        
        if len(sessions) >= max_sessions:
            # Invalidate oldest session
            sessions.pop(0)
        
        session_id = secrets.token_urlsafe(32)
        sessions.append(session_id)
        cache.set(cache_key, sessions, 86400 * 30)  # 30 days
        
        return session_id