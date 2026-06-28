# A/B Testing & Experimentation Framework

from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta
import random
import hashlib
from decimal import Decimal

# ============================================================
# A/B TEST MODELS
# ============================================================

class ABTest(models.Model):
    """A/B test configuration"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
    ]
    
    # Basic info
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Variants
    control_name = models.CharField(max_length=100, default='Control')
    treatment_name = models.CharField(max_length=100, default='Treatment')
    
    # Configuration
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    test_type = models.CharField(max_length=50)  # e.g., 'ui', 'pricing', 'flow'
    
    # Targeting
    target_audience = models.JSONField(default=dict)  # Targeting rules
    include_percentage = models.IntegerField(default=100)  # % of traffic to include
    allocation = models.IntegerField(default=50)  # % in treatment group
    
    # Scheduling
    start_date = models.DateTimeField()
    end_date = models.DateTimeField(null=True, blank=True)
    
    # Metrics
    primary_metric = models.CharField(max_length=100)  # e.g., 'conversion_rate'
    secondary_metrics = models.JSONField(default=list)
    
    # Statistics
    min_sample_size = models.IntegerField(default=100)
    confidence_level = models.IntegerField(default=95)  # %
    
    # Metadata
    created_by = models.ForeignKey('users.CustomUser', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'ab_test'
        ordering = ['-created_at']


class ABTestVariant(models.Model):
    """A/B test variant details"""
    test = models.ForeignKey(ABTest, on_delete=models.CASCADE, related_name='variants')
    
    name = models.CharField(max_length=100)  # 'control' or 'treatment'
    variant_key = models.CharField(max_length=50)
    
    # Configuration
    config = models.JSONField(default=dict)  # Variant-specific config
    
    # Metrics
    participants = models.IntegerField(default=0)
    conversions = models.IntegerField(default=0)
    revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    class Meta:
        db_table = 'ab_test_variant'
        unique_together = ['test', 'name']


class ABTestParticipant(models.Model):
    """Track test participants"""
    test = models.ForeignKey(ABTest, on_delete=models.CASCADE)
    user = models.ForeignKey('users.CustomUser', null=True, blank=True, on_delete=models.SET_NULL)
    
    # Assignment
    variant = models.ForeignKey(ABTestVariant, on_delete=models.SET_NULL, null=True)
    assigned_at = models.DateTimeField(auto_now_add=True)
    
    # Tracking
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    
    class Meta:
        db_table = 'ab_test_participant'
        unique_together = ['test', 'user', 'ip_address']


class ABTestEvent(models.Model):
    """Track test events"""
    test = models.ForeignKey(ABTest, on_delete=models.CASCADE)
    participant = models.ForeignKey(ABTestParticipant, on_delete=models.CASCADE)
    
    # Event
    event_type = models.CharField(max_length=50)  # e.g., 'view', 'click', 'conversion'
    event_name = models.CharField(max_length=100)
    
    # Value
    value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    properties = models.JSONField(default=dict)
    
    # Timestamp
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'ab_test_event'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['test', 'event_type']),
            models.Index(fields=['participant']),
        ]


# ============================================================
# A/B TEST ENGINE
# ============================================================

class ABTestEngine:
    """Manage A/B tests"""
    
    @staticmethod
    def assign_variant(test, user, ip_address, user_agent):
        """Assign user to control or treatment"""
        from apps.ab_testing.models import ABTestParticipant, ABTestVariant
        
        # Check if user already assigned
        try:
            participant = ABTestParticipant.objects.get(
                test=test,
                user=user if user else None,
                ip_address=ip_address
            )
            return participant
        except ABTestParticipant.DoesNotExist:
            pass
        
        # Check if in target audience
        if not ABTestEngine.matches_criteria(test, user):
            # Assign to control
            control_variant = ABTestVariant.objects.get(test=test, name='control')
            participant = ABTestParticipant.objects.create(
                test=test,
                user=user,
                variant=control_variant,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            return participant
        
        # Randomly assign to variant
        if random.randint(1, 100) <= test.allocation:
            variant_name = 'treatment'
        else:
            variant_name = 'control'
        
        variant = ABTestVariant.objects.get(test=test, name=variant_name)
        
        participant = ABTestParticipant.objects.create(
            test=test,
            user=user,
            variant=variant,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        
        # Update variant count
        variant.participants += 1
        variant.save()
        
        return participant
    
    @staticmethod
    def matches_criteria(test, user):
        """Check if user matches test criteria"""
        criteria = test.target_audience
        
        if not criteria:
            return True  # No criteria = all users
        
        # Check user attributes
        if 'min_orders' in criteria:
            user_orders = user.order_set.count() if user else 0
            if user_orders < criteria['min_orders']:
                return False
        
        if 'min_spend' in criteria:
            user_spend = user.order_set.aggregate(
                total=models.Sum('total_amount')
            )['total'] or 0
            if user_spend < criteria['min_spend']:
                return False
        
        return True
    
    @staticmethod
    def track_event(participant, event_type, event_name, value=None, properties=None):
        """Track an event"""
        from apps.ab_testing.models import ABTestEvent
        
        event = ABTestEvent.objects.create(
            test=participant.test,
            participant=participant,
            event_type=event_type,
            event_name=event_name,
            value=value,
            properties=properties or {},
        )
        
        # Update variant metrics
        if event_type == 'conversion':
            participant.variant.conversions += 1
            if value:
                participant.variant.revenue += Decimal(str(value))
            participant.variant.save()
        
        return event
    
    @staticmethod
    def get_test_results(test):
        """Calculate test results and statistics"""
        from apps.ab_testing.models import ABTestVariant, ABTestEvent
        
        variants = test.variants.all()
        results = {}
        
        for variant in variants:
            # Count events
            conversions = variant.conversions
            participants = variant.participants
            
            # Calculate metrics
            conversion_rate = (conversions / participants * 100) if participants > 0 else 0
            avg_revenue = (variant.revenue / participants) if participants > 0 else 0
            
            results[variant.name] = {
                'participants': participants,
                'conversions': conversions,
                'conversion_rate': conversion_rate,
                'revenue': float(variant.revenue),
                'avg_revenue': float(avg_revenue),
            }
        
        # Calculate statistical significance
        if len(variants) == 2:
            control = results[test.control_name]
            treatment = results[test.treatment_name]
            
            # Simple chi-square test for conversion rate
            significance = ABTestEngine.calculate_significance(
                control['conversions'],
                control['participants'],
                treatment['conversions'],
                treatment['participants'],
            )
            
            results['significance'] = significance
            results['winner'] = None
            
            if significance > (test.confidence_level / 100):
                if treatment['conversion_rate'] > control['conversion_rate']:
                    results['winner'] = 'treatment'
                else:
                    results['winner'] = 'control'
        
        return results
    
    @staticmethod
    def calculate_significance(control_conversions, control_n, 
                             treatment_conversions, treatment_n):
        """Calculate statistical significance (simplified chi-square)"""
        from scipy import stats
        
        # Create contingency table
        contingency = [
            [control_conversions, control_n - control_conversions],
            [treatment_conversions, treatment_n - treatment_conversions],
        ]
        
        try:
            chi2, p_value, dof, expected = stats.chi2_contingency(contingency)
            return p_value  # P-value < 0.05 = significant at 95%
        except:
            return 1.0  # Not enough data


# ============================================================
# A/B TEST MIDDLEWARE
# ============================================================

class ABTestMiddleware:
    """Middleware to track A/B tests"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        from apps.ab_testing.models import ABTest
        
        # Get active tests
        active_tests = ABTest.objects.filter(
            status='active',
            start_date__lte=timezone.now()
        ).exclude(end_date__isnull=False, end_date__lt=timezone.now())
        
        # Assign user to variants
        for test in active_tests:
            ABTestEngine.assign_variant(
                test,
                request.user if request.user.is_authenticated else None,
                self.get_client_ip(request),
                request.META.get('HTTP_USER_AGENT', '')
            )
        
        response = self.get_response(request)
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
# API ENDPOINTS
# ============================================================

"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

class ABTestViewSet(viewsets.ModelViewSet):
    queryset = ABTest.objects.all()
    permission_classes = [IsAdminUser]
    
    @action(detail=True)
    def results(self, request, pk=None):
        '''Get test results'''
        test = self.get_object()
        results = ABTestEngine.get_test_results(test)
        return Response(results)
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        '''Complete a test'''
        test = self.get_object()
        test.status = 'completed'
        test.end_date = timezone.now()
        test.save()
        return Response({'message': 'Test completed'})

class ABTestEventViewSet(viewsets.ViewSet):
    @action(detail=False, methods=['post'])
    def track(self, request):
        '''Track an event'''
        test_id = request.data.get('test_id')
        event_type = request.data.get('event_type')
        event_name = request.data.get('event_name')
        value = request.data.get('value')
        
        test = ABTest.objects.get(id=test_id)
        participant = ABTestParticipant.objects.get(
            test=test,
            user=request.user
        )
        
        event = ABTestEngine.track_event(
            participant, event_type, event_name, value
        )
        
        return Response({'event_id': event.id})
"""

# ============================================================
# EXAMPLE: PRICING TEST
# ============================================================

"""
Create a pricing A/B test:

1. Create test:
   test = ABTest.objects.create(
       name='Pricing Test',
       description='Test two pricing tiers',
       test_type='pricing',
       primary_metric='conversion_rate',
       start_date=timezone.now(),
       allocation=50,  # 50% treatment
   )

2. Create variants:
   control = ABTestVariant.objects.create(
       test=test,
       name='control',
       config={'price': 15}
   )
   
   treatment = ABTestVariant.objects.create(
       test=test,
       name='treatment',
       config={'price': 12}
   )

3. Show price in template:
   {% if request.ab_test_variant.config.price %}
       Price: KES {{ request.ab_test_variant.config.price }}
   {% endif %}

4. Track conversion:
   ABTestEngine.track_event(
       participant,
       'conversion',
       'purchase',
       value=order.total_amount
   )

5. Analyze results:
   results = ABTestEngine.get_test_results(test)
"""