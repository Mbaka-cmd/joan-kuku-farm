# Advanced Fraud Detection System - Machine Learning Based

from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta
import logging

logger = logging.getLogger('fraud')

# ============================================================
# FRAUD DETECTION MODELS
# ============================================================

class FraudRule(models.Model):
    """Fraud detection rules"""
    RULE_TYPE_CHOICES = [
        ('velocity', 'Velocity Check'),
        ('amount', 'Amount Anomaly'),
        ('pattern', 'Pattern Anomaly'),
        ('card', 'Card Fraud'),
        ('account', 'Account Abuse'),
        ('ip', 'IP Blacklist'),
    ]
    
    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    # Rule
    name = models.CharField(max_length=255)
    rule_type = models.CharField(max_length=20, choices=RULE_TYPE_CHOICES)
    description = models.TextField(blank=True)
    
    # Configuration
    condition = models.JSONField()  # Rule condition
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    
    # Action
    action = models.CharField(
        max_length=20,
        choices=[
            ('flag', 'Flag'),
            ('review', 'Manual Review'),
            ('block', 'Block'),
            ('challenge', 'Challenge'),
        ]
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'fraud_rule'
        ordering = ['-severity', '-created_at']


class FraudAlert(models.Model):
    """Fraud alerts and flags"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('reviewing', 'Under Review'),
        ('confirmed', 'Confirmed Fraud'),
        ('dismissed', 'Dismissed'),
        ('resolved', 'Resolved'),
    ]
    
    # Alert
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, related_name='fraud_alerts')
    
    # Detection
    triggered_rules = models.JSONField(default=list)
    fraud_score = models.DecimalField(max_digits=5, decimal_places=2)  # 0-100
    
    # Risk assessment
    severity = models.CharField(max_length=20, choices=FraudRule.SEVERITY_CHOICES)
    risk_factors = models.JSONField(default=list)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Investigation
    investigated_by = models.ForeignKey('users.CustomUser', null=True, blank=True, on_delete=models.SET_NULL)
    investigation_notes = models.TextField(blank=True)
    
    # Dates
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'fraud_alert'
        ordering = ['-fraud_score', '-created_at']
        indexes = [
            models.Index(fields=['status', '-fraud_score']),
        ]


class DeviceFingerprint(models.Model):
    """Device fingerprinting for fraud detection"""
    user = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE)
    
    # Device
    device_id = models.CharField(max_length=255, unique=True)
    device_type = models.CharField(max_length=50)  # mobile, desktop, tablet
    browser = models.CharField(max_length=100)
    os = models.CharField(max_length=100)
    
    # IP
    ip_address = models.GenericIPAddressField()
    country = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    
    # Trust score
    trust_score = models.IntegerField(default=50)  # 0-100
    
    # Usage
    is_trusted = models.BooleanField(default=False)
    last_seen = models.DateTimeField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'device_fingerprint'
        unique_together = ['user', 'device_id']


class FraudBlacklist(models.Model):
    """Blacklisted items"""
    ITEM_TYPE_CHOICES = [
        ('card', 'Card Number'),
        ('ip', 'IP Address'),
        ('email', 'Email'),
        ('phone', 'Phone'),
        ('device', 'Device'),
    ]
    
    item_type = models.CharField(max_length=20, choices=ITEM_TYPE_CHOICES)
    item_value = models.CharField(max_length=255, unique=True)
    
    # Info
    reason = models.TextField()
    reported_by = models.ForeignKey('users.CustomUser', null=True, blank=True, on_delete=models.SET_NULL)
    
    # Validity
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'fraud_blacklist'
        indexes = [
            models.Index(fields=['item_type', 'item_value']),
        ]


# ============================================================
# FRAUD DETECTION ENGINE
# ============================================================

class FraudDetectionEngine:
    """Detect and prevent fraud"""
    
    @staticmethod
    def check_order_fraud(order):
        """Check order for fraud indicators"""
        from apps.fraud.models import FraudRule, FraudAlert
        
        fraud_score = 0
        triggered_rules = []
        risk_factors = []
        
        # Get active rules
        rules = FraudRule.objects.filter(is_active=True)
        
        for rule in rules:
            if FraudDetectionEngine.check_rule(rule, order):
                fraud_score += FraudDetectionEngine.get_rule_score(rule)
                triggered_rules.append(rule.name)
                risk_factors.append(rule.description)
        
        # Create alert if fraud score high
        if fraud_score >= 50:
            alert = FraudAlert.objects.create(
                order=order,
                triggered_rules=triggered_rules,
                fraud_score=fraud_score,
                severity=FraudDetectionEngine.get_severity(fraud_score),
                risk_factors=risk_factors,
            )
            
            logger.warning(f'Fraud alert created for order {order.order_id}: score {fraud_score}')
            
            # Block or review based on score
            if fraud_score >= 80:
                order.status = 'fraud_review'
                order.save()
            
            return alert
        
        return None
    
    @staticmethod
    def check_rule(rule, order):
        """Check if rule applies to order"""
        condition = rule.condition
        
        if rule.rule_type == 'velocity':
            # Check if customer made many orders recently
            recent_orders = order.customer.order_set.filter(
                created_at__gte=timezone.now() - timedelta(hours=1)
            ).count()
            return recent_orders > condition.get('max_orders_per_hour', 5)
        
        elif rule.rule_type == 'amount':
            # Check if order amount is unusual
            avg_order_value = order.customer.order_set.aggregate(
                models.Avg('total_amount')
            )['total_amount__avg'] or 0
            
            threshold = condition.get('std_devs', 3)
            return order.total_amount > avg_order_value * threshold
        
        elif rule.rule_type == 'pattern':
            # Check for unusual patterns
            days_since_last = (timezone.now() - (
                order.customer.order_set.order_by('-created_at').first().created_at
                if order.customer.order_set.exists() else timezone.now()
            )).days
            
            return days_since_last > condition.get('unusual_gap_days', 30)
        
        elif rule.rule_type == 'card':
            # Check card fraud patterns
            if hasattr(order, 'payment'):
                card_num = order.payment.card_last_four
                recent_cards = order.customer.order_set.filter(
                    payment__card_last_four=card_num,
                    created_at__gte=timezone.now() - timedelta(days=30)
                ).count()
                
                return recent_cards > condition.get('max_uses', 10)
        
        elif rule.rule_type == 'ip':
            # Check IP blacklist
            from apps.fraud.models import FraudBlacklist
            return FraudBlacklist.objects.filter(
                item_type='ip',
                item_value=order.customer_ip,
                is_active=True
            ).exists()
        
        return False
    
    @staticmethod
    def get_rule_score(rule):
        """Get fraud score contribution for rule"""
        scores = {
            'low': 10,
            'medium': 25,
            'high': 50,
            'critical': 100,
        }
        return scores.get(rule.severity, 10)
    
    @staticmethod
    def get_severity(score):
        """Get severity from fraud score"""
        if score >= 80:
            return 'critical'
        elif score >= 60:
            return 'high'
        elif score >= 40:
            return 'medium'
        else:
            return 'low'
    
    @staticmethod
    def check_device(user, device_id, ip_address):
        """Check device trust"""
        from apps.fraud.models import DeviceFingerprint
        
        try:
            fingerprint = DeviceFingerprint.objects.get(
                user=user,
                device_id=device_id
            )
            
            # Update last seen
            fingerprint.last_seen = timezone.now()
            fingerprint.save()
            
            return fingerprint.trust_score
        
        except DeviceFingerprint.DoesNotExist:
            # New device - lower trust
            return 30
    
    @staticmethod
    def is_blacklisted(item_type, value):
        """Check if item is blacklisted"""
        from apps.fraud.models import FraudBlacklist
        
        return FraudBlacklist.objects.filter(
            item_type=item_type,
            item_value=value,
            is_active=True,
            expires_at__gt=timezone.now()
        ).exists()


# ============================================================
# CELERY TASKS
# ============================================================

"""
from celery import shared_task

@shared_task
def check_pending_alerts():
    '''Review pending fraud alerts'''
    from apps.fraud.models import FraudAlert
    
    pending = FraudAlert.objects.filter(status='pending').order_by('-fraud_score')[:50]
    
    for alert in pending:
        # Manual review or auto-action based on score
        if alert.fraud_score >= 90:
            alert.status = 'confirmed'
            alert.save()
            # Cancel order
            alert.order.status = 'cancelled'
            alert.order.save()

@shared_task
def update_device_trust_scores():
    '''Update device trust scores'''
    from apps.fraud.models import DeviceFingerprint
    
    devices = DeviceFingerprint.objects.all()
    
    for device in devices:
        # Check for fraud on this device
        fraud_count = device.user.fraud_alerts.filter(
            status='confirmed',
            created_at__gte=timezone.now() - timedelta(days=30)
        ).count()
        
        device.trust_score = max(10, 100 - (fraud_count * 20))
        device.save()

# Add to CELERY_BEAT_SCHEDULE:
'check-pending-alerts': {
    'task': 'apps.fraud.tasks.check_pending_alerts',
    'schedule': 3600.0,  # Hourly
},
'update-trust-scores': {
    'task': 'apps.fraud.tasks.update_device_trust_scores',
    'schedule': 86400.0,  # Daily
},
"""