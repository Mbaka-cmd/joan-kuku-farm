# Compliance & Legal Documentation System - GDPR, Privacy, Legal

from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta
import logging

logger = logging.getLogger('compliance')

# ============================================================
# COMPLIANCE MODELS
# ============================================================

class TermsAndConditions(models.Model):
    """Terms and conditions management"""
    version = models.CharField(max_length=20)
    content = models.TextField()
    
    # Availability
    is_active = models.BooleanField(default=True)
    effective_date = models.DateTimeField()
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'terms_and_conditions'
        ordering = ['-effective_date']


class PrivacyPolicy(models.Model):
    """Privacy policy management"""
    version = models.CharField(max_length=20)
    content = models.TextField()
    
    # Sections
    data_collection = models.TextField()
    data_usage = models.TextField()
    data_sharing = models.TextField()
    data_retention = models.TextField()
    user_rights = models.TextField()
    
    # Compliance
    gdpr_compliant = models.BooleanField(default=True)
    ccpa_compliant = models.BooleanField(default=True)
    
    # Availability
    is_active = models.BooleanField(default=True)
    effective_date = models.DateTimeField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'privacy_policy'
        ordering = ['-effective_date']


class UserConsent(models.Model):
    """Track user consent to policies"""
    CONSENT_TYPE_CHOICES = [
        ('terms', 'Terms & Conditions'),
        ('privacy', 'Privacy Policy'),
        ('marketing', 'Marketing Communications'),
        ('cookies', 'Cookie Policy'),
    ]
    
    user = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE)
    consent_type = models.CharField(max_length=20, choices=CONSENT_TYPE_CHOICES)
    
    # Consent
    version = models.CharField(max_length=20)
    consented = models.BooleanField(default=True)
    
    # IP & user agent
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    
    # Dates
    consented_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'user_consent'
        unique_together = ['user', 'consent_type', 'version']


class DataDeletionRequest(models.Model):
    """GDPR right to be forgotten"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('denied', 'Denied'),
    ]
    
    user = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE)
    
    # Request
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Processing
    processed_at = models.DateTimeField(null=True, blank=True)
    denial_reason = models.TextField(blank=True)
    
    # Verification
    email_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    
    # Dates
    requested_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'data_deletion_request'
        ordering = ['-requested_at']


class DataExportRequest(models.Model):
    """GDPR data portability"""
    user = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE)
    
    # Export
    file = models.FileField(upload_to='gdpr_exports/%Y/%m/%d/', null=True, blank=True)
    format = models.CharField(max_length=20, choices=[('json', 'JSON'), ('csv', 'CSV')])
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[('pending', 'Pending'), ('ready', 'Ready'), ('downloaded', 'Downloaded')]
    )
    
    # Download
    downloaded_at = models.DateTimeField(null=True, blank=True)
    download_count = models.IntegerField(default=0)
    
    # Dates
    requested_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    
    class Meta:
        db_table = 'data_export_request'
        ordering = ['-requested_at']


class AuditLog(models.Model):
    """Compliance audit log"""
    ACTIONS = [
        ('user_created', 'User Created'),
        ('user_updated', 'User Updated'),
        ('data_accessed', 'Data Accessed'),
        ('data_modified', 'Data Modified'),
        ('data_deleted', 'Data Deleted'),
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('export', 'Data Exported'),
    ]
    
    # Action
    action = models.CharField(max_length=30, choices=ACTIONS)
    
    # User
    user = models.ForeignKey('users.CustomUser', on_delete=models.SET_NULL, null=True)
    
    # Details
    resource_type = models.CharField(max_length=100)
    resource_id = models.CharField(max_length=100)
    
    # Change details
    old_value = models.JSONField(null=True, blank=True)
    new_value = models.JSONField(null=True, blank=True)
    
    # IP & user agent
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    
    # Timestamp
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'audit_log'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['action']),
        ]


# ============================================================
# COMPLIANCE MANAGER
# ============================================================

class ComplianceManager:
    """Manage compliance"""
    
    @staticmethod
    def request_data_deletion(user, reason):
        """Request data deletion (GDPR)"""
        from apps.compliance.models import DataDeletionRequest
        
        request = DataDeletionRequest.objects.create(
            user=user,
            reason=reason,
        )
        
        # Send verification email
        ComplianceManager.send_deletion_verification_email(request)
        
        logger.info(f'Data deletion request created for user {user.id}')
        
        return request
    
    @staticmethod
    def verify_deletion_request(request, token):
        """Verify email for deletion request"""
        # In production, verify token against sent email
        request.email_verified = True
        request.verified_at = timezone.now()
        request.save()
        
        logger.info(f'Deletion request verified: {request.id}')
    
    @staticmethod
    def process_data_deletion(deletion_request):
        """Process GDPR data deletion"""
        from apps.users.models import CustomUser
        
        deletion_request.status = 'processing'
        deletion_request.save()
        
        user = deletion_request.user
        
        try:
            # Delete/anonymize user data
            user.email = f'deleted_{user.id}@deleted.local'
            user.first_name = 'Deleted'
            user.last_name = 'User'
            user.phone_number = ''
            user.address = ''
            user.is_active = False
            user.save()
            
            # Delete related data
            # Keep minimal data for legal/financial compliance
            
            deletion_request.status = 'completed'
            deletion_request.completed_at = timezone.now()
            deletion_request.save()
            
            logger.info(f'Data deletion completed for user {user.id}')
            
        except Exception as e:
            deletion_request.status = 'denied'
            deletion_request.denial_reason = str(e)
            deletion_request.save()
            logger.error(f'Data deletion failed: {e}')
    
    @staticmethod
    def request_data_export(user, format='json'):
        """Request GDPR data export"""
        from apps.compliance.models import DataExportRequest
        
        export_request = DataExportRequest.objects.create(
            user=user,
            format=format,
            expires_at=timezone.now() + timedelta(days=30),
        )
        
        # Generate export
        ComplianceManager.generate_data_export(export_request)
        
        logger.info(f'Data export requested for user {user.id}')
        
        return export_request
    
    @staticmethod
    def generate_data_export(export_request):
        """Generate user data export"""
        from django.core.files.base import ContentFile
        import json
        
        user = export_request.user
        
        # Collect all user data
        data = {
            'user': {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'phone': user.phone_number,
                'created_at': user.date_joined.isoformat(),
            },
            'orders': [],
            'reviews': [],
            'addresses': [],
        }
        
        # Orders
        for order in user.order_set.all():
            data['orders'].append({
                'order_id': order.order_id,
                'total': str(order.total_amount),
                'status': order.status,
                'created_at': order.created_at.isoformat(),
            })
        
        # Reviews
        for review in user.productreview_set.all():
            data['reviews'].append({
                'product': review.product.name,
                'rating': review.rating,
                'content': review.content,
                'created_at': review.created_at.isoformat(),
            })
        
        # Export
        if export_request.format == 'json':
            content = json.dumps(data, indent=2)
            filename = f'user_data_{user.id}.json'
        else:
            # CSV format
            content = str(data)
            filename = f'user_data_{user.id}.csv'
        
        export_request.file = ContentFile(
            content.encode('utf-8'),
            name=filename
        )
        export_request.status = 'ready'
        export_request.save()
    
    @staticmethod
    def log_action(action, user, resource_type, resource_id, old_value=None, new_value=None, ip_address='', user_agent=''):
        """Log action for audit trail"""
        from apps.compliance.models import AuditLog
        
        AuditLog.objects.create(
            action=action,
            user=user,
            resource_type=resource_type,
            resource_id=resource_id,
            old_value=old_value,
            new_value=new_value,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    
    @staticmethod
    def send_deletion_verification_email(deletion_request):
        """Send deletion verification email"""
        from django.core.mail import send_mail
        
        subject = 'Confirm Data Deletion Request'
        message = f"""
        You requested to delete your account and data.
        
        This action is permanent and cannot be undone.
        
        Click here to confirm: [verification link]
        
        If you did not make this request, ignore this email.
        """
        
        send_mail(
            subject,
            message,
            'privacy@joankkfarm.com',
            [deletion_request.user.email],
        )


# ============================================================
# CELERY TASKS
# ============================================================

"""
from celery import shared_task

@shared_task
def process_pending_deletions():
    '''Process verified deletion requests after 30 days'''
    from apps.compliance.models import DataDeletionRequest
    
    cutoff = timezone.now() - timedelta(days=30)
    
    pending = DataDeletionRequest.objects.filter(
        status='pending',
        verified_at__lt=cutoff
    )
    
    for req in pending:
        ComplianceManager.process_data_deletion(req)

@shared_task
def cleanup_expired_exports():
    '''Delete expired data exports'''
    from apps.compliance.models import DataExportRequest
    
    DataExportRequest.objects.filter(expires_at__lt=timezone.now()).delete()

@subdask_task
def send_consent_reminders():
    '''Send periodic consent reminders'''
    from apps.users.models import CustomUser
    
    # Send reminders to users who haven't consented
    pass

# Add to CELERY_BEAT_SCHEDULE:
'process-pending-deletions': {
    'task': 'apps.compliance.tasks.process_pending_deletions',
    'schedule': 86400.0,  # Daily
},
'cleanup-expired-exports': {
    'task': 'apps.compliance.tasks.cleanup_expired_exports',
    'schedule': 604800.0,  # Weekly
},
"""