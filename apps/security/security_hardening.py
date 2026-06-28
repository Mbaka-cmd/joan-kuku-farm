# Security Hardening Guide - Production Security

import os
import hashlib
import secrets
from cryptography.fernet import Fernet

# ============================================================
# DJANGO SECURITY SETTINGS
# ============================================================

SECURITY_SETTINGS = {
    # HTTPS & SSL
    'SECURE_SSL_REDIRECT': True,
    'SESSION_COOKIE_SECURE': True,
    'CSRF_COOKIE_SECURE': True,
    'SECURE_BROWSER_XSS_FILTER': True,
    'SECURE_CONTENT_SECURITY_POLICY': {
        'default-src': ("'self'",),
        'script-src': ("'self'", "'unsafe-inline'"),
        'style-src': ("'self'", "'unsafe-inline'"),
    },
    
    # Headers
    'SECURE_HSTS_SECONDS': 31536000,  # 1 year
    'SECURE_HSTS_INCLUDE_SUBDOMAINS': True,
    'SECURE_HSTS_PRELOAD': True,
    
    # CORS
    'CORS_ALLOWED_ORIGINS': [
        'https://yourdomain.com',
        'https://www.yourdomain.com',
    ],
    'CORS_ALLOW_CREDENTIALS': True,
    
    # Passwords
    'PASSWORD_HASHERS': [
        'django.contrib.auth.hashers.Argon2PasswordHasher',
        'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    ],
    'PASSWORD_VALIDATORS': [
        'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
        'django.contrib.auth.password_validation.MinimumLengthValidator',
        'django.contrib.auth.password_validation.CommonPasswordValidator',
        'django.contrib.auth.password_validation.NumericPasswordValidator',
    ],
    
    # Sessions
    'SESSION_COOKIE_HTTPONLY': True,
    'SESSION_COOKIE_SAMESITE': 'Strict',
    'SESSION_EXPIRE_AT_BROWSER_CLOSE': True,
    'SESSION_COOKIE_AGE': 3600,  # 1 hour
    
    # Content Security
    'X_FRAME_OPTIONS': 'DENY',
}

# ============================================================
# INPUT VALIDATION & SANITIZATION
# ============================================================

class InputValidation:
    """Validate and sanitize user inputs"""
    
    @staticmethod
    def validate_email(email):
        """Validate email format"""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    @staticmethod
    def validate_phone(phone):
        """Validate phone number format"""
        import re
        # Kenyan phone numbers
        pattern = r'^(\+254|0)[1-9]\d{8}$'
        return re.match(pattern, phone) is not None
    
    @staticmethod
    def sanitize_input(user_input):
        """Remove potentially harmful characters"""
        import bleach
        
        # Allowed tags
        allowed_tags = ['p', 'br', 'strong', 'em', 'a']
        allowed_attributes = {'a': ['href']}
        
        sanitized = bleach.clean(
            user_input,
            tags=allowed_tags,
            attributes=allowed_attributes,
            strip=True
        )
        
        return sanitized
    
    @staticmethod
    def prevent_sql_injection():
        """SQL injection prevention"""
        """
        ALWAYS use Django ORM:
        
        # BAD - SQL Injection vulnerable
        Order.objects.raw(f"SELECT * FROM orders WHERE id = {user_input}")
        
        # GOOD - Safe
        Order.objects.filter(id=user_input)
        
        Use parameterized queries:
        from django.db import connection
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM orders WHERE id = %s", [user_id])
        """
        pass
    
    @staticmethod
    def prevent_xss():
        """Cross-Site Scripting prevention"""
        """
        Use template escaping:
        
        # Templates automatically escape by default
        {{ user_input }}  # Safely escaped
        
        Or explicitly escape in Python:
        from django.utils.html import escape
        escaped = escape(user_input)
        """
        pass
    
    @staticmethod
    def prevent_csrf():
        """Cross-Site Request Forgery prevention"""
        """
        Django CSRF token:
        
        # In template
        <form method="post">
            {% csrf_token %}
            <!-- form fields -->
        </form>
        
        # In AJAX
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
        }
        """
        pass


# ============================================================
# AUTHENTICATION SECURITY
# ============================================================

class AuthenticationSecurity:
    """Secure authentication implementation"""
    
    @staticmethod
    def hash_password(password):
        """Hash password using Argon2"""
        from django.contrib.auth.hashers import make_password
        return make_password(password)
    
    @staticmethod
    def verify_password(password, hash):
        """Verify password hash"""
        from django.contrib.auth.hashers import check_password
        return check_password(password, hash)
    
    @staticmethod
    def generate_secure_token(length=32):
        """Generate cryptographically secure token"""
        return secrets.token_urlsafe(length)
    
    @staticmethod
    def implement_brute_force_protection():
        """Protect against brute force attacks"""
        """
        Use django-ratelimit:
        
        pip install django-ratelimit
        
        @ratelimit(key='ip', rate='5/m', method='POST')
        def login_view(request):
            # Max 5 login attempts per minute per IP
            pass
        
        Or use django-axes:
        
        pip install django-axes
        
        INSTALLED_APPS = [
            'axes',
        ]
        
        # Locks account after N failed attempts
        """
        pass
    
    @staticmethod
    def implement_account_lockout():
        """Lock account after failed attempts"""
        """
        from axes.models import AccessAttempt
        
        # Auto-lockout after 5 failed attempts
        AXES_FAILURE_LIMIT = 5
        AXES_COOLOFF_DURATION = 30  # minutes
        AXES_LOCK_OUT_AT_FAILURE = True
        """
        pass
    
    @staticmethod
    def enforce_strong_passwords():
        """Enforce password strength requirements"""
        """
        settings.py:
        
        PASSWORD_VALIDATORS = [
            'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
            'django.contrib.auth.password_validation.MinimumLengthValidator',
            'django.contrib.auth.password_validation.CommonPasswordValidator',
            'django.contrib.auth.password_validation.NumericPasswordValidator',
        ]
        
        AUTH_PASSWORD_VALIDATORS = PASSWORD_VALIDATORS
        
        PASSWORD_VALIDATION = {
            'minimum_length': 12,
            'must_include_uppercase': True,
            'must_include_lowercase': True,
            'must_include_numbers': True,
            'must_include_special': True,
        }
        """
        pass


# ============================================================
# DATA ENCRYPTION
# ============================================================

class DataEncryption:
    """Encrypt sensitive data"""
    
    @staticmethod
    def encrypt_field(data, key):
        """Encrypt sensitive field"""
        from cryptography.fernet import Fernet
        
        f = Fernet(key)
        encrypted = f.encrypt(data.encode())
        return encrypted.decode()
    
    @staticmethod
    def decrypt_field(encrypted_data, key):
        """Decrypt sensitive field"""
        from cryptography.fernet import Fernet
        
        f = Fernet(key)
        decrypted = f.decrypt(encrypted_data.encode())
        return decrypted.decode()
    
    @staticmethod
    def hash_sensitive_data(data):
        """Hash sensitive data (one-way)"""
        return hashlib.sha256(data.encode()).hexdigest()
    
    @staticmethod
    def encrypt_database_at_rest():
        """Encrypt PostgreSQL at rest"""
        """
        PostgreSQL Transparent Data Encryption (TDE):
        
        1. Create encrypted tablespace
        2. Use pgcrypto extension
        3. Encrypt specific columns
        
        -- Enable pgcrypto
        CREATE EXTENSION pgcrypto;
        
        -- Encrypt sensitive column
        ALTER TABLE users
        ADD COLUMN phone_encrypted bytea;
        
        UPDATE users
        SET phone_encrypted = pgp_sym_encrypt(phone, 'secret-key');
        """
        pass


# ============================================================
# API SECURITY
# ============================================================

class APISecurity:
    """Secure API endpoints"""
    
    @staticmethod
    def implement_rate_limiting():
        """Rate limit API endpoints"""
        """
        from rest_framework.throttling import UserRateThrottle
        
        class APIRateThrottle(UserRateThrottle):
            scope = 'api'
            rate = '100/hour'
        
        # In viewset
        throttle_classes = [APIRateThrottle]
        """
        pass
    
    @staticmethod
    def validate_api_tokens():
        """Validate JWT tokens"""
        """
        from rest_framework_simplejwt.tokens import Token
        
        try:
            token = Token(user_token)
            # Token is valid
        except TokenError:
            # Token is invalid or expired
            pass
        """
        pass
    
    @staticmethod
    def implement_api_versioning():
        """Version API for security"""
        """
        Different API versions:
        - v1: Old, deprecated, limited access
        - v2: Current, full access
        - v3: New, beta, limited access
        """
        pass
    
    @staticmethod
    def add_security_headers():
        """Add security headers to responses"""
        """
        Middleware to add headers:
        
        class SecurityHeadersMiddleware:
            def __init__(self, get_response):
                self.get_response = get_response
            
            def __call__(self, request):
                response = self.get_response(request)
                
                response['X-Content-Type-Options'] = 'nosniff'
                response['X-Frame-Options'] = 'DENY'
                response['X-XSS-Protection'] = '1; mode=block'
                response['Strict-Transport-Security'] = 'max-age=31536000'
                response['Content-Security-Policy'] = "default-src 'self'"
                
                return response
        """
        pass


# ============================================================
# MONITORING & LOGGING
# ============================================================

class SecurityMonitoring:
    """Monitor security events"""
    
    @staticmethod
    def log_security_events():
        """Log suspicious activity"""
        """
        import logging
        
        security_logger = logging.getLogger('security')
        
        # Log failed login attempts
        security_logger.warning(
            f'Failed login attempt: {username}',
            extra={'ip': request.META.get('REMOTE_ADDR')}
        )
        
        # Log unauthorized access
        security_logger.error(
            f'Unauthorized access attempt',
            extra={'user': user_id, 'resource': resource}
        )
        
        # Log privilege escalation
        security_logger.critical(
            f'Privilege escalation attempt',
            extra={'user': user_id, 'target': target_role}
        )
        """
        pass
    
    @staticmethod
    def detect_suspicious_activity():
        """Detect and alert on suspicious patterns"""
        """
        Monitor:
        - Multiple failed login attempts
        - Access from unusual IP
        - Unusual API call patterns
        - Large data downloads
        - Privilege escalation attempts
        """
        pass


# ============================================================
# FILE UPLOAD SECURITY
# ============================================================

class FileUploadSecurity:
    """Secure file uploads"""
    
    @staticmethod
    def validate_file_upload(file):
        """Validate uploaded file"""
        import magic
        
        # Check file type
        allowed_types = ['image/jpeg', 'image/png', 'application/pdf']
        
        file_type = magic.from_buffer(file.read(1024), mime=True)
        if file_type not in allowed_types:
            raise ValueError('Invalid file type')
        
        # Check file size
        max_size = 5 * 1024 * 1024  # 5MB
        if file.size > max_size:
            raise ValueError('File too large')
        
        return True
    
    @staticmethod
    def scan_files_for_malware():
        """Scan uploads for malware"""
        """
        Use ClamAV:
        
        pip install pyclamd
        
        import pyclamd
        
        clam = pyclamd.ClamD()
        
        if clam.scan_file(file_path):
            # Malware detected!
            pass
        """
        pass
    
    @staticmethod
    def quarantine_suspicious_files():
        """Move suspicious files to quarantine"""
        """
        Separate storage for quarantined files
        """
        pass


# ============================================================
# COMPLIANCE & AUDITING
# ============================================================

class ComplianceAuditing:
    """Track compliance and audit logs"""
    
    @staticmethod
    def audit_user_actions():
        """Log all user actions"""
        """
        Create AuditLog model:
        
        class AuditLog(models.Model):
            user = models.ForeignKey(User)
            action = models.CharField(max_length=100)
            timestamp = models.DateTimeField(auto_now_add=True)
            details = models.JSONField()
        """
        pass
    
    @staticmethod
    def track_data_access():
        """Track who accesses what data"""
        """
        Log every:
        - Data view
        - Data export
        - Data modification
        - Data deletion
        """
        pass
    
    @staticmethod
    def implement_gdpr_compliance():
        """GDPR compliance"""
        """
        - Right to be forgotten
        - Data portability
        - Consent management
        - Data retention policies
        - Privacy by design
        """
        pass


# ============================================================
# SECURITY CHECKLIST
# ============================================================

"""
PRE-DEPLOYMENT SECURITY CHECKLIST:

Authentication:
☐ Enforce strong passwords
☐ Implement 2FA
☐ Use secure session handling
☐ HTTPS everywhere
☐ Protect against brute force
☐ Account lockout after failed attempts

Data Protection:
☐ Encrypt sensitive data at rest
☐ Encrypt data in transit (TLS)
☐ Hash passwords with strong algorithm
☐ PII encryption
☐ Secure backups

API Security:
☐ API authentication (JWT)
☐ Rate limiting
☐ Input validation
☐ Output encoding
☐ CORS properly configured
☐ API versioning

Application:
☐ SQL injection prevention
☐ XSS prevention
☐ CSRF protection
☐ Security headers
☐ Dependency scanning
☐ Code review

Infrastructure:
☐ Firewall configured
☐ SSL/TLS certificates
☐ HSTS enabled
☐ Regular security updates
☐ Penetration testing
☐ Security monitoring

Compliance:
☐ Audit logging
☐ Data retention policies
☐ GDPR compliance
☐ Terms of service
☐ Privacy policy
☐ Security incident plan
"""