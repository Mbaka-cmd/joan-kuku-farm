# Multi-Language & Localization (i18n) Implementation

from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy
from django.conf import settings
from rest_framework import serializers

# ============================================================
# DJANGO LOCALIZATION SETTINGS
# ============================================================

LOCALIZATION_SETTINGS = {
    # Enable translations
    'USE_I18N': True,
    'USE_L10N': True,
    'USE_TZ': True,
    
    # Supported languages
    'LANGUAGE_CODE': 'en-us',
    'LANGUAGES': [
        ('en', 'English'),
        ('sw', 'Swahili'),
        ('fr', 'French'),
        ('es', 'Spanish'),
        ('pt', 'Portuguese'),
        ('ar', 'Arabic'),
    ],
    
    # Language selection
    'LOCALE_PATHS': [
        '/path/to/locale',
    ],
    
    # Time zone
    'TIME_ZONE': 'Africa/Nairobi',
    
    # Currency
    'CURRENCY': 'KES',
    'DECIMAL_SEPARATOR': '.',
    'THOUSANDS_SEPARATOR': ',',
    
    # Date formatting
    'DATE_FORMAT': 'd/m/Y',
    'TIME_FORMAT': 'H:i',
    'DATETIME_FORMAT': 'd/m/Y H:i',
    
    # Number formatting
    'NUMBER_GROUPING': 3,
}

# ============================================================
# TRANSLATION MODELS
# ============================================================

class TranslatableModel:
    """Base model with translation support"""
    
    """
    Using django-parler for translations:
    
    pip install django-parler
    
    from parler.models import TranslatableModel, TranslatedFields
    
    class Product(TranslatableModel):
        translations = TranslatedFields(
            name=models.CharField(max_length=255),
            description=models.TextField(),
        )
        
        price = models.DecimalField(max_digits=10, decimal_places=2)
        sku = models.CharField(max_length=50)
    
    # Usage:
    # Get in current language
    product.name
    
    # Get in specific language
    product.translations.get(language_code='sw').name
    
    # Set translation
    product.translate('sw')
    product.name = 'Bidhaa'
    product.save()
    """
    pass


# ============================================================
# TRANSLATION STRINGS
# ============================================================

class TranslationStrings:
    """Common translation strings"""
    
    # Authentication
    AUTH_STRINGS = {
        'login': _('Login'),
        'logout': _('Logout'),
        'register': _('Register'),
        'password': _('Password'),
        'email': _('Email'),
        'remember_me': _('Remember me'),
        'forgot_password': _('Forgot password?'),
        'invalid_credentials': _('Invalid email or password'),
        'account_created': _('Account created successfully'),
        'login_required': _('Login required'),
    }
    
    # Orders
    ORDER_STRINGS = {
        'create_order': _('Create Order'),
        'order_placed': _('Order placed successfully'),
        'order_cancelled': _('Order cancelled'),
        'order_confirmed': _('Order confirmed'),
        'track_order': _('Track Order'),
        'order_status': _('Order Status'),
        'estimated_delivery': _('Estimated Delivery'),
    }
    
    # Products
    PRODUCT_STRINGS = {
        'products': _('Products'),
        'add_to_cart': _('Add to Cart'),
        'out_of_stock': _('Out of Stock'),
        'in_stock': _('In Stock'),
        'price': _('Price'),
        'quantity': _('Quantity'),
        'description': _('Description'),
    }
    
    # Payments
    PAYMENT_STRINGS = {
        'payment': _('Payment'),
        'pay_now': _('Pay Now'),
        'payment_successful': _('Payment successful'),
        'payment_failed': _('Payment failed'),
        'total_amount': _('Total Amount'),
        'payment_method': _('Payment Method'),
    }
    
    # Errors
    ERROR_STRINGS = {
        'error': _('Error'),
        'something_went_wrong': _('Something went wrong'),
        'try_again': _('Please try again'),
        'not_found': _('Not found'),
        'access_denied': _('Access denied'),
        'validation_error': _('Validation error'),
    }


# ============================================================
# SERIALIZER LOCALIZATION
# ============================================================

class LocalizedSerializer(serializers.Serializer):
    """Serializer with localization support"""
    
    def to_representation(self, instance):
        """Translate fields based on requested language"""
        data = super().to_representation(instance)
        request = self.context.get('request')
        
        if request:
            language = request.query_params.get('language', settings.LANGUAGE_CODE)
            # Get translations for the language
            if hasattr(instance, 'translate'):
                instance.translate(language)
        
        return data


class ProductLocalizedSerializer(serializers.Serializer):
    """Product serializer with multi-language support"""
    id = serializers.IntegerField()
    name = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    
    def get_name(self, obj):
        request = self.context.get('request')
        language = 'en'
        
        if request:
            language = request.query_params.get('language', 'en')
        
        # Get translated name
        try:
            return obj.translations.get(language_code=language).name
        except:
            return obj.name  # Fallback to default
    
    def get_description(self, obj):
        request = self.context.get('request')
        language = 'en'
        
        if request:
            language = request.query_params.get('language', 'en')
        
        # Get translated description
        try:
            return obj.translations.get(language_code=language).description
        except:
            return obj.description  # Fallback to default


# ============================================================
# TRANSLATION MANAGEMENT
# ============================================================

class TranslationManagement:
    """Manage translations"""
    
    @staticmethod
    def create_translation_strings():
        """Create translatable strings"""
        """
        1. Mark strings for translation in code:
        
        from django.utils.translation import gettext as _
        
        message = _('Hello World')
        
        2. Make translation files:
        
        django-admin makemessages -l sw
        django-admin makemessages -l fr
        
        3. Edit .po files in locale/ directory
        
        4. Compile translations:
        
        django-admin compilemessages
        """
        pass
    
    @staticmethod
    def extract_messages():
        """Extract translatable strings"""
        """
        django-admin makemessages -a
        
        This extracts all strings marked with _()
        Creates .po files for each language
        """
        pass
    
    @staticmethod
    def compile_translations():
        """Compile .po files to .mo files"""
        """
        django-admin compilemessages
        
        Must run before Django uses translations
        """
        pass


# ============================================================
# LANGUAGE MIDDLEWARE
# ============================================================

class LanguageMiddleware:
    """Detect and set language"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Detect language from:
        # 1. URL parameter: ?language=sw
        # 2. Accept-Language header
        # 3. User preference (if logged in)
        # 4. Default language
        
        from django.utils.translation import activate
        
        language = request.GET.get('language')
        
        if not language and request.user.is_authenticated:
            # Get user's preferred language
            language = getattr(request.user, 'preferred_language', None)
        
        if not language:
            # Use Accept-Language header
            language = request.META.get('HTTP_ACCEPT_LANGUAGE', '').split(',')[0]
        
        if not language:
            language = settings.LANGUAGE_CODE
        
        activate(language)
        request.LANGUAGE_CODE = language
        
        response = self.get_response(request)
        return response


# ============================================================
# API LANGUAGE SELECTION
# ============================================================

class LanguageSelectionMixin:
    """Mixin for API views with language support"""
    
    def get_language(self):
        """Get requested language"""
        language = self.request.query_params.get('language')
        
        if not language and self.request.user.is_authenticated:
            language = getattr(self.request.user, 'preferred_language', None)
        
        return language or settings.LANGUAGE_CODE
    
    def get_serializer_context(self):
        """Add language to serializer context"""
        context = super().get_serializer_context()
        context['language'] = self.get_language()
        return context


# ============================================================
# NUMBER & DATE FORMATTING
# ============================================================

class LocalizationFormatting:
    """Format numbers and dates based on locale"""
    
    @staticmethod
    def format_currency(amount, language='en'):
        """Format amount as currency"""
        from django.utils.formats import number_format
        
        currencies = {
            'en': 'KES',
            'sw': 'Shilingi',
            'fr': '€',
        }
        
        currency = currencies.get(language, 'KES')
        formatted = number_format(amount, 2)
        
        return f'{currency} {formatted}'
    
    @staticmethod
    def format_date(date, language='en'):
        """Format date based on locale"""
        from django.utils.formats import date_format
        
        formats = {
            'en': 'D, M d, Y',  # Wednesday, January 15, 2024
            'sw': 'd/m/Y',      # 15/01/2024
            'fr': 'd/m/Y',      # 15/01/2024
        }
        
        return date_format(date, formats.get(language))
    
    @staticmethod
    def format_phone(phone, language='en'):
        """Format phone number based on locale"""
        if language == 'en':
            # +254 726 306 005
            return f'+254 {phone[1:4]} {phone[4:7]} {phone[7:]}'
        elif language == 'sw':
            # +255726306005
            return f'+{phone}'
        return phone


# ============================================================
# TRANSLATION API ENDPOINTS
# ============================================================

"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

class LocalizationViewSet(viewsets.ViewSet):
    @action(detail=False)
    def supported_languages(self, request):
        '''Get list of supported languages'''
        languages = [
            {'code': code, 'name': name}
            for code, name in settings.LANGUAGES
        ]
        return Response(languages)
    
    @action(detail=False, methods=['post'])
    def set_language(self, request):
        '''Set user's preferred language'''
        language = request.data.get('language')
        
        if language not in dict(settings.LANGUAGES):
            return Response(
                {'error': 'Unsupported language'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        request.user.preferred_language = language
        request.user.save()
        
        return Response({'message': 'Language updated'})
    
    @action(detail=False)
    def translations(self, request):
        '''Get all translation strings for frontend'''
        language = request.query_params.get('language', 'en')
        
        from django.utils.translation import activate
        activate(language)
        
        translations = {
            'auth': TranslationStrings.AUTH_STRINGS,
            'orders': TranslationStrings.ORDER_STRINGS,
            'products': TranslationStrings.PRODUCT_STRINGS,
            'payments': TranslationStrings.PAYMENT_STRINGS,
            'errors': TranslationStrings.ERROR_STRINGS,
        }
        
        return Response(translations)
"""

# ============================================================
# FRONTEND USAGE
# ============================================================

"""
React component with localization:

import { useState, useEffect } from 'react';

function App() {
    const [language, setLanguage] = useState('en');
    const [translations, setTranslations] = useState({});
    
    useEffect(() => {
        // Fetch translations for language
        fetch(`/api/translations/?language=${language}`)
            .then(r => r.json())
            .then(data => setTranslations(data))
    }, [language])
    
    const t = (key) => {
        const keys = key.split('.');
        return keys.reduce((obj, k) => obj?.[k], translations) || key;
    }
    
    return (
        <div>
            <select value={language} onChange={e => setLanguage(e.target.value)}>
                <option value="en">English</option>
                <option value="sw">Swahili</option>
                <option value="fr">French</option>
            </select>
            
            <h1>{t('auth.login')}</h1>
            <button>{t('auth.login')}</button>
        </div>
    )
}

export default App;
"""

# ============================================================
# SETTINGS.PY CONFIGURATION
# ============================================================

"""
Add to settings.py:

# Localization
USE_I18N = True
USE_L10N = True
USE_TZ = True

LANGUAGE_CODE = 'en-us'
LANGUAGES = [
    ('en', 'English'),
    ('sw', 'Swahili'),
    ('fr', 'French'),
    ('es', 'Spanish'),
]

LOCALE_PATHS = [
    BASE_DIR / 'locale',
]

TIME_ZONE = 'Africa/Nairobi'

# Add middleware
MIDDLEWARE = [
    ...
    'django.middleware.locale.LocaleMiddleware',
    'apps.core.middleware.LanguageMiddleware',
]

# REST Framework localization
REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}
"""