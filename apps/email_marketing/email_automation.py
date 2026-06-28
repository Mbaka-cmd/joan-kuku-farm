# Advanced Email Marketing Automation System

from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta
import logging

logger = logging.getLogger('email_marketing')

# ============================================================
# EMAIL MARKETING MODELS
# ============================================================

class EmailSequence(models.Model):
    """Automated email sequences"""
    TRIGGER_TYPE = [
        ('welcome', 'Welcome Series'),
        ('abandoned_cart', 'Abandoned Cart'),
        ('post_purchase', 'Post Purchase'),
        ('reengagement', 'Re-engagement'),
        ('win_back', 'Win Back'),
        ('birthday', 'Birthday'),
        ('milestone', 'Milestone'),
    ]
    
    name = models.CharField(max_length=255)
    trigger_type = models.CharField(max_length=30, choices=TRIGGER_TYPE)
    description = models.TextField(blank=True)
    
    # Configuration
    is_active = models.BooleanField(default=True)
    auto_enroll = models.BooleanField(default=True)
    
    # Personalization
    use_personalization = models.BooleanField(default=True)
    use_dynamic_content = models.BooleanField(default=True)
    
    # Analytics
    total_enrolled = models.IntegerField(default=0)
    total_completed = models.IntegerField(default=0)
    open_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    click_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    conversion_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'email_sequence'
        ordering = ['-created_at']


class SequenceEmail(models.Model):
    """Individual emails in sequence"""
    sequence = models.ForeignKey(EmailSequence, on_delete=models.CASCADE, related_name='emails')
    
    # Order
    order = models.IntegerField()
    
    # Timing
    delay_days = models.IntegerField(default=0)
    delay_hours = models.IntegerField(default=0)
    send_hour = models.IntegerField(default=9)  # Hour of day to send
    
    # Content
    subject = models.CharField(max_length=255)
    preview_text = models.CharField(max_length=255, blank=True)
    body = models.TextField()
    
    # CTA
    cta_text = models.CharField(max_length=255, blank=True)
    cta_url = models.URLField(blank=True)
    
    # Dynamic content
    dynamic_sections = models.JSONField(default=dict)
    
    # Analytics
    sent_count = models.IntegerField(default=0)
    open_count = models.IntegerField(default=0)
    click_count = models.IntegerField(default=0)
    conversion_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'sequence_email'
        unique_together = ['sequence', 'order']


class EmailSubscriber(models.Model):
    """Email list management"""
    user = models.OneToOneField('users.CustomUser', on_delete=models.CASCADE)
    
    # Subscription
    email = models.EmailField()
    is_subscribed = models.BooleanField(default=True)
    
    # Preferences
    frequency = models.CharField(
        max_length=20,
        choices=[
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
            ('monthly', 'Monthly'),
            ('promotional', 'Promotional Only'),
        ],
        default='weekly'
    )
    
    # Interests
    interests = models.JSONField(default=list)  # ['electronics', 'fashion', etc]
    
    # Engagement
    score = models.IntegerField(default=50)  # 0-100, engagement score
    last_open = models.DateTimeField(null=True, blank=True)
    last_click = models.DateTimeField(null=True, blank=True)
    
    # Compliance
    unsubscribe_date = models.DateTimeField(null=True, blank=True)
    complaint_count = models.IntegerField(default=0)
    
    # Lists
    lists = models.ManyToManyField('EmailList', blank=True)
    
    subscribed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'email_subscriber'


class EmailList(models.Model):
    """Segmented email lists"""
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Segment
    segment_criteria = models.JSONField(default=dict)
    
    # Stats
    subscriber_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'email_list'


class EmailCampaign(models.Model):
    """Email marketing campaigns"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('sending', 'Sending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
    ]
    
    name = models.CharField(max_length=255)
    
    # Content
    subject = models.CharField(max_length=255)
    preview_text = models.CharField(max_length=255, blank=True)
    body = models.TextField()
    
    # Target
    target_list = models.ForeignKey(EmailList, on_delete=models.SET_NULL, null=True)
    
    # Schedule
    scheduled_send = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Results
    total_sent = models.IntegerField(default=0)
    open_count = models.IntegerField(default=0)
    click_count = models.IntegerField(default=0)
    unsubscribe_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'email_campaign'
        ordering = ['-created_at']


class EmailTracking(models.Model):
    """Track individual email interactions"""
    subscriber = models.ForeignKey(EmailSubscriber, on_delete=models.CASCADE)
    campaign = models.ForeignKey(EmailCampaign, on_delete=models.CASCADE)
    
    # Events
    sent_at = models.DateTimeField()
    opened_at = models.DateTimeField(null=True, blank=True)
    clicked_at = models.DateTimeField(null=True, blank=True)
    
    # Interaction
    click_count = models.IntegerField(default=0)
    clicked_links = models.JSONField(default=list)
    
    # Device
    device_type = models.CharField(max_length=50, blank=True)
    
    class Meta:
        db_table = 'email_tracking'
        unique_together = ['subscriber', 'campaign']


# ============================================================
# EMAIL AUTOMATION ENGINE
# ============================================================

class EmailAutomationEngine:
    """Manage email marketing automation"""
    
    @staticmethod
    def enroll_in_sequence(user, sequence_type):
        """Enroll user in email sequence"""
        from apps.email_marketing.models import EmailSequence, SequenceEmail, SequenceEnrollment
        
        try:
            sequence = EmailSequence.objects.get(trigger_type=sequence_type, is_active=True)
        except EmailSequence.DoesNotExist:
            return None
        
        # Check if already enrolled
        if SequenceEnrollment.objects.filter(user=user, sequence=sequence).exists():
            return None
        
        enrollment = SequenceEnrollment.objects.create(
            user=user,
            sequence=sequence,
        )
        
        # Schedule first email
        first_email = sequence.emails.order_by('order').first()
        if first_email:
            send_time = timezone.now() + timedelta(
                days=first_email.delay_days,
                hours=first_email.delay_hours
            )
            
            # Schedule email send
            from apps.email_marketing.tasks import send_sequence_email
            send_sequence_email.apply_async(
                args=[enrollment.id, first_email.id],
                eta=send_time
            )
        
        logger.info(f'User {user.email} enrolled in {sequence_type}')
        
        return enrollment
    
    @staticmethod
    def personalize_email(subscriber, email_template):
        """Personalize email for subscriber"""
        
        content = email_template.body
        
        # Name personalization
        content = content.replace('{{first_name}}', subscriber.user.first_name or 'Valued Customer')
        content = content.replace('{{last_name}}', subscriber.user.last_name or '')
        
        # Behavior-based personalization
        last_purchase = subscriber.user.order_set.order_by('-created_at').first()
        if last_purchase:
            content = content.replace('{{last_purchase_date}}', last_purchase.created_at.strftime('%B %d, %Y'))
        
        # Recommendation personalization
        from apps.recommendations.models import Recommendation
        recommendations = Recommendation.objects.filter(
            user=subscriber.user,
            algorithm='hybrid'
        )[:3]
        
        if recommendations:
            product_names = ', '.join([rec.product.name for rec in recommendations])
            content = content.replace('{{recommendations}}', product_names)
        
        return content
    
    @staticmethod
    def segment_subscribers():
        """Segment subscribers for targeted campaigns"""
        from apps.email_marketing.models import EmailSubscriber
        from django.db.models import Count, Sum
        
        segments = {}
        
        # High engagement
        high_engagement = EmailSubscriber.objects.filter(
            score__gte=75,
            is_subscribed=True
        ).count()
        segments['high_engagement'] = high_engagement
        
        # At risk
        at_risk = EmailSubscriber.objects.filter(
            score__lte=25,
            is_subscribed=True,
            last_open__lt=timezone.now() - timedelta(days=90)
        ).count()
        segments['at_risk'] = at_risk
        
        # VIP customers
        vip = EmailSubscriber.objects.filter(
            user__order_set__aggregated_total__gte=10000,
            is_subscribed=True
        ).count()
        segments['vip'] = vip
        
        return segments
    
    @staticmethod
    def optimize_send_time(subscriber):
        """Optimize email send time for subscriber"""
        from apps.email_marketing.models import EmailTracking
        
        # Get historical open data
        opens = EmailTracking.objects.filter(
            subscriber=subscriber,
            opened_at__isnull=False
        ).values_list('opened_at', flat=True)
        
        if not opens:
            return 9  # Default to 9 AM
        
        # Find most common hour of open
        hours = {}
        for open_time in opens:
            hour = open_time.hour
            hours[hour] = hours.get(hour, 0) + 1
        
        best_hour = max(hours, key=hours.get)
        return best_hour
    
    @staticmethod
    def calculate_engagement_score(subscriber):
        """Calculate subscriber engagement score"""
        from apps.email_marketing.models import EmailTracking
        
        score = 50  # Base score
        
        # Opens in last 30 days
        opens_30d = EmailTracking.objects.filter(
            subscriber=subscriber,
            opened_at__gte=timezone.now() - timedelta(days=30)
        ).count()
        
        score += min(opens_30d * 5, 20)
        
        # Clicks in last 30 days
        clicks_30d = EmailTracking.objects.filter(
            subscriber=subscriber,
            clicked_at__gte=timezone.now() - timedelta(days=30)
        ).count()
        
        score += min(clicks_30d * 10, 30)
        
        # Negative: Complaint or unsubscribe
        if subscriber.complaint_count > 0:
            score -= subscriber.complaint_count * 10
        
        return max(0, min(100, score))


# ============================================================
# CELERY TASKS
# ============================================================

"""
from celery import shared_task

@shared_task
def send_scheduled_campaigns():
    '''Send scheduled email campaigns'''
    from apps.email_marketing.models import EmailCampaign
    
    ready = EmailCampaign.objects.filter(
        status='scheduled',
        scheduled_send__lte=timezone.now()
    )
    
    for campaign in ready:
        subscribers = campaign.target_list.emailsubscriber_set.filter(is_subscribed=True)
        
        for subscriber in subscribers:
            send_campaign_email.delay(subscriber.id, campaign.id)

@shared_task
def track_email_opens():
    '''Track email opens from open pixels'''
    pass

@shared_task
def update_engagement_scores():
    '''Update subscriber engagement scores'''
    from apps.email_marketing.models import EmailSubscriber
    
    subscribers = EmailSubscriber.objects.filter(is_subscribed=True)
    
    for subscriber in subscribers:
        subscriber.score = EmailAutomationEngine.calculate_engagement_score(subscriber)
        subscriber.save()

# Add to CELERY_BEAT_SCHEDULE:
'send-email-campaigns': {
    'task': 'apps.email_marketing.tasks.send_scheduled_campaigns',
    'schedule': 300.0,  # Every 5 minutes
},
'update-engagement': {
    'task': 'apps.email_marketing.tasks.update_engagement_scores',
    'schedule': 86400.0,  # Daily
},
"""