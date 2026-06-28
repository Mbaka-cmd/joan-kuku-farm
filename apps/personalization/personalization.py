# Real-time Personalization Engine - AI-Powered Content Customization

from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta
import logging

logger = logging.getLogger('personalization')

# ============================================================
# PERSONALIZATION MODELS
# ============================================================

class UserProfile(models.Model):
    """Extended user profile for personalization"""
    user = models.OneToOneField('users.CustomUser', on_delete=models.CASCADE)
    
    # Preferences
    preferred_categories = models.JSONField(default=list)
    price_sensitivity = models.CharField(
        max_length=20,
        choices=[('low', 'Budget'), ('medium', 'Mid-range'), ('high', 'Premium')],
        default='medium'
    )
    
    # Behavior
    browsing_behavior = models.CharField(
        max_length=50,
        choices=[
            ('explorer', 'Likes to Browse'),
            ('searcher', 'Uses Search'),
            ('recommendation', 'Follows Recommendations'),
        ]
    )
    
    # Device preferences
    preferred_device = models.CharField(max_length=50)
    
    # Psychographics
    lifestyle_tags = models.JSONField(default=list)
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_profile'


class PersonalizationRule(models.Model):
    """Rules for personalization"""
    RULE_TYPE = [
        ('homepage', 'Homepage Layout'),
        ('product_page', 'Product Page'),
        ('search_results', 'Search Results'),
        ('email', 'Email Content'),
        ('push', 'Push Notifications'),
        ('recommendations', 'Recommendations'),
    ]
    
    name = models.CharField(max_length=255)
    rule_type = models.CharField(max_length=50, choices=RULE_TYPE)
    
    # Conditions
    condition = models.JSONField()
    
    # Action
    personalization = models.JSONField()
    
    # Priority
    priority = models.IntegerField(default=10)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'personalization_rule'
        ordering = ['priority']


class PersonalizationEvent(models.Model):
    """Track personalization events"""
    user = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE)
    
    # Event
    event_type = models.CharField(max_length=100)  # viewed, clicked, purchased
    
    # Context
    page = models.CharField(max_length=255)
    personalization_id = models.CharField(max_length=100)
    
    # Result
    was_relevant = models.BooleanField(null=True, blank=True)
    engagement_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'personalization_event'
        indexes = [
            models.Index(fields=['user', '-created_at']),
        ]


class DynamicContent(models.Model):
    """Dynamic content blocks"""
    name = models.CharField(max_length=255)
    
    # Content variants
    default_variant = models.TextField()
    variants = models.JSONField(default=dict)  # {segment_id: content}
    
    # Placement
    page_type = models.CharField(max_length=100)
    
    # Performance
    impressions = models.IntegerField(default=0)
    clicks = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'dynamic_content'


# ============================================================
# PERSONALIZATION ENGINE
# ============================================================

class PersonalizationEngine:
    """Real-time personalization"""
    
    @staticmethod
    def get_personalized_homepage(user):
        """Generate personalized homepage"""
        from apps.recommendations.models import Recommendation
        from apps.products.models import Product
        
        personalization = {
            'hero_banner': PersonalizationEngine.get_hero_banner(user),
            'featured_categories': PersonalizationEngine.get_featured_categories(user),
            'recommended_products': PersonalizationEngine.get_recommendations(user),
            'personalized_deals': PersonalizationEngine.get_personalized_deals(user),
            'message': PersonalizationEngine.get_personalized_message(user),
        }
        
        return personalization
    
    @staticmethod
    def get_hero_banner(user):
        """Personalized hero banner"""
        from apps.products.models import Category
        
        try:
            profile = user.userprofile
            if profile.preferred_categories:
                category = Category.objects.get(id=profile.preferred_categories[0])
                return {
                    'title': f'Discover {category.name}',
                    'image': category.image_url,
                    'cta': 'Shop Now',
                }
        except:
            pass
        
        return {
            'title': 'Welcome Back!',
            'image': '/static/default-banner.jpg',
            'cta': 'Explore',
        }
    
    @staticmethod
    def get_featured_categories(user):
        """Get personalized category recommendations"""
        try:
            profile = user.userprofile
            return profile.preferred_categories[:5]
        except:
            # Default categories
            from apps.products.models import Category
            return list(Category.objects.all()[:5].values_list('id', flat=True))
    
    @staticmethod
    def get_recommendations(user):
        """Get personalized product recommendations"""
        from apps.recommendations.models import Recommendation
        
        recs = Recommendation.objects.filter(
            user=user,
            algorithm='hybrid'
        ).order_by('-score')[:8]
        
        return [
            {
                'product_id': rec.product.id,
                'name': rec.product.name,
                'price': rec.product.price,
                'image': rec.product.image_url,
                'reason': rec.reason,
            }
            for rec in recs
        ]
    
    @staticmethod
    def get_personalized_deals(user):
        """Get personalized offers"""
        from apps.orders.models import Order
        from apps.discount.models import Discount
        
        # Analyze purchase history
        try:
            profile = user.userprofile
            price_sensitivity = profile.price_sensitivity
        except:
            price_sensitivity = 'medium'
        
        # Get relevant discounts
        if price_sensitivity == 'low':
            # Show budget deals
            min_discount = 30
        elif price_sensitivity == 'high':
            # Show premium/exclusive deals
            min_discount = 10
        else:
            min_discount = 20
        
        # Would return applicable discounts
        return []
    
    @staticmethod
    def get_personalized_message(user):
        """Get personalized greeting message"""
        from apps.orders.models import Order
        
        order_count = Order.objects.filter(customer=user).count()
        
        if order_count == 0:
            return "Welcome! Explore our collection and get 10% off your first order."
        elif order_count < 5:
            return f"Welcome back! You've made {order_count} purchases with us."
        else:
            return "Welcome back, loyal customer! Check out what's new."
    
    @staticmethod
    def personalize_search_results(user, query):
        """Personalize search results"""
        from apps.products.models import Product
        from django.db.models import Q
        
        results = Product.objects.filter(
            Q(name__icontains=query) | Q(description__icontains=query),
            is_active=True
        )
        
        # Rerank based on user preference
        try:
            profile = user.userprofile
            preferred_price = {
                'low': (0, 500),
                'medium': (500, 2000),
                'high': (2000, float('inf')),
            }
            
            min_price, max_price = preferred_price[profile.price_sensitivity]
            
            # Boost matching price range
            results = results.annotate(
                price_match=models.Case(
                    models.When(price__gte=min_price, price__lte=max_price, then=models.Value(1)),
                    default=models.Value(0),
                    output_field=models.IntegerField()
                )
            ).order_by('-price_match', 'name')
        except:
            pass
        
        return results
    
    @staticmethod
    def get_personalized_email_content(user, email_type):
        """Personalize email content"""
        from apps.email_marketing.models import DynamicContent
        
        content = {
            'greeting': f"Hi {user.first_name or 'there'},",
            'body': '',
            'cta': '',
        }
        
        if email_type == 'product_recommendation':
            content['body'] = 'We found products you might like:'
            content['cta'] = 'See Recommendations'
        elif email_type == 'abandoned_cart':
            content['body'] = 'You left items in your cart:'
            content['cta'] = 'Complete Your Purchase'
        elif email_type == 'win_back':
            content['body'] = 'We miss you! Here are exclusive deals:'
            content['cta'] = 'Shop Now'
        
        return content
    
    @staticmethod
    def track_personalization(user, event_type, page, personalization_id, was_relevant=None):
        """Track personalization effectiveness"""
        from apps.personalization.models import PersonalizationEvent
        
        event = PersonalizationEvent.objects.create(
            user=user,
            event_type=event_type,
            page=page,
            personalization_id=personalization_id,
            was_relevant=was_relevant,
        )
        
        logger.debug(f'Personalization tracked: {personalization_id}')
        
        return event
    
    @staticmethod
    def optimize_rules():
        """Optimize personalization rules based on data"""
        from apps.personalization.models import PersonalizationEvent, PersonalizationRule
        
        # Get engagement data
        events = PersonalizationEvent.objects.filter(
            was_relevant__isnull=False,
            created_at__gte=timezone.now() - timedelta(days=30)
        )
        
        # Calculate effectiveness by rule
        rule_effectiveness = {}
        
        for event in events:
            rule_id = event.personalization_id
            
            if rule_id not in rule_effectiveness:
                rule_effectiveness[rule_id] = {
                    'relevant': 0,
                    'total': 0,
                }
            
            rule_effectiveness[rule_id]['total'] += 1
            if event.was_relevant:
                rule_effectiveness[rule_id]['relevant'] += 1
        
        # Update rule priorities based on effectiveness
        for rule_id, metrics in rule_effectiveness.items():
            if metrics['total'] >= 10:
                effectiveness = metrics['relevant'] / metrics['total']
                
                try:
                    rule = PersonalizationRule.objects.get(id=rule_id)
                    # Boost priority of effective rules
                    if effectiveness > 0.7:
                        rule.priority = max(1, rule.priority - 1)
                    elif effectiveness < 0.3:
                        rule.priority = rule.priority + 1
                    rule.save()
                except:
                    pass


# ============================================================
# CELERY TASKS
# ============================================================

"""
from celery import shared_task

@shared_task
def build_user_profiles():
    '''Build/update user profiles for personalization'''
    from apps.users.models import CustomUser
    from apps.personalization.models import UserProfile
    
    users = CustomUser.objects.filter(is_active=True)
    
    for user in users:
        profile, created = UserProfile.objects.get_or_create(user=user)
        
        # Analyze user behavior and update profile
        # This would be more sophisticated in production
        profile.save()

@shared_task
def optimize_personalization():
    '''Optimize personalization rules'''
    PersonalizationEngine.optimize_rules()

# Add to CELERY_BEAT_SCHEDULE:
'build-user-profiles': {
    'task': 'apps.personalization.tasks.build_user_profiles',
    'schedule': 604800.0,  # Weekly
},
'optimize-personalization': {
    'task': 'apps.personalization.tasks.optimize_personalization',
    'schedule': 604800.0,  # Weekly
},
"""