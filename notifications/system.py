# Real-time Notifications System - Multi-Channel

from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta
import logging

logger = logging.getLogger('notifications')

# ============================================================
# NOTIFICATION MODELS
# ============================================================

class NotificationTemplate(models.Model):
    """Notification templates"""
    CHANNEL_CHOICES = [
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('push', 'Push Notification'),
        ('in_app', 'In-App'),
        ('whatsapp', 'WhatsApp'),
        ('telegram', 'Telegram'),
    ]
    
    EVENT_TYPE_CHOICES = [
        ('order_confirmed', 'Order Confirmed'),
        ('order_shipped', 'Order Shipped'),
        ('order_delivered', 'Order Delivered'),
        ('payment_received', 'Payment Received'),
        ('refund_processed', 'Refund Processed'),
        ('review_request', 'Review Request'),
        ('promotional', 'Promotional'),
        ('account_alert', 'Account Alert'),
        ('system_alert', 'System Alert'),
    ]
    
    # Template
    name = models.CharField(max_length=255)
    event_type = models.CharField(max_length=50, choices=EVENT_TYPE_CHOICES)
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)
    
    # Content
    subject = models.CharField(max_length=255, blank=True)
    body = models.TextField()
    cta_text = models.CharField(max_length=100, blank=True)
    cta_url = models.URLField(blank=True)
    
    # Variables
    variables = models.JSONField(default=list)  # {{order_id}}, {{customer_name}}
    
    # Status
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'notification_template'
        unique_together = ['event_type', 'channel']


class Notification(models.Model):
    """Individual notifications"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('queued', 'Queued'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
        ('bounced', 'Bounced'),
    ]
    
    # Notification
    notification_id = models.CharField(max_length=50, unique=True)
    
    # Recipient
    recipient = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE)
    
    # Template & Content
    template = models.ForeignKey(NotificationTemplate, on_delete=models.SET_NULL, null=True)
    channel = models.CharField(max_length=20)
    
    subject = models.CharField(max_length=255, blank=True)
    body = models.TextField()
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Metadata
    external_id = models.CharField(max_length=100, blank=True)  # From notification provider
    
    # Tracking
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    clicked_at = models.DateTimeField(null=True, blank=True)
    
    # Error
    error_message = models.TextField(blank=True)
    
    # Scheduling
    scheduled_for = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'notification'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'status']),
            models.Index(fields=['channel']),
        ]


class NotificationPreference(models.Model):
    """User notification preferences"""
    user = models.OneToOneField('users.CustomUser', on_delete=models.CASCADE)
    
    # Email
    email_enabled = models.BooleanField(default=True)
    email_frequency = models.CharField(
        max_length=20,
        choices=[('instant', 'Instant'), ('daily', 'Daily Digest'), ('weekly', 'Weekly')],
        default='instant'
    )
    
    # SMS
    sms_enabled = models.BooleanField(default=True)
    
    # Push
    push_enabled = models.BooleanField(default=True)
    
    # WhatsApp
    whatsapp_enabled = models.BooleanField(default=False)
    
    # Notification types
    order_updates = models.BooleanField(default=True)
    promotional = models.BooleanField(default=True)
    account_alerts = models.BooleanField(default=True)
    
    # Do not disturb
    dnd_enabled = models.BooleanField(default=False)
    dnd_start = models.TimeField(null=True, blank=True)
    dnd_end = models.TimeField(null=True, blank=True)
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'notification_preference'


class NotificationLog(models.Model):
    """Track notification history"""
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE)
    
    # Event
    event = models.CharField(max_length=50)  # sent, delivered, opened, clicked, bounced
    
    # Metadata
    metadata = models.JSONField(default=dict)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'notification_log'


# ============================================================
# NOTIFICATION ENGINE
# ============================================================

class NotificationEngine:
    """Send notifications across channels"""
    
    @staticmethod
    def trigger_notification(event_type, recipient, context=None):
        """Trigger notification for event"""
        from apps.notifications.models import NotificationTemplate, Notification, NotificationPreference
        import uuid
        
        # Get templates
        templates = NotificationTemplate.objects.filter(
            event_type=event_type,
            is_active=True
        )
        
        if not templates.exists():
            logger.warning(f'No templates found for event: {event_type}')
            return []
        
        # Check preferences
        try:
            prefs = NotificationPreference.objects.get(user=recipient)
        except:
            prefs = None
        
        notifications = []
        
        for template in templates:
            # Check if channel is enabled
            if not NotificationEngine.is_channel_enabled(prefs, template.channel):
                continue
            
            # Check DND
            if prefs and prefs.dnd_enabled:
                if NotificationEngine.is_in_dnd(prefs):
                    continue
            
            # Render content
            subject, body = NotificationEngine.render_template(template, context)
            
            # Create notification
            notification = Notification.objects.create(
                notification_id=f"NOT-{uuid.uuid4().hex[:8].upper()}",
                recipient=recipient,
                template=template,
                channel=template.channel,
                subject=subject,
                body=body,
            )
            
            # Queue for sending
            NotificationEngine.queue_notification(notification)
            
            notifications.append(notification)
        
        return notifications
    
    @staticmethod
    def is_channel_enabled(prefs, channel):
        """Check if channel is enabled"""
        if not prefs:
            return True
        
        channel_map = {
            'email': prefs.email_enabled,
            'sms': prefs.sms_enabled,
            'push': prefs.push_enabled,
            'whatsapp': prefs.whatsapp_enabled,
        }
        
        return channel_map.get(channel, True)
    
    @staticmethod
    def is_in_dnd(prefs):
        """Check if in do-not-disturb window"""
        if not prefs.dnd_enabled:
            return False
        
        current_time = timezone.now().time()
        
        if prefs.dnd_start and prefs.dnd_end:
            if prefs.dnd_start <= current_time <= prefs.dnd_end:
                return True
        
        return False
    
    @staticmethod
    def render_template(template, context):
        """Render template with context"""
        subject = template.subject
        body = template.body
        
        if context:
            for key, value in context.items():
                placeholder = f"{{{{{key}}}}}"
                subject = subject.replace(placeholder, str(value))
                body = body.replace(placeholder, str(value))
        
        return subject, body
    
    @staticmethod
    def queue_notification(notification):
        """Queue notification for sending"""
        from apps.notifications.tasks import send_notification
        
        notification.status = 'queued'
        notification.save()
        
        # Send via appropriate channel
        if notification.channel == 'email':
            send_notification.apply_async(args=[notification.id], countdown=5)
        elif notification.channel == 'sms':
            send_notification.apply_async(args=[notification.id], countdown=2)
        else:
            send_notification.apply_async(args=[notification.id])
    
    @staticmethod
    def send_via_email(notification):
        """Send notification via email"""
        from django.core.mail import send_mail
        
        try:
            send_mail(
                notification.subject,
                notification.body,
                'notifications@joankkfarm.com',
                [notification.recipient.email],
                html_message=notification.body,
            )
            
            notification.status = 'sent'
            notification.sent_at = timezone.now()
            notification.save()
            
            logger.info(f'Email sent: {notification.notification_id}')
            
            return True
        
        except Exception as e:
            notification.status = 'failed'
            notification.error_message = str(e)
            notification.save()
            
            logger.error(f'Email failed: {e}')
            
            return False
    
    @staticmethod
    def send_via_sms(notification):
        """Send notification via SMS"""
        from twilio.rest import Client
        
        try:
            account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
            auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
            
            client = Client(account_sid, auth_token)
            
            message = client.messages.create(
                body=notification.body,
                from_='+1234567890',  # Twilio number
                to=notification.recipient.phone_number,
            )
            
            notification.status = 'sent'
            notification.sent_at = timezone.now()
            notification.external_id = message.sid
            notification.save()
            
            logger.info(f'SMS sent: {notification.notification_id}')
            
            return True
        
        except Exception as e:
            notification.status = 'failed'
            notification.error_message = str(e)
            notification.save()
            
            logger.error(f'SMS failed: {e}')
            
            return False
    
    @staticmethod
    def send_via_push(notification):
        """Send push notification"""
        # Firebase Cloud Messaging
        try:
            import firebase_admin
            from firebase_admin import messaging
            
            message = messaging.Message(
                notification=messaging.Notification(
                    title=notification.subject,
                    body=notification.body,
                ),
                data={'notification_id': notification.notification_id},
            )
            
            # Send to user's devices
            response = messaging.send(message)
            
            notification.status = 'sent'
            notification.sent_at = timezone.now()
            notification.external_id = response
            notification.save()
            
            logger.info(f'Push sent: {notification.notification_id}')
            
            return True
        
        except Exception as e:
            notification.status = 'failed'
            notification.error_message = str(e)
            notification.save()
            
            logger.error(f'Push failed: {e}')
            
            return False


# ============================================================
# CELERY TASKS
# ============================================================

"""
from celery import shared_task

@shared_task
def send_notification(notification_id):
    '''Send queued notification'''
    from apps.notifications.models import Notification
    
    notification = Notification.objects.get(id=notification_id)
    
    if notification.channel == 'email':
        NotificationEngine.send_via_email(notification)
    elif notification.channel == 'sms':
        NotificationEngine.send_via_sms(notification)
    elif notification.channel == 'push':
        NotificationEngine.send_via_push(notification)

@shared_task
def retry_failed_notifications():
    '''Retry failed notifications'''
    from apps.notifications.models import Notification
    
    failed = Notification.objects.filter(
        status='failed',
        created_at__gte=timezone.now() - timedelta(hours=24)
    )
    
    for notification in failed:
        send_notification.delay(notification.id)

# Add to CELERY_BEAT_SCHEDULE:
'retry-notifications': {
    'task': 'apps.notifications.tasks.retry_failed_notifications',
    'schedule': 3600.0,  # Hourly
},
"""