# Advanced Monitoring and Logging Setup for Joan Kuku Farm

import os
import logging
import json
from datetime import datetime

# ============================================================
# LOGGING CONFIGURATION
# ============================================================

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'json': {
            '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': '%(asctime)s %(name)s %(levelname)s %(message)s'
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'handlers': {
        # Console handler
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        # File handler
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join('logs', 'django.log'),
            'maxBytes': 1024 * 1024 * 50,  # 50 MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
        # Error file handler
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join('logs', 'error.log'),
            'maxBytes': 1024 * 1024 * 100,  # 100 MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
        # JSON file handler (for ELK)
        'json_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join('logs', 'json.log'),
            'maxBytes': 1024 * 1024 * 100,
            'backupCount': 10,
            'formatter': 'json',
        },
        # Celery handler
        'celery_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join('logs', 'celery.log'),
            'maxBytes': 1024 * 1024 * 50,
            'backupCount': 5,
            'formatter': 'verbose',
        },
        # Mail handler for critical errors
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler',
        },
        # Sentry handler
        'sentry': {
            'level': 'ERROR',
            'class': 'sentry_sdk.integrations.logging.SentryHandler',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file', 'json_file'],
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': True,
        },
        'django.request': {
            'handlers': ['error_file', 'mail_admins', 'sentry'],
            'level': 'ERROR',
            'propagate': False,
        },
        'django.db.backends': {
            'handlers': ['file'],
            'level': 'DEBUG' if os.getenv('DEBUG') == 'True' else 'INFO',
            'propagate': False,
        },
        'celery': {
            'handlers': ['celery_file'],
            'level': 'INFO',
            'propagate': True,
        },
        'apps': {
            'handlers': ['console', 'file', 'json_file'],
            'level': 'INFO',
            'propagate': True,
        },
        'apps.orders': {
            'handlers': ['console', 'file', 'json_file', 'sentry'],
            'level': 'INFO',
        },
        'apps.payments': {
            'handlers': ['console', 'file', 'json_file', 'sentry'],
            'level': 'INFO',
        },
    },
}

# ============================================================
# SENTRY CONFIGURATION
# ============================================================

def init_sentry():
    """Initialize Sentry error tracking"""
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.redis import RedisIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration
    
    sentry_dsn = os.getenv('SENTRY_DSN')
    if not sentry_dsn:
        return
    
    sentry_sdk.init(
        dsn=sentry_dsn,
        integrations=[
            DjangoIntegration(),
            CeleryIntegration(),
            RedisIntegration(),
            LoggingIntegration(
                level=logging.INFO,
                event_level=logging.ERROR,
            ),
        ],
        # Performance monitoring
        traces_sample_rate=0.1,
        # Profiling
        profiles_sample_rate=0.1,
        # Environment
        environment=os.getenv('ENVIRONMENT', 'development'),
        # Release tracking
        release=os.getenv('APP_VERSION', '1.0.0'),
        # Additional context
        server_name=os.getenv('SERVER_NAME', 'unknown'),
        # Enable debug in development
        debug=os.getenv('DEBUG') == 'True',
        # Before send (filter sensitive data)
        before_send=before_send_sentry,
    )
    
    logging.info('✅ Sentry initialized')


def before_send_sentry(event, hint):
    """Filter sensitive data before sending to Sentry"""
    # Don't send 404 errors
    if event.get('exception'):
        exc_value = hint['exc_info'][1]
        if isinstance(exc_value, Exception) and '404' in str(exc_value):
            return None
    
    # Remove passwords and tokens from breadcrumbs
    for breadcrumb in event.get('breadcrumbs', {}).get('values', []):
        if 'data' in breadcrumb:
            data = breadcrumb['data']
            for key in ['password', 'token', 'secret', 'api_key']:
                if key in data:
                    data[key] = '***REDACTED***'
    
    return event

# ============================================================
# DATADOG INTEGRATION
# ============================================================

def init_datadog():
    """Initialize Datadog monitoring"""
    try:
        from datadog import initialize, api
        
        options = {
            'api_key': os.getenv('DATADOG_API_KEY'),
            'app_key': os.getenv('DATADOG_APP_KEY'),
        }
        
        if options['api_key']:
            initialize(**options)
            logging.info('✅ Datadog initialized')
    except ImportError:
        logging.warning('⚠️ Datadog SDK not installed')


# ============================================================
# CUSTOM LOGGING UTILITIES
# ============================================================

logger = logging.getLogger('apps')

class OrderLogger:
    """Logging for order operations"""
    
    @staticmethod
    def log_order_created(order_id, user_id, total_amount):
        logger.info(f'Order created: {order_id} | User: {user_id} | Amount: {total_amount}', extra={
            'order_id': order_id,
            'user_id': user_id,
            'amount': total_amount,
            'action': 'order_created',
        })
    
    @staticmethod
    def log_order_status_changed(order_id, old_status, new_status):
        logger.info(f'Order status changed: {order_id} {old_status} → {new_status}', extra={
            'order_id': order_id,
            'old_status': old_status,
            'new_status': new_status,
            'action': 'order_status_changed',
        })
    
    @staticmethod
    def log_order_cancelled(order_id, reason):
        logger.warning(f'Order cancelled: {order_id} | Reason: {reason}', extra={
            'order_id': order_id,
            'reason': reason,
            'action': 'order_cancelled',
        })


class PaymentLogger:
    """Logging for payment operations"""
    
    @staticmethod
    def log_payment_initiated(order_id, method, amount):
        logger.info(f'Payment initiated: {order_id} | Method: {method} | Amount: {amount}', extra={
            'order_id': order_id,
            'method': method,
            'amount': amount,
            'action': 'payment_initiated',
        })
    
    @staticmethod
    def log_payment_completed(order_id, transaction_id):
        logger.info(f'Payment completed: {order_id} | Transaction: {transaction_id}', extra={
            'order_id': order_id,
            'transaction_id': transaction_id,
            'action': 'payment_completed',
        })
    
    @staticmethod
    def log_payment_failed(order_id, reason):
        logger.error(f'Payment failed: {order_id} | Reason: {reason}', extra={
            'order_id': order_id,
            'reason': reason,
            'action': 'payment_failed',
        })


class PerformanceLogger:
    """Logging for performance monitoring"""
    
    @staticmethod
    def log_slow_query(query, duration):
        if duration > 1:  # Log queries over 1 second
            logger.warning(f'Slow database query: {duration:.2f}s', extra={
                'duration': duration,
                'query': query,
                'action': 'slow_query',
            })
    
    @staticmethod
    def log_slow_api_response(endpoint, duration, status_code):
        if duration > 1:  # Log responses over 1 second
            logger.warning(f'Slow API response: {endpoint} {duration:.2f}s', extra={
                'endpoint': endpoint,
                'duration': duration,
                'status_code': status_code,
                'action': 'slow_api_response',
            })


# ============================================================
# MIDDLEWARE FOR REQUEST/RESPONSE LOGGING
# ============================================================

import time
from django.utils.deprecation import MiddlewareMixin

class RequestLoggingMiddleware(MiddlewareMixin):
    """Log all HTTP requests and responses"""
    
    def process_request(self, request):
        request.start_time = time.time()
        return None
    
    def process_response(self, request, response):
        if hasattr(request, 'start_time'):
            duration = time.time() - request.start_time
            
            # Log request
            logger.info(
                f'{request.method} {request.path} {response.status_code} {duration:.2f}s',
                extra={
                    'method': request.method,
                    'path': request.path,
                    'status_code': response.status_code,
                    'duration': duration,
                    'user_id': request.user.id if request.user.is_authenticated else None,
                    'ip': self.get_client_ip(request),
                }
            )
            
            # Log slow requests
            if duration > 2:
                logger.warning(
                    f'Slow request: {request.method} {request.path} {duration:.2f}s',
                    extra={
                        'method': request.method,
                        'path': request.path,
                        'duration': duration,
                    }
                )
        
        return response
    
    @staticmethod
    def get_client_ip(request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


# ============================================================
# SETTINGS.PY ADDITIONS
# ============================================================

"""
Add to settings.py:

# Initialize monitoring
init_sentry()
init_datadog()

# Add middleware
MIDDLEWARE = [
    ...
    'apps.monitoring.middleware.RequestLoggingMiddleware',
]

# Logging configuration
LOGGING = LOGGING

# Email configuration for error alerts
ADMINS = [('Admin', 'admin@joankkfarm.com')]
MANAGERS = [('Manager', 'manager@joankkfarm.com')]

# Sentry
import sentry_sdk
sentry_sdk.init(...)

# Health check endpoint
HEALTH_CHECK_ENABLED = True
"""

# ============================================================
# MANAGEMENT COMMAND FOR TESTING
# ============================================================

"""
Create apps/core/management/commands/test_logging.py:

from django.core.management.base import BaseCommand
from apps.monitoring.logging_utils import OrderLogger, PaymentLogger

class Command(BaseCommand):
    help = 'Test logging configuration'
    
    def handle(self, *args, **options):
        self.stdout.write('Testing logging...')
        
        # Test order logging
        OrderLogger.log_order_created('JKF-20240101-ABC123', 1, 5000)
        OrderLogger.log_order_status_changed('JKF-20240101-ABC123', 'pending', 'confirmed')
        OrderLogger.log_order_cancelled('JKF-20240101-ABC123', 'Customer request')
        
        # Test payment logging
        PaymentLogger.log_payment_initiated('JKF-20240101-ABC123', 'mpesa', 5000)
        PaymentLogger.log_payment_completed('JKF-20240101-ABC123', 'MPR24010100123')
        
        self.stdout.write(self.style.SUCCESS('✅ Logging test complete'))
"""

# ============================================================
# DOCKER COMPOSE SERVICE FOR ELK STACK
# ============================================================

"""
Add to docker-compose.yml:

  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.0.0
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
    volumes:
      - elasticsearch_data:/usr/share/elasticsearch/data
    ports:
      - "9200:9200"
    networks:
      - jkf-network

  logstash:
    image: docker.elastic.co/logstash/logstash:8.0.0
    volumes:
      - ./logstash.conf:/usr/share/logstash/pipeline/logstash.conf:ro
    depends_on:
      - elasticsearch
    ports:
      - "5000:5000"
    networks:
      - jkf-network

  kibana:
    image: docker.elastic.co/kibana/kibana:8.0.0
    ports:
      - "5601:5601"
    environment:
      - ELASTICSEARCH_HOSTS=http://elasticsearch:9200
    depends_on:
      - elasticsearch
    networks:
      - jkf-network

volumes:
  elasticsearch_data:
"""

# ============================================================
# ENVIRONMENT VARIABLES
# ============================================================

"""
Add to .env:

# Monitoring
SENTRY_DSN=https://key@sentry.io/project-id
DATADOG_API_KEY=your-datadog-api-key
DATADOG_APP_KEY=your-datadog-app-key
ENVIRONMENT=production
SERVER_NAME=jkf-api-production
APP_VERSION=1.0.0

# Logging
DJANGO_LOG_LEVEL=INFO
LOG_FILE_PATH=logs/django.log
"""