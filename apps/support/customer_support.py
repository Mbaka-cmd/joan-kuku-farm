# Customer Support & Ticketing System

from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta
import logging

logger = logging.getLogger('support')

# ============================================================
# SUPPORT MODELS
# ============================================================

class SupportTicket(models.Model):
    """Customer support tickets"""
    STATUS_CHOICES = [
        ('new', 'New'),
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('waiting_customer', 'Waiting for Customer'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    CATEGORY_CHOICES = [
        ('billing', 'Billing'),
        ('shipping', 'Shipping'),
        ('product', 'Product Quality'),
        ('order', 'Order Issue'),
        ('account', 'Account'),
        ('technical', 'Technical'),
        ('other', 'Other'),
    ]
    
    # Ticket info
    ticket_id = models.CharField(max_length=50, unique=True)
    title = models.CharField(max_length=255)
    description = models.TextField()
    
    # Classification
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    
    # Customer
    customer = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE, related_name='support_tickets')
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=20, blank=True)
    
    # Reference
    order = models.ForeignKey('orders.Order', null=True, blank=True, on_delete=models.SET_NULL)
    product = models.ForeignKey('products.Product', null=True, blank=True, on_delete=models.SET_NULL)
    
    # Assignment
    assigned_to = models.ForeignKey(
        'users.CustomUser',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='assigned_tickets'
    )
    assigned_at = models.DateTimeField(null=True, blank=True)
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    
    # Stats
    response_count = models.IntegerField(default=0)
    resolution_time = models.IntegerField(null=True, blank=True)  # Minutes
    
    class Meta:
        db_table = 'support_ticket'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'priority']),
            models.Index(fields=['customer']),
            models.Index(fields=['assigned_to']),
        ]
    
    def save(self, *args, **kwargs):
        if not self.ticket_id:
            import uuid
            self.ticket_id = f"TKT-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)


class TicketResponse(models.Model):
    """Responses to support tickets"""
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name='responses')
    
    # Response
    author = models.ForeignKey('users.CustomUser', on_delete=models.SET_NULL, null=True)
    content = models.TextField()
    is_internal = models.BooleanField(default=False)  # Internal note
    
    # Status change
    status_change = models.CharField(
        max_length=20,
        choices=SupportTicket.STATUS_CHOICES,
        blank=True
    )
    
    # Attachments
    attachment = models.FileField(upload_to='support/%Y/%m/%d/', blank=True)
    
    # Satisfaction
    satisfaction_rating = models.IntegerField(null=True, blank=True, choices=[(i, i) for i in range(1, 6)])
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'ticket_response'
        ordering = ['created_at']


class SupportTemplate(models.Model):
    """Support response templates"""
    title = models.CharField(max_length=255)
    category = models.CharField(max_length=20, choices=SupportTicket.CATEGORY_CHOICES)
    content = models.TextField()
    
    # Variables
    variables = models.JSONField(default=list)  # {{var_name}}
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'support_template'


class SupportMetrics(models.Model):
    """Support team metrics"""
    support_staff = models.OneToOneField('users.CustomUser', on_delete=models.CASCADE)
    
    # Volume
    total_tickets = models.IntegerField(default=0)
    resolved_tickets = models.IntegerField(default=0)
    
    # Quality
    avg_satisfaction = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    avg_response_time = models.IntegerField(default=0)  # Minutes
    
    # Performance
    first_response_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # %
    resolution_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # %
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'support_metrics'


# ============================================================
# SUPPORT MANAGER
# ============================================================

class SupportManager:
    """Manage support tickets"""
    
    @staticmethod
    def create_ticket(customer, title, description, category, priority='medium', order=None, product=None):
        """Create new support ticket"""
        
        ticket = SupportTicket.objects.create(
            customer=customer,
            customer_email=customer.email,
            customer_phone=customer.phone_number,
            title=title,
            description=description,
            category=category,
            priority=priority,
            order=order,
            product=product,
        )
        
        logger.info(f'Ticket created: {ticket.ticket_id}')
        
        # Send confirmation email
        SupportManager.send_ticket_created_email(ticket)
        
        return ticket
    
    @staticmethod
    def assign_ticket(ticket, agent):
        """Assign ticket to support agent"""
        ticket.assigned_to = agent
        ticket.assigned_at = timezone.now()
        ticket.status = 'open'
        ticket.save()
        
        logger.info(f'Ticket {ticket.ticket_id} assigned to {agent.email}')
    
    @staticmethod
    def add_response(ticket, author, content, status_change=None, is_internal=False):
        """Add response to ticket"""
        response = TicketResponse.objects.create(
            ticket=ticket,
            author=author,
            content=content,
            is_internal=is_internal,
            status_change=status_change,
        )
        
        # Update ticket
        ticket.response_count += 1
        
        if status_change:
            ticket.status = status_change
            
            if status_change == 'resolved':
                ticket.resolved_at = timezone.now()
                
                # Calculate resolution time
                duration = ticket.resolved_at - ticket.created_at
                ticket.resolution_time = int(duration.total_seconds() / 60)  # In minutes
            
            elif status_change == 'closed':
                ticket.closed_at = timezone.now()
        
        ticket.save()
        
        # Send notification
        if not is_internal:
            SupportManager.send_response_email(ticket, response)
        
        return response
    
    @staticmethod
    def auto_assign_ticket(ticket):
        """Automatically assign ticket to least busy agent"""
        from apps.users.models import CustomUser
        
        # Get support staff with lowest open ticket count
        agents = CustomUser.objects.filter(
            groups__name='Support Staff'
        ).annotate(
            open_count=Count('assigned_tickets', filter=Q(assigned_tickets__status__in=['new', 'open', 'in_progress']))
        ).order_by('open_count').first()
        
        if agents:
            SupportManager.assign_ticket(ticket, agents)
    
    @staticmethod
    def get_ticket_analytics(start_date=None, end_date=None):
        """Get support analytics"""
        if not start_date:
            start_date = timezone.now() - timedelta(days=30)
        if not end_date:
            end_date = timezone.now()
        
        tickets = SupportTicket.objects.filter(
            created_at__range=[start_date, end_date]
        )
        
        from django.db.models import Avg, Count, Q
        
        analytics = {
            'total_tickets': tickets.count(),
            'resolved_tickets': tickets.filter(status='resolved').count(),
            'avg_resolution_time': tickets.filter(
                resolution_time__isnull=False
            ).aggregate(Avg('resolution_time'))['resolution_time__avg'] or 0,
            'by_category': {},
            'by_priority': {},
            'by_status': {},
        }
        
        # By category
        for category, name in SupportTicket.CATEGORY_CHOICES:
            count = tickets.filter(category=category).count()
            analytics['by_category'][name] = count
        
        # By priority
        for priority, name in SupportTicket.PRIORITY_CHOICES:
            count = tickets.filter(priority=priority).count()
            analytics['by_priority'][name] = count
        
        # By status
        for status, name in SupportTicket.STATUS_CHOICES:
            count = tickets.filter(status=status).count()
            analytics['by_status'][name] = count
        
        return analytics
    
    @staticmethod
    def send_ticket_created_email(ticket):
        """Send ticket creation confirmation"""
        from django.core.mail import send_mail
        
        subject = f"Support Ticket Created - {ticket.ticket_id}"
        message = f"""
        Thank you for contacting support.
        
        Ticket ID: {ticket.ticket_id}
        Subject: {ticket.title}
        Status: {ticket.get_status_display()}
        
        We'll respond to your ticket shortly.
        """
        
        send_mail(
            subject,
            message,
            'support@joankkfarm.com',
            [ticket.customer_email],
        )
    
    @staticmethod
    def send_response_email(ticket, response):
        """Send response notification"""
        from django.core.mail import send_mail
        
        subject = f"Response to your ticket - {ticket.ticket_id}"
        message = response.content
        
        send_mail(
            subject,
            message,
            'support@joankkfarm.com',
            [ticket.customer_email],
        )


# ============================================================
# CELERY TASKS
# ============================================================

"""
from celery import shared_task

@shared_task
def auto_assign_new_tickets():
    '''Auto-assign new support tickets'''
    from apps.support.models import SupportTicket
    
    new_tickets = SupportTicket.objects.filter(
        status='new',
        assigned_to__isnull=True
    )
    
    for ticket in new_tickets:
        SupportManager.auto_assign_ticket(ticket)

@shared_task
def send_satisfaction_survey():
    '''Send satisfaction survey for resolved tickets'''
    from apps.support.models import SupportTicket
    
    resolved = SupportTicket.objects.filter(
        status='resolved',
        resolved_at__gte=timezone.now() - timedelta(hours=1)
    )
    
    for ticket in resolved:
        # Send survey email
        pass

@shared_task
def generate_support_metrics():
    '''Generate support team metrics'''
    from apps.support.models import SupportMetrics, SupportTicket
    from apps.users.models import CustomUser
    from django.db.models import Avg, Q
    
    agents = CustomUser.objects.filter(groups__name='Support Staff')
    
    for agent in agents:
        tickets = SupportTicket.objects.filter(assigned_to=agent)
        
        metrics, created = SupportMetrics.objects.get_or_create(support_staff=agent)
        
        metrics.total_tickets = tickets.count()
        metrics.resolved_tickets = tickets.filter(status='resolved').count()
        metrics.avg_response_time = tickets.filter(
            resolution_time__isnull=False
        ).aggregate(Avg('resolution_time'))['resolution_time__avg'] or 0
        
        # Calculate satisfaction
        responses = TicketResponse.objects.filter(
            ticket__assigned_to=agent,
            satisfaction_rating__isnull=False
        )
        
        if responses.exists():
            metrics.avg_satisfaction = responses.aggregate(Avg('satisfaction_rating'))['satisfaction_rating__avg']
        
        metrics.save()

# Add to CELERY_BEAT_SCHEDULE:
'auto-assign-tickets': {
    'task': 'apps.support.tasks.auto_assign_new_tickets',
    'schedule': 300.0,  # Every 5 minutes
},
'send-satisfaction-survey': {
    'task': 'apps.support.tasks.send_satisfaction_survey',
    'schedule': 3600.0,  # Hourly
},
'generate-support-metrics': {
    'task': 'apps.support.tasks.generate_support_metrics',
    'schedule': 3600.0,  # Hourly
},
"""