# Advanced Security & DDoS Protection System

from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta
import logging

logger = logging.getLogger('security')

# ============================================================
# SECURITY MODELS
# ============================================================

class SecurityPolicy(models.Model):
    """Security policies"""
    POLICY_TYPE = [
        ('password', 'Password Policy'),
        ('ip_whitelist', 'IP Whitelist'),
        ('rate_limit', 'Rate Limiting'),
        ('session', 'Session Policy'),
        ('mfa', 'Multi-Factor Auth'),
    ]
    
    name = models.CharField(max_length=255)
    policy_type = models.CharField(max_length=50, choices=POLICY_TYPE)
    description = models.TextField(blank=True)
    
    # Configuration
    config = models.JSONField(default=dict)
    
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'security_policy'


class IPWhitelist(models.Model):
    """IP whitelisting"""
    ip_address = models.GenericIPAddressField()
    description = models.CharField(max_length=255, blank=True)
    
    # Duration
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Trust
    trust_level = models.IntegerField(choices=[(i, str(i)) for i in range(1, 6)])  # 1-5
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'ip_whitelist'
        indexes = [
            models.Index(fields=['ip_address']),
        ]


class IPBlacklist(models.Model):
    """IP blacklisting"""
    ip_address = models.GenericIPAddressField()
    reason = models.CharField(max_length=255)
    
    # Duration
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Severity
    severity = models.CharField(
        max_length=20,
        choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('critical', 'Critical')]
    )
    
    # Source
    reported_by = models.CharField(max_length=100, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'ip_blacklist'
        indexes = [
            models.Index(fields=['ip_address']),
        ]


class SecurityIncident(models.Model):
    """Security incidents"""
    INCIDENT_TYPE = [
        ('brute_force', 'Brute Force Attack'),
        ('ddos', 'DDoS Attack'),
        ('injection', 'SQL Injection'),
        ('xss', 'XSS Attack'),
        ('malware', 'Malware Detection'),
        ('unauthorized_access', 'Unauthorized Access'),
        ('data_breach', 'Data Breach'),
        ('other', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('detected', 'Detected'),
        ('investigating', 'Investigating'),
        ('resolved', 'Resolved'),
        ('escalated', 'Escalated'),
    ]
    
    # Incident
    incident_type = models.CharField(max_length=50, choices=INCIDENT_TYPE)
    description = models.TextField()
    
    # Details
    source_ip = models.GenericIPAddressField(null=True, blank=True)
    target = models.CharField(max_length=500, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='detected')
    
    # Response
    responded_by = models.ForeignKey('users.CustomUser', null=True, blank=True, on_delete=models.SET_NULL)
    response_notes = models.TextField(blank=True)
    
    # Severity
    severity = models.CharField(max_length=20, choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('critical', 'Critical')])
    
    # Dates
    detected_at = models.DateTimeField()
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'security_incident'
        ordering = ['-severity', '-detected_at']


class RateLimitRule(models.Model):
    """Rate limiting rules"""
    endpoint = models.CharField(max_length=500)
    
    # Limits
    requests_per_minute = models.IntegerField()
    requests_per_hour = models.IntegerField()
    requests_per_day = models.IntegerField()
    
    # Scope
    scope = models.CharField(
        max_length=20,
        choices=[('ip', 'By IP'), ('user', 'By User'), ('global', 'Global')]
    )
    
    # Action
    action = models.CharField(
        max_length=20,
        choices=[('throttle', 'Throttle'), ('block', 'Block'), ('challenge', 'Challenge')]
    )
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'rate_limit_rule'
        unique_together = ['endpoint', 'scope']


class RateLimitViolation(models.Model):
    """Track rate limit violations"""
    rule = models.ForeignKey(RateLimitRule, on_delete=models.CASCADE)
    
    # Violator
    ip_address = models.GenericIPAddressField()
    user = models.ForeignKey('users.CustomUser', null=True, blank=True, on_delete=models.SET_NULL)
    
    # Violation
    requests_made = models.IntegerField()
    limit = models.IntegerField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'rate_limit_violation'
        indexes = [
            models.Index(fields=['ip_address', '-created_at']),
        ]


# ============================================================
# SECURITY ENGINE
# ============================================================

class SecurityEngine:
    """Advanced security operations"""
    
    @staticmethod
    def check_ip_reputation(ip_address):
        """Check IP reputation"""
        from apps.security.models import IPBlacklist, IPWhitelist
        
        # Check whitelist first
        whitelisted = IPWhitelist.objects.filter(
            ip_address=ip_address,
            expires_at__gt=timezone.now()
        ).exists()
        
        if whitelisted:
            return {'status': 'trusted', 'trust_score': 100}
        
        # Check blacklist
        blacklisted = IPBlacklist.objects.filter(
            ip_address=ip_address,
            expires_at__gt=timezone.now()
        ).first()
        
        if blacklisted:
            return {
                'status': 'blocked',
                'trust_score': 0,
                'reason': blacklisted.reason,
                'severity': blacklisted.severity,
            }
        
        return {'status': 'unknown', 'trust_score': 50}
    
    @staticmethod
    def detect_brute_force(ip_address):
        """Detect brute force attacks"""
        from apps.security.models import SecurityIncident
        from apps.audit_log.models import AuditLog
        
        # Check failed login attempts
        failed_logins = AuditLog.objects.filter(
            action='login_failed',
            ip_address=ip_address,
            created_at__gte=timezone.now() - timedelta(minutes=15)
        ).count()
        
        if failed_logins >= 5:
            SecurityEngine.create_incident(
                incident_type='brute_force',
                description=f'Brute force attack detected from {ip_address}',
                source_ip=ip_address,
                severity='high'
            )
            
            # Block IP temporarily
            SecurityEngine.block_ip(ip_address, 'Brute force attack', hours=1)
            
            return True
        
        return False
    
    @staticmethod
    def detect_injection_attack(input_data):
        """Detect SQL injection attempts"""
        sql_keywords = ['UNION', 'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP', 'EXEC']
        
        for keyword in sql_keywords:
            if keyword.upper() in input_data.upper():
                return True
        
        return False
    
    @staticmethod
    def detect_xss_attack(input_data):
        """Detect XSS attempts"""
        xss_patterns = ['<script', 'javascript:', 'onerror=', 'onclick=']
        
        for pattern in xss_patterns:
            if pattern.lower() in input_data.lower():
                return True
        
        return False
    
    @staticmethod
    def create_incident(incident_type, description, source_ip=None, severity='medium'):
        """Create security incident"""
        from apps.security.models import SecurityIncident
        
        incident = SecurityIncident.objects.create(
            incident_type=incident_type,
            description=description,
            source_ip=source_ip,
            severity=severity,
            detected_at=timezone.now(),
        )
        
        logger.warning(f'Security incident created: {incident_type} - {description}')
        
        return incident
    
    @staticmethod
    def block_ip(ip_address, reason, hours=24):
        """Block IP address"""
        from apps.security.models import IPBlacklist
        
        blacklist, created = IPBlacklist.objects.get_or_create(
            ip_address=ip_address,
            defaults={
                'reason': reason,
                'severity': 'high',
                'expires_at': timezone.now() + timedelta(hours=hours),
            }
        )
        
        logger.warning(f'IP blocked: {ip_address} - {reason}')
        
        return blacklist
    
    @staticmethod
    def check_rate_limit(ip_address, endpoint):
        """Check if IP violates rate limits"""
        from apps.security.models import RateLimitRule, RateLimitViolation
        
        rules = RateLimitRule.objects.filter(
            endpoint=endpoint,
            is_active=True
        )
        
        for rule in rules:
            # Count requests in last minute
            recent = RateLimitViolation.objects.filter(
                rule=rule,
                ip_address=ip_address,
                created_at__gte=timezone.now() - timedelta(minutes=1)
            ).count()
            
            if recent >= rule.requests_per_minute:
                RateLimitViolation.objects.create(
                    rule=rule,
                    ip_address=ip_address,
                    requests_made=recent,
                    limit=rule.requests_per_minute,
                )
                
                if rule.action == 'block':
                    SecurityEngine.block_ip(ip_address, f'Rate limit violation on {endpoint}', hours=1)
                    return {'blocked': True}
                elif rule.action == 'challenge':
                    return {'challenge': True, 'type': 'captcha'}
                else:
                    return {'throttled': True}
        
        return {'allowed': True}


# ============================================================
# CELERY TASKS
# ============================================================

"""
from celery import shared_task

@shared_task
def scan_for_threats():
    '''Scan for security threats'''
    # Monitor logs for suspicious activity
    pass

@shared_task
def check_rate_limits():
    '''Enforce rate limits'''
    from apps.security.models import RateLimitViolation
    
    # Check violations and block if necessary
    violations = RateLimitViolation.objects.filter(
        created_at__gte=timezone.now() - timedelta(minutes=1)
    )
    
    for violation in violations:
        if violation.requests_made >= violation.limit * 2:
            SecurityEngine.block_ip(
                violation.ip_address,
                f'Excessive rate limit violations',
                hours=1
            )

@shared_task
def cleanup_expired_blocks():
    '''Clean up expired IP blocks'''
    from apps.security.models import IPBlacklist
    
    IPBlacklist.objects.filter(
        expires_at__lt=timezone.now()
    ).delete()

# Add to CELERY_BEAT_SCHEDULE:
'scan-threats': {
    'task': 'apps.security.tasks.scan_for_threats',
    'schedule': 600.0,  # Every 10 minutes
},
'check-rate-limits': {
    'task': 'apps.security.tasks.check_rate_limits',
    'schedule': 60.0,  # Every minute
},
'cleanup-blocks': {
    'task': 'apps.security.tasks.cleanup_expired_blocks',
    'schedule': 3600.0,  # Hourly
},
"""