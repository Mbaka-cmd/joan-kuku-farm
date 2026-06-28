# Customer Churn Prediction & Retention System

from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta
import logging

logger = logging.getLogger('churn')

# ============================================================
# CHURN MODELS
# ============================================================

class CustomerRiskScore(models.Model):
    """Customer churn risk assessment"""
    RISK_LEVEL = [
        ('low', 'Low Risk'),
        ('medium', 'Medium Risk'),
        ('high', 'High Risk'),
        ('critical', 'Critical'),
    ]
    
    customer = models.OneToOneField('users.CustomUser', on_delete=models.CASCADE)
    
    # Risk score (0-100)
    risk_score = models.DecimalField(max_digits=5, decimal_places=2)
    risk_level = models.CharField(max_length=20, choices=RISK_LEVEL)
    
    # Factors
    days_since_purchase = models.IntegerField()
    avg_order_frequency = models.IntegerField()  # days
    purchase_frequency_trend = models.DecimalField(max_digits=5, decimal_places=2)  # -100 to 100
    
    # Engagement
    email_engagement = models.DecimalField(max_digits=5, decimal_places=2)  # 0-100
    app_usage = models.DecimalField(max_digits=5, decimal_places=2)  # 0-100
    review_sentiment = models.DecimalField(max_digits=3, decimal_places=2)  # -1 to 1
    
    # Value metrics
    customer_lifetime_value = models.DecimalField(max_digits=12, decimal_places=2)
    predictive_lifetime_value = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Predictions
    churn_probability = models.DecimalField(max_digits=5, decimal_places=4)  # 0-1
    estimated_churn_date = models.DateField(null=True, blank=True)
    
    # Actions
    intervention_recommended = models.BooleanField(default=False)
    retention_strategy = models.CharField(
        max_length=100,
        choices=[
            ('discount', 'Personalized Discount'),
            ('loyalty', 'Loyalty Incentive'),
            ('engagement', 'Re-engagement Campaign'),
            ('vip', 'VIP Treatment'),
            ('none', 'No Action'),
        ],
        default='none'
    )
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'customer_risk_score'
        ordering = ['-risk_score']


class RetentionCampaign(models.Model):
    """Retention campaigns"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
    ]
    
    # Campaign
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Target
    risk_level_min = models.CharField(max_length=20, default='high')
    customer_segment = models.CharField(max_length=100, blank=True)
    
    # Offer
    offer_type = models.CharField(max_length=50)
    offer_value = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Campaign details
    channels = models.JSONField(default=list)  # email, sms, in_app, push
    message = models.TextField()
    
    # Schedule
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Results
    target_customers = models.IntegerField(default=0)
    sent_count = models.IntegerField(default=0)
    open_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    conversion_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    roi = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'retention_campaign'
        ordering = ['-start_date']


class CampaignParticipant(models.Model):
    """Track campaign participation"""
    campaign = models.ForeignKey(RetentionCampaign, on_delete=models.CASCADE)
    customer = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE)
    
    # Engagement
    sent = models.BooleanField(default=False)
    opened = models.BooleanField(default=False)
    clicked = models.BooleanField(default=False)
    converted = models.BooleanField(default=False)
    
    # Offer usage
    offer_redeemed = models.BooleanField(default=False)
    redemption_date = models.DateTimeField(null=True, blank=True)
    
    # Results
    order_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'campaign_participant'
        unique_together = ['campaign', 'customer']


class ChurnInsight(models.Model):
    """Insights about churn patterns"""
    # Pattern
    churn_reason = models.CharField(max_length=255)
    customer_segment = models.CharField(max_length=100)
    
    # Metrics
    total_churned = models.IntegerField()
    avg_lifetime_value = models.DecimalField(max_digits=12, decimal_places=2)
    warning_signs = models.JSONField(default=list)
    
    # Trend
    churn_rate = models.DecimalField(max_digits=5, decimal_places=2)  # %
    trend = models.CharField(
        max_length=20,
        choices=[('increasing', 'Increasing'), ('stable', 'Stable'), ('decreasing', 'Decreasing')]
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'churn_insight'
        ordering = ['-created_at']


# ============================================================
# CHURN PREDICTION ENGINE
# ============================================================

class ChurnPredictionEngine:
    """Predict and prevent customer churn"""
    
    @staticmethod
    def calculate_risk_score(customer):
        """Calculate churn risk for customer"""
        from apps.orders.models import Order
        from apps.reviews.models import ProductReview
        
        risk_factors = {}
        
        # 1. Days since last purchase
        last_order = customer.order_set.order_by('-created_at').first()
        if last_order:
            days_since = (timezone.now() - last_order.created_at).days
            risk_factors['days_since_purchase'] = days_since
            
            # Risk increases over time
            if days_since > 180:
                risk_factors['purchase_recency'] = 30  # High risk
            elif days_since > 90:
                risk_factors['purchase_recency'] = 15
            elif days_since > 30:
                risk_factors['purchase_recency'] = 5
            else:
                risk_factors['purchase_recency'] = 0
        else:
            # No purchase history
            days_since = (timezone.now() - customer.date_joined).days
            if days_since > 90:
                risk_factors['purchase_recency'] = 30
        
        # 2. Purchase frequency
        orders = customer.order_set.all()
        if orders.count() >= 2:
            first_order = orders.order_by('created_at').first()
            last_order = orders.order_by('-created_at').first()
            days_active = (last_order.created_at - first_order.created_at).days
            frequency = orders.count() / max(days_active / 30, 1)
            
            risk_factors['purchase_frequency'] = frequency
            
            if frequency < 0.5:  # Less than 1 order per 2 months
                risk_factors['frequency_risk'] = 20
            else:
                risk_factors['frequency_risk'] = 0
        
        # 3. Email engagement
        risk_factors['email_engagement'] = 0  # Would integrate with email service
        
        # 4. Review sentiment
        reviews = ProductReview.objects.filter(customer=customer, status='approved')
        if reviews.exists():
            avg_rating = reviews.aggregate(models.Avg('rating'))['rating__avg'] or 3
            
            if avg_rating < 3:
                risk_factors['review_sentiment'] = 15
            else:
                risk_factors['review_sentiment'] = 0
        
        # Calculate total risk score
        total_score = sum(risk_factors.values())
        
        return {
            'score': min(100, total_score),
            'factors': risk_factors,
        }
    
    @staticmethod
    def update_all_risk_scores():
        """Update risk scores for all customers"""
        from apps.users.models import CustomUser
        from apps.churn.models import CustomerRiskScore
        
        customers = CustomUser.objects.filter(is_active=True)
        
        for customer in customers:
            risk_data = ChurnPredictionEngine.calculate_risk_score(customer)
            
            # Determine risk level
            score = risk_data['score']
            if score >= 75:
                risk_level = 'critical'
            elif score >= 50:
                risk_level = 'high'
            elif score >= 25:
                risk_level = 'medium'
            else:
                risk_level = 'low'
            
            risk_score, created = CustomerRiskScore.objects.get_or_create(customer=customer)
            
            risk_score.risk_score = score
            risk_score.risk_level = risk_level
            
            # Set intervention
            if risk_level in ['high', 'critical']:
                risk_score.intervention_recommended = True
                risk_score.retention_strategy = ChurnPredictionEngine.select_retention_strategy(customer, risk_level)
            else:
                risk_score.intervention_recommended = False
            
            risk_score.save()
    
    @staticmethod
    def select_retention_strategy(customer, risk_level):
        """Select best retention strategy"""
        from apps.orders.models import Order
        
        total_spent = customer.order_set.aggregate(models.Sum('total_amount'))['total_amount__sum'] or 0
        order_count = customer.order_set.count()
        
        if total_spent > 10000:
            # High-value customers
            return 'vip'
        elif risk_level == 'critical' and order_count == 1:
            # First-time buyer at risk
            return 'discount'
        elif order_count >= 5:
            # Loyal but at risk
            return 'loyalty'
        else:
            # Disengage customer
            return 'engagement'
    
    @staticmethod
    def create_retention_campaign(risk_level):
        """Create campaign for at-risk customers"""
        from apps.churn.models import RetentionCampaign, CustomerRiskScore
        
        at_risk_customers = CustomerRiskScore.objects.filter(
            risk_level=risk_level,
            intervention_recommended=True
        ).count()
        
        if at_risk_customers < 10:
            return None  # Not enough customers
        
        campaign = RetentionCampaign.objects.create(
            name=f'{risk_level.title()} Risk Retention Campaign',
            risk_level_min=risk_level,
            offer_type='discount',
            offer_value=Decimal('10.00'),
            channels=['email', 'sms'],
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            target_customers=at_risk_customers,
        )
        
        logger.info(f'Retention campaign created: {campaign.name}')
        
        return campaign
    
    @staticmethod
    def predict_churn_cohort(cohort_size=30):
        """Predict which customers might churn in next 30 days"""
        from apps.churn.models import CustomerRiskScore
        
        at_risk = CustomerRiskScore.objects.filter(
            risk_level__in=['high', 'critical'],
            churn_probability__gte=0.6
        ).order_by('-churn_probability')[:cohort_size]
        
        predictions = [
            {
                'customer': risk.customer.email,
                'risk_score': float(risk.risk_score),
                'churn_probability': float(risk.churn_probability),
                'retention_strategy': risk.retention_strategy,
            }
            for risk in at_risk
        ]
        
        return predictions


# ============================================================
# CELERY TASKS
# ============================================================

"""
from celery import shared_task

@shared_task
def update_churn_risk_scores():
    '''Update churn risk scores daily'''
    ChurnPredictionEngine.update_all_risk_scores()

@shared_task
def create_retention_campaigns():
    '''Create retention campaigns for at-risk customers'''
    for risk_level in ['high', 'critical']:
        ChurnPredictionEngine.create_retention_campaign(risk_level)

@shared_task
def send_retention_offers():
    '''Send retention offers to at-risk customers'''
    from apps.churn.models import RetentionCampaign, CampaignParticipant
    
    active_campaigns = RetentionCampaign.objects.filter(
        status='active',
        start_date__lte=timezone.now(),
        end_date__gt=timezone.now()
    )
    
    for campaign in active_campaigns:
        # Get at-risk customers
        # Send offers
        pass

# Add to CELERY_BEAT_SCHEDULE:
'update-churn-scores': {
    'task': 'apps.churn.tasks.update_churn_risk_scores',
    'schedule': 86400.0,  # Daily
},
'create-retention-campaigns': {
    'task': 'apps.churn.tasks.create_retention_campaigns',
    'schedule': 604800.0,  # Weekly
},
'send-retention-offers': {
    'task': 'apps.churn.tasks.send_retention_offers',
    'schedule': 3600.0,  # Hourly
},
"""