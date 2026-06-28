# Advanced User Behavior Analytics - Complete Behavioral System

from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta
import logging

logger = logging.getLogger('behavior')

# ============================================================
# BEHAVIOR ANALYTICS MODELS
# ============================================================

class UserBehavior(models.Model):
    """Track detailed user behavior"""
    user = models.OneToOneField('users.CustomUser', on_delete=models.CASCADE)
    
    # Session metrics
    total_sessions = models.IntegerField(default=0)
    avg_session_duration = models.IntegerField(default=0)  # seconds
    
    # Engagement
    total_page_views = models.IntegerField(default=0)
    total_clicks = models.IntegerField(default=0)
    scroll_depth_avg = models.IntegerField(default=0)  # %
    
    # Device preferences
    preferred_device = models.CharField(max_length=50, blank=True)
    device_breakdown = models.JSONField(default=dict)
    
    # Time patterns
    most_active_day = models.CharField(max_length=20, blank=True)
    most_active_hour = models.IntegerField(null=True, blank=True)
    
    # Purchase behavior
    purchase_frequency = models.IntegerField(default=0)  # days between purchases
    avg_cart_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Retention
    is_returning_user = models.BooleanField(default=False)
    days_since_last_visit = models.IntegerField(default=0)
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_behavior'


class UserSession(models.Model):
    """Individual user sessions"""
    user = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE)
    
    # Session
    session_id = models.CharField(max_length=100, unique=True)
    
    # Timing
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    duration = models.IntegerField(null=True, blank=True)  # seconds
    
    # Device
    device_type = models.CharField(max_length=50)
    browser = models.CharField(max_length=100)
    os = models.CharField(max_length=100)
    
    # Network
    ip_address = models.GenericIPAddressField()
    country = models.CharField(max_length=100)
    
    # Engagement
    pages_visited = models.IntegerField(default=0)
    events_fired = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'user_session'
        ordering = ['-start_time']


class PageVisit(models.Model):
    """Track page visits"""
    user = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE)
    session = models.ForeignKey(UserSession, on_delete=models.CASCADE)
    
    # Page
    url = models.CharField(max_length=500)
    page_title = models.CharField(max_length=255)
    
    # Timing
    visit_time = models.DateTimeField()
    time_on_page = models.IntegerField(default=0)  # seconds
    
    # Engagement
    scroll_depth = models.IntegerField()  # %
    click_count = models.IntegerField(default=0)
    
    # Referrer
    referrer = models.CharField(max_length=500, blank=True)
    
    class Meta:
        db_table = 'page_visit'
        ordering = ['-visit_time']


class UserEvent(models.Model):
    """Track user events"""
    EVENT_TYPE = [
        ('click', 'Click'),
        ('hover', 'Hover'),
        ('form_start', 'Form Started'),
        ('form_submit', 'Form Submitted'),
        ('search', 'Search'),
        ('filter', 'Filter Applied'),
        ('add_to_cart', 'Add to Cart'),
        ('remove_from_cart', 'Remove from Cart'),
        ('checkout', 'Checkout Started'),
        ('purchase', 'Purchase'),
    ]
    
    user = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE)
    session = models.ForeignKey(UserSession, on_delete=models.CASCADE)
    
    # Event
    event_type = models.CharField(max_length=50, choices=EVENT_TYPE)
    
    # Target
    element_id = models.CharField(max_length=255, blank=True)
    element_text = models.CharField(max_length=500, blank=True)
    
    # Context
    page_url = models.CharField(max_length=500)
    value = models.CharField(max_length=500, blank=True)
    
    # Metadata
    metadata = models.JSONField(default=dict)
    
    timestamp = models.DateTimeField()
    
    class Meta:
        db_table = 'user_event'
        indexes = [
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['event_type']),
        ]


class BehaviorCohort(models.Model):
    """Behavioral cohorts"""
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Criteria
    criteria = models.JSONField()
    
    # Members
    member_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'behavior_cohort'


class UserInsight(models.Model):
    """AI-generated insights"""
    user = models.OneToOneField('users.CustomUser', on_delete=models.CASCADE)
    
    # Insights
    insights = models.JSONField(default=dict)
    
    # Predictions
    predicted_churn_probability = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    predicted_lifetime_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Recommendations
    recommended_actions = models.JSONField(default=list)
    
    generated_at = models.DateTimeField()
    
    class Meta:
        db_table = 'user_insight'


# ============================================================
# BEHAVIOR ANALYTICS ENGINE
# ============================================================

class BehaviorAnalyticsEngine:
    """User behavior analysis"""
    
    @staticmethod
    def track_session(user, session_id, device_info):
        """Create new user session"""
        from apps.analytics.models import UserSession
        
        session = UserSession.objects.create(
            user=user,
            session_id=session_id,
            start_time=timezone.now(),
            device_type=device_info.get('device_type', 'unknown'),
            browser=device_info.get('browser', ''),
            os=device_info.get('os', ''),
            ip_address=device_info.get('ip', '127.0.0.1'),
            country=device_info.get('country', ''),
        )
        
        return session
    
    @staticmethod
    def track_page_visit(user, session, url, page_title, referrer=''):
        """Track page visit"""
        from apps.analytics.models import PageVisit
        
        visit = PageVisit.objects.create(
            user=user,
            session=session,
            url=url,
            page_title=page_title,
            visit_time=timezone.now(),
            referrer=referrer,
        )
        
        session.pages_visited += 1
        session.save()
        
        return visit
    
    @staticmethod
    def track_event(user, session, event_type, metadata=None):
        """Track user event"""
        from apps.analytics.models import UserEvent
        
        event = UserEvent.objects.create(
            user=user,
            session=session,
            event_type=event_type,
            page_url=metadata.get('page_url', '') if metadata else '',
            metadata=metadata or {},
            timestamp=timezone.now(),
        )
        
        session.events_fired += 1
        session.save()
        
        return event
    
    @staticmethod
    def close_session(session, duration):
        """Close user session"""
        session.end_time = timezone.now()
        session.duration = duration
        session.save()
    
    @staticmethod
    def analyze_user_behavior(user):
        """Analyze user behavior"""
        from apps.analytics.models import UserBehavior, UserSession, PageVisit
        from django.db.models import Count, Avg
        
        behavior, created = UserBehavior.objects.get_or_create(user=user)
        
        # Get sessions
        sessions = UserSession.objects.filter(user=user)
        
        behavior.total_sessions = sessions.count()
        behavior.avg_session_duration = int(
            sessions.aggregate(Avg('duration'))['duration__avg'] or 0
        )
        
        # Get page visits
        visits = PageVisit.objects.filter(user=user)
        behavior.total_page_views = visits.count()
        behavior.scroll_depth_avg = int(
            visits.aggregate(Avg('scroll_depth'))['scroll_depth__avg'] or 0
        )
        
        # Returning user check
        if behavior.total_sessions >= 2:
            behavior.is_returning_user = True
        
        behavior.save()
        
        logger.info(f'User behavior analyzed: {user.email}')
        
        return behavior
    
    @staticmethod
    def generate_user_insights(user):
        """Generate AI insights"""
        from apps.analytics.models import UserInsight, UserBehavior
        
        try:
            behavior = UserBehavior.objects.get(user=user)
        except:
            return None
        
        insights = {
            'engagement_level': 'high' if behavior.total_page_views > 50 else 'medium' if behavior.total_page_views > 10 else 'low',
            'avg_session_time': behavior.avg_session_duration,
            'returning_user': behavior.is_returning_user,
            'preferred_device': behavior.preferred_device,
        }
        
        # Predict churn
        churn_prob = BehaviorAnalyticsEngine.predict_churn(user)
        
        # Predict LTV
        ltv = BehaviorAnalyticsEngine.predict_lifetime_value(user)
        
        insight = UserInsight.objects.create(
            user=user,
            insights=insights,
            predicted_churn_probability=churn_prob,
            predicted_lifetime_value=ltv,
            generated_at=timezone.now(),
        )
        
        return insight
    
    @staticmethod
    def predict_churn(user):
        """Predict user churn probability"""
        from apps.analytics.models import UserBehavior
        
        try:
            behavior = UserBehavior.objects.get(user=user)
            
            # Simple heuristic
            if behavior.days_since_last_visit > 90:
                return 0.85
            elif behavior.days_since_last_visit > 30:
                return 0.5
            elif behavior.total_sessions < 2:
                return 0.3
            else:
                return 0.1
        
        except:
            return 0.5
    
    @staticmethod
    def predict_lifetime_value(user):
        """Predict user lifetime value"""
        from apps.orders.models import Order
        from django.db.models import Sum, Avg
        
        orders = Order.objects.filter(customer=user)
        
        if not orders.exists():
            return 0
        
        avg_order_value = orders.aggregate(Avg('total_amount'))['total_amount__avg'] or 0
        purchase_frequency = orders.count() / max((timezone.now() - user.date_joined).days, 1)
        
        # Estimate 3-year value
        predicted_ltv = avg_order_value * purchase_frequency * 365 * 3
        
        return predicted_ltv
    
    @staticmethod
    def get_behavior_report(user):
        """Get complete behavior report"""
        try:
            behavior = UserBehavior.objects.get(user=user)
            insight = user.userinsight
        except:
            return None
        
        return {
            'sessions': behavior.total_sessions,
            'page_views': behavior.total_page_views,
            'avg_session_duration': behavior.avg_session_duration,
            'engagement_level': insight.insights.get('engagement_level', 'unknown'),
            'churn_risk': float(insight.predicted_churn_probability),
            'lifetime_value': float(insight.predicted_lifetime_value),
            'is_returning_user': behavior.is_returning_user,
        }


# ============================================================
# CELERY TASKS
# ============================================================

"""
from celery import shared_task

@shared_task
def analyze_user_behaviors():
    '''Analyze all user behaviors'''
    from apps.users.models import CustomUser
    
    users = CustomUser.objects.filter(is_active=True)
    
    for user in users:
        BehaviorAnalyticsEngine.analyze_user_behavior(user)

@shared_task
def generate_user_insights():
    '''Generate insights for all users'''
    from apps.users.models import CustomUser
    
    users = CustomUser.objects.filter(is_active=True)
    
    for user in users:
        BehaviorAnalyticsEngine.generate_user_insights(user)

# Add to CELERY_BEAT_SCHEDULE:
'analyze-behaviors': {
    'task': 'apps.analytics.tasks.analyze_user_behaviors',
    'schedule': 604800.0,  # Weekly
},
'generate-insights': {
    'task': 'apps.analytics.tasks.generate_user_insights',
    'schedule': 604800.0,  # Weekly
},
"""