# Customer Data Platform (CDP) - Unified Customer Profile

from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta
import logging

logger = logging.getLogger('cdp')

# ============================================================
# CDP MODELS
# ============================================================

class UnifiedCustomerProfile(models.Model):
    """Unified 360° customer profile"""
    customer = models.OneToOneField('users.CustomUser', on_delete=models.CASCADE)
    
    # Identity
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    
    # Demographics
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    age_range = models.CharField(max_length=20, blank=True)
    gender = models.CharField(max_length=20, blank=True)
    
    # Lifecycle
    lifecycle_stage = models.CharField(
        max_length=50,
        choices=[
            ('prospect', 'Prospect'),
            ('lead', 'Lead'),
            ('customer', 'Customer'),
            ('loyal', 'Loyal'),
            ('vip', 'VIP'),
            ('at_risk', 'At Risk'),
            ('churned', 'Churned'),
        ]
    )
    
    # Engagement
    first_interaction = models.DateTimeField()
    last_interaction = models.DateTimeField()
    total_interactions = models.IntegerField(default=0)
    
    # Value
    lifetime_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    predicted_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Preferences
    communication_preferences = models.JSONField(default=dict)
    product_interests = models.JSONField(default=list)
    
    # Attributes (extensible)
    custom_attributes = models.JSONField(default=dict)
    
    # Segments
    segments = models.JSONField(default=list)
    
    # Last update
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'unified_customer_profile'


class CustomerEvent(models.Model):
    """Track all customer events"""
    EVENT_TYPES = [
        ('page_view', 'Page View'),
        ('click', 'Click'),
        ('form_submit', 'Form Submit'),
        ('purchase', 'Purchase'),
        ('review', 'Review'),
        ('support_ticket', 'Support Ticket'),
        ('email_open', 'Email Open'),
        ('email_click', 'Email Click'),
        ('cart_add', 'Cart Add'),
        ('cart_remove', 'Cart Remove'),
        ('wishlist_add', 'Wishlist Add'),
    ]
    
    customer = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE)
    
    # Event
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES)
    event_id = models.CharField(max_length=100)
    
    # Context
    source = models.CharField(max_length=100)  # web, mobile, email, etc
    device_type = models.CharField(max_length=50, blank=True)
    browser = models.CharField(max_length=100, blank=True)
    
    # Properties
    properties = models.JSONField(default=dict)
    
    # Referrer
    referrer = models.CharField(max_length=255, blank=True)
    
    # Timestamp
    timestamp = models.DateTimeField()
    
    class Meta:
        db_table = 'customer_event'
        indexes = [
            models.Index(fields=['customer', '-timestamp']),
            models.Index(fields=['event_type']),
        ]


class CustomerSegment(models.Model):
    """Dynamic customer segments"""
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Rules
    rules = models.JSONField()  # Segment definition
    
    # Size
    member_count = models.IntegerField(default=0)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Update
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'customer_segment'


class CustomerAttribute(models.Model):
    """Custom customer attributes"""
    customer = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE)
    
    # Attribute
    key = models.CharField(max_length=255)
    value = models.TextField()
    value_type = models.CharField(max_length=50)  # string, number, boolean, date
    
    # Source
    source = models.CharField(max_length=100)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'customer_attribute'
        unique_together = ['customer', 'key']


class CDPSegmentMembership(models.Model):
    """Track segment membership"""
    customer = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE)
    segment = models.ForeignKey(CustomerSegment, on_delete=models.CASCADE)
    
    # Timing
    joined_at = models.DateTimeField()
    left_at = models.DateTimeField(null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'cdp_segment_membership'
        unique_together = ['customer', 'segment']


class CDPAuditLog(models.Model):
    """Audit trail for customer data"""
    customer = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE)
    
    # Change
    action = models.CharField(max_length=100)
    field_changed = models.CharField(max_length=255, blank=True)
    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)
    
    # User
    changed_by = models.ForeignKey('users.CustomUser', null=True, blank=True, 
                                   on_delete=models.SET_NULL, related_name='cdp_changes')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'cdp_audit_log'
        ordering = ['-created_at']


# ============================================================
# CDP ENGINE
# ============================================================

class CDPEngine:
    """Manage customer data platform"""
    
    @staticmethod
    def build_unified_profile(customer):
        """Build unified customer profile"""
        from apps.orders.models import Order
        from apps.cdp.models import UnifiedCustomerProfile, CustomerEvent
        
        profile, created = UnifiedCustomerProfile.objects.get_or_create(customer=customer)
        
        # Basic info
        profile.email = customer.email
        profile.first_name = customer.first_name
        profile.last_name = customer.last_name
        profile.phone = customer.phone_number
        
        # Lifecycle
        orders = customer.order_set.all()
        if orders.exists():
            profile.lifecycle_stage = 'customer'
        else:
            profile.lifecycle_stage = 'prospect'
        
        # Interactions
        events = CustomerEvent.objects.filter(customer=customer)
        profile.total_interactions = events.count()
        
        if events.exists():
            profile.first_interaction = events.order_by('timestamp').first().timestamp
            profile.last_interaction = events.order_by('-timestamp').first().timestamp
        
        # Value
        total_value = orders.aggregate(models.Sum('total_amount'))['total_amount__sum'] or 0
        profile.lifetime_value = total_value
        
        # Value-based segmentation
        if total_value >= 10000:
            profile.lifecycle_stage = 'vip'
        elif total_value >= 5000:
            profile.lifecycle_stage = 'loyal'
        
        profile.save()
        
        logger.info(f'Unified profile built for {customer.email}')
        
        return profile
    
    @staticmethod
    def track_event(customer, event_type, properties=None, source='web'):
        """Track customer event"""
        from apps.cdp.models import CustomerEvent
        import uuid
        
        event = CustomerEvent.objects.create(
            customer=customer,
            event_type=event_type,
            event_id=str(uuid.uuid4()),
            source=source,
            properties=properties or {},
            timestamp=timezone.now(),
        )
        
        logger.debug(f'Event tracked: {event_type} for {customer.email}')
        
        return event
    
    @staticmethod
    def evaluate_segments(customer):
        """Evaluate customer segments"""
        from apps.cdp.models import CustomerSegment, CDPSegmentMembership
        
        segments = CustomerSegment.objects.filter(is_active=True)
        
        for segment in segments:
            # Check if customer matches segment rules
            matches = CDPEngine.evaluate_segment_rules(customer, segment.rules)
            
            if matches:
                # Add to segment
                membership, created = CDPSegmentMembership.objects.get_or_create(
                    customer=customer,
                    segment=segment,
                    defaults={'joined_at': timezone.now()}
                )
                
                if not membership.is_active:
                    membership.is_active = True
                    membership.left_at = None
                    membership.save()
            else:
                # Remove from segment if member
                try:
                    membership = CDPSegmentMembership.objects.get(
                        customer=customer,
                        segment=segment
                    )
                    membership.is_active = False
                    membership.left_at = timezone.now()
                    membership.save()
                except:
                    pass
    
    @staticmethod
    def evaluate_segment_rules(customer, rules):
        """Evaluate if customer matches segment rules"""
        from apps.orders.models import Order
        
        try:
            profile = customer.userprofile
        except:
            return False
        
        # Simple rule evaluation
        # This would be more sophisticated in production
        
        for rule in rules.get('conditions', []):
            field = rule.get('field')
            operator = rule.get('operator')
            value = rule.get('value')
            
            if field == 'lifetime_value':
                customer_value = Order.objects.filter(customer=customer).aggregate(
                    models.Sum('total_amount')
                )['total_amount__sum'] or 0
                
                if operator == 'gte':
                    if not (customer_value >= value):
                        return False
                elif operator == 'lte':
                    if not (customer_value <= value):
                        return False
            
            elif field == 'purchase_frequency':
                order_count = Order.objects.filter(customer=customer).count()
                
                if operator == 'gte':
                    if not (order_count >= value):
                        return False
        
        return True
    
    @staticmethod
    def get_customer_profile_api(customer):
        """Get complete customer profile for API/integration"""
        from apps.cdp.models import UnifiedCustomerProfile, CDPSegmentMembership
        
        try:
            profile = UnifiedCustomerProfile.objects.get(customer=customer)
        except:
            CDPEngine.build_unified_profile(customer)
            profile = UnifiedCustomerProfile.objects.get(customer=customer)
        
        segments = CDPSegmentMembership.objects.filter(
            customer=customer,
            is_active=True
        ).values_list('segment__name', flat=True)
        
        return {
            'customer_id': customer.id,
            'email': profile.email,
            'name': f"{profile.first_name} {profile.last_name}",
            'lifecycle_stage': profile.lifecycle_stage,
            'lifetime_value': float(profile.lifetime_value),
            'total_interactions': profile.total_interactions,
            'segments': list(segments),
            'preferences': profile.communication_preferences,
            'interests': profile.product_interests,
            'attributes': profile.custom_attributes,
        }


# ============================================================
# CELERY TASKS
# ============================================================

"""
from celery import shared_task

@shared_task
def rebuild_unified_profiles():
    '''Rebuild all unified customer profiles'''
    from apps.users.models import CustomUser
    
    customers = CustomUser.objects.filter(is_active=True)
    
    for customer in customers:
        CDPEngine.build_unified_profile(customer)

@shared_task
def evaluate_all_segments():
    '''Evaluate customer segments'''
    from apps.users.models import CustomUser
    
    customers = CustomUser.objects.filter(is_active=True)
    
    for customer in customers:
        CDPEngine.evaluate_segments(customer)

@shared_task
def sync_external_data():
    '''Sync customer data with external platforms'''
    from apps.cdp.models import UnifiedCustomerProfile
    
    profiles = UnifiedCustomerProfile.objects.all()
    
    for profile in profiles:
        # Sync to external CDP (e.g., Segment, mParticle)
        pass

# Add to CELERY_BEAT_SCHEDULE:
'rebuild-profiles': {
    'task': 'apps.cdp.tasks.rebuild_unified_profiles',
    'schedule': 604800.0,  # Weekly
},
'evaluate-segments': {
    'task': 'apps.cdp.tasks.evaluate_all_segments',
    'schedule': 86400.0,  # Daily
},
'sync-external': {
    'task': 'apps.cdp.tasks.sync_external_data',
    'schedule': 3600.0,  # Hourly
},
"""