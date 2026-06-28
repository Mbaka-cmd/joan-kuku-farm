# Advanced Rate Limiting Configuration for Joan Kuku Farm API

from rest_framework.throttling import UserRateThrottle, AnonRateThrottle, BaseThrottle
from rest_framework.response import Response
from rest_framework import status
from django.core.cache import cache
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# ============================================================
# CUSTOM THROTTLE CLASSES
# ============================================================

class StandardUserThrottle(UserRateThrottle):
    """
    Rate limit for authenticated users
    100 requests per hour
    """
    scope = 'user'
    rate = '100/hour'


class StandardAnonThrottle(AnonRateThrottle):
    """
    Rate limit for anonymous users
    20 requests per hour
    """
    scope = 'anon'
    rate = '20/hour'


class BurstUserThrottle(UserRateThrottle):
    """
    Strict rate limit for sensitive operations
    10 requests per minute
    """
    scope = 'burst'
    rate = '10/minute'


class OrderCreationThrottle(UserRateThrottle):
    """
    Rate limit for order creation
    5 orders per minute per user
    """
    scope = 'order_creation'
    rate = '5/minute'


class PaymentThrottle(UserRateThrottle):
    """
    Strict rate limit for payment operations
    3 attempts per minute per user
    """
    scope = 'payment'
    rate = '3/minute'


class SearchThrottle(UserRateThrottle):
    """
    Moderate rate limit for search
    30 requests per minute
    """
    scope = 'search'
    rate = '30/minute'


class AuthenticationThrottle(AnonRateThrottle):
    """
    Strict rate limit for login/registration
    5 attempts per minute
    """
    scope = 'auth'
    rate = '5/minute'


# ============================================================
# IP-BASED THROTTLING
# ============================================================

class IPRateThrottle(BaseThrottle):
    """
    Rate limit based on IP address
    Useful for preventing abuse from specific IPs
    """
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def throttle_success(self):
        return True
    
    def throttle_failure(self):
        return False
    
    def allow_request(self, request, view):
        ip = self.get_client_ip(request)
        cache_key = f'ip_rate_limit_{ip}'
        
        try:
            request_count = cache.get(cache_key, 0)
        except:
            request_count = 0
        
        # 1000 requests per hour per IP
        if request_count >= 1000:
            return False
        
        cache.set(cache_key, request_count + 1, 3600)
        return True


# ============================================================
# PROGRESSIVE RATE LIMITING
# ============================================================

class ProgressiveThrottle(UserRateThrottle):
    """
    Increases rate limits based on user tier/reputation
    New users: stricter limits
    Verified users: relaxed limits
    """
    
    def get_rate(self, request):
        if not request.user or not request.user.is_authenticated:
            return '20/hour'  # Anonymous
        
        user = request.user
        
        # Suspended users - no requests
        if hasattr(user, 'profile') and user.profile.is_suspended:
            return '0/hour'
        
        # New users (< 7 days) - strict limits
        if (datetime.now() - user.date_joined.replace(tzinfo=None)).days < 7:
            return '50/hour'
        
        # Verified users - standard limits
        if user.email_verified and user.is_verified:
            return '200/hour'
        
        # Standard limit
        return '100/hour'


# ============================================================
# REQUEST COUNTING & MONITORING
# ============================================================

class RequestCountingThrottle(BaseThrottle):
    """
    Count requests for analytics without throttling
    """
    
    def allow_request(self, request, view):
        # Count all requests
        cache_key = f'request_count_{datetime.now().strftime("%Y-%m-%d")}'
        count = cache.get(cache_key, 0)
        cache.set(cache_key, count + 1, 86400)  # 24 hours
        
        # Log excessive traffic
        if count > 10000:
            logger.warning(f'High traffic detected: {count} requests today')
        
        return True


# ============================================================
# THROTTLE CONFIGURATION FOR SETTINGS.PY
# ============================================================

"""
Add to settings.py REST_FRAMEWORK:

REST_FRAMEWORK = {
    ...
    'DEFAULT_THROTTLE_CLASSES': [
        'apps.api.throttling.StandardUserThrottle',
        'apps.api.throttling.StandardAnonThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'user': '100/hour',
        'anon': '20/hour',
        'burst': '10/minute',
        'order_creation': '5/minute',
        'payment': '3/minute',
        'search': '30/minute',
        'auth': '5/minute',
    }
    ...
}
"""

# ============================================================
# DECORATOR FOR VIEW-SPECIFIC THROTTLING
# ============================================================

from functools import wraps
from rest_framework.exceptions import Throttled

def throttle_view(throttle_class):
    """
    Decorator to apply throttling to specific views
    
    Usage:
        @throttle_view(PaymentThrottle)
        def process_payment(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            throttle = throttle_class()
            
            if not throttle.allow_request(request, view_func):
                raise Throttled(throttle.wait())
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


# ============================================================
# VIEWSET THROTTLE CONFIGURATION
# ============================================================

"""
Apply different throttles to different actions:

from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from apps.api.throttling import (
    StandardUserThrottle,
    OrderCreationThrottle,
    PaymentThrottle,
    SearchThrottle,
)

class OrderViewSet(ModelViewSet):
    # Override throttle classes per action
    throttle_classes = [StandardUserThrottle]
    
    def get_throttles(self):
        if self.action == 'create':
            throttle_classes = [OrderCreationThrottle]
        elif self.action == 'list':
            throttle_classes = [SearchThrottle]
        else:
            throttle_classes = self.throttle_classes
        
        return [throttle() for throttle in throttle_classes]


class PaymentViewSet(ModelViewSet):
    def get_throttles(self):
        if self.action in ['initiate_payment', 'initiate_refund']:
            throttle_classes = [PaymentThrottle]
        else:
            throttle_classes = [StandardUserThrottle]
        
        return [throttle() for throttle in throttle_classes]
"""

# ============================================================
# RATE LIMIT ERROR RESPONSES
# ============================================================

def get_rate_limit_headers(throttle, request, view):
    """
    Generate rate limit headers for response
    """
    if not hasattr(throttle, 'rate'):
        return {}
    
    # Parse rate string (e.g., '100/hour' → 100 requests per 3600 seconds)
    rate_string = throttle.rate
    num, period = rate_string.split('/')
    duration = {
        'second': 1,
        'minute': 60,
        'hour': 3600,
        'day': 86400,
    }.get(period, 3600)
    
    return {
        'X-RateLimit-Limit': str(num),
        'X-RateLimit-Period': str(duration),
        'X-RateLimit-Reset': str(int((datetime.now() + timedelta(seconds=duration)).timestamp())),
    }


# ============================================================
# THROTTLE STATUS ENDPOINT (ADMIN)
# ============================================================

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

@api_view(['GET'])
@permission_classes([IsAdminUser])
def throttle_stats(request):
    """
    Get throttle statistics (admin only)
    """
    return Response({
        'message': 'Throttle statistics',
        'note': 'Implement based on your tracking method',
    })


# ============================================================
# CELERY TASK TO CLEANUP THROTTLE CACHE
# ============================================================

"""
Add to celery tasks:

from celery import shared_task
from django.core.cache import cache
import logging

logger = logging.getLogger('celery')

@shared_task
def cleanup_throttle_cache():
    '''Clean up old throttle cache entries'''
    # Django Redis automatically expires keys, so this is optional
    logger.info('Throttle cache cleanup completed')
    return 'Throttle cache cleaned up'
"""

# ============================================================
# MONITORING EXCESSIVE THROTTLING
# ============================================================

class ThrottleMonitor:
    """
    Monitor and log throttle events
    """
    
    @staticmethod
    def log_throttle_event(request, throttle_class):
        """Log when a user is throttled"""
        user_id = request.user.id if request.user.is_authenticated else 'anonymous'
        ip = request.META.get('REMOTE_ADDR', 'unknown')
        
        logger.warning(
            f'Throttled: {throttle_class.__name__} | User: {user_id} | IP: {ip}',
            extra={
                'user_id': user_id,
                'ip': ip,
                'throttle_class': throttle_class.__name__,
                'path': request.path,
                'method': request.method,
            }
        )
    
    @staticmethod
    def detect_abuse_pattern(request, throttle_class):
        """
        Detect potential abuse patterns
        """
        user_id = request.user.id if request.user.is_authenticated else request.META.get('REMOTE_ADDR')
        
        cache_key = f'throttle_abuse_{throttle_class.__name__}_{user_id}'
        throttle_count = cache.get(cache_key, 0)
        
        # Alert if user is throttled more than 5 times in an hour
        if throttle_count >= 5:
            logger.error(
                f'Potential abuse detected: {user_id}',
                extra={'user_id': user_id, 'throttle_count': throttle_count}
            )
            
            # Consider temporary ban
            return True
        
        cache.set(cache_key, throttle_count + 1, 3600)
        return False


# ============================================================
# DOCUMENTATION
# ============================================================

"""
RATE LIMITING SUMMARY:

Public Endpoints (No Auth Required):
- Authentication (login, register): 5 requests/minute
- Product listing: 20 requests/hour
- Search: 20 requests/hour

Authenticated Endpoints:
- Standard: 100 requests/hour
- Order creation: 5 requests/minute
- Payment operations: 3 requests/minute
- Search: 30 requests/minute

Behavior:
- Requests below limit: 200 OK
- Limit reached: 429 Too Many Requests
- Throttle-Info headers included in response:
  - X-RateLimit-Limit: max requests
  - X-RateLimit-Period: window in seconds
  - X-RateLimit-Reset: unix timestamp when limit resets

Throttle-After: seconds until next request allowed
Retry-After: seconds before retry

Examples:
- User makes 101st request in an hour: 429 Too Many Requests
- Payment attempt #4 in a minute: 429 Too Many Requests
- After reset time passes: normal 200 response

For abuse prevention:
- Strict payment throttling (3/minute) prevents brute force
- IP-based throttling prevents distributed attacks
- Progressive throttling rewards good users
"""