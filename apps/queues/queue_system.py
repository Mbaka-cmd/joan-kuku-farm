# Queue Management System - Advanced Job Processing & Scheduling

from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta
import logging

logger = logging.getLogger('queues')

# ============================================================
# QUEUE MODELS
# ============================================================

class JobQueue(models.Model):
    """Job queue configuration"""
    PRIORITY_CHOICES = [
        ('critical', 'Critical'),
        ('high', 'High'),
        ('normal', 'Normal'),
        ('low', 'Low'),
    ]
    
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    
    # Configuration
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='normal')
    max_retries = models.IntegerField(default=3)
    timeout_seconds = models.IntegerField(default=300)
    
    # Rate limiting
    rate_limit = models.IntegerField(null=True, blank=True)  # Jobs per minute
    max_concurrent = models.IntegerField(default=10)
    
    # Monitoring
    total_jobs = models.IntegerField(default=0)
    successful_jobs = models.IntegerField(default=0)
    failed_jobs = models.IntegerField(default=0)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'job_queue'
        ordering = ['-priority']


class QueuedJob(models.Model):
    """Individual queued job"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('retry', 'Retry'),
        ('dead_letter', 'Dead Letter'),
    ]
    
    # Job info
    queue = models.ForeignKey(JobQueue, on_delete=models.CASCADE)
    job_id = models.CharField(max_length=100, unique=True)
    
    # Task
    task_name = models.CharField(max_length=255)
    task_args = models.JSONField(default=list)
    task_kwargs = models.JSONField(default=dict)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Scheduling
    scheduled_time = models.DateTimeField(null=True, blank=True)
    
    # Processing
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Retry info
    retry_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=3)
    
    # Result
    result = models.JSONField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    
    # Processing info
    processed_by = models.CharField(max_length=100, blank=True)  # Worker ID
    
    # Priority
    priority = models.CharField(max_length=20, default='normal')
    
    # Metadata
    user = models.ForeignKey('users.CustomUser', null=True, blank=True, on_delete=models.SET_NULL)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'queued_job'
        ordering = ['-priority', 'created_at']
        indexes = [
            models.Index(fields=['queue', 'status']),
            models.Index(fields=['status']),
            models.Index(fields=['-priority', 'created_at']),
        ]


class JobLog(models.Model):
    """Job execution log"""
    job = models.ForeignKey(QueuedJob, on_delete=models.CASCADE, related_name='logs')
    
    # Log entry
    level = models.CharField(max_length=20)  # DEBUG, INFO, WARNING, ERROR
    message = models.TextField()
    
    # Details
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'job_log'
        ordering = ['timestamp']


class DeadLetterQueue(models.Model):
    """Dead letter queue for failed jobs"""
    original_job = models.OneToOneField(QueuedJob, on_delete=models.CASCADE)
    
    # Failure info
    final_error = models.TextField()
    failure_count = models.IntegerField(default=0)
    
    # Manual intervention
    requires_review = models.BooleanField(default=True)
    reviewed_by = models.ForeignKey('users.CustomUser', null=True, blank=True, on_delete=models.SET_NULL)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    # Resolution
    resolved = models.BooleanField(default=False)
    resolution_notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'dead_letter_queue'
        ordering = ['-created_at']


# ============================================================
# QUEUE MANAGER
# ============================================================

class QueueManager:
    """Manage job queues"""
    
    @staticmethod
    def enqueue_job(queue_name, task_name, args=None, kwargs=None, priority='normal', scheduled_time=None, user=None):
        """Enqueue a job"""
        from apps.queues.models import JobQueue, QueuedJob
        
        try:
            queue = JobQueue.objects.get(name=queue_name)
        except JobQueue.DoesNotExist:
            raise ValueError(f'Queue "{queue_name}" not found')
        
        import uuid
        job_id = f'job_{uuid.uuid4().hex[:12]}'
        
        job = QueuedJob.objects.create(
            queue=queue,
            job_id=job_id,
            task_name=task_name,
            task_args=args or [],
            task_kwargs=kwargs or {},
            priority=priority,
            scheduled_time=scheduled_time or timezone.now(),
            user=user,
        )
        
        queue.total_jobs += 1
        queue.save()
        
        logger.info(f'Job enqueued: {job_id}')
        
        return job
    
    @staticmethod
    def process_job(job):
        """Process a queued job"""
        from apps.queues.models import QueuedJob
        import importlib
        
        try:
            job.status = 'processing'
            job.started_at = timezone.now()
            job.save()
            
            # Import and execute task
            module_name, function_name = job.task_name.rsplit('.', 1)
            module = importlib.import_module(module_name)
            task_func = getattr(module, function_name)
            
            # Execute
            result = task_func(*job.task_args, **job.task_kwargs)
            
            # Mark complete
            job.status = 'completed'
            job.completed_at = timezone.now()
            job.result = {'success': True, 'result': str(result)}
            job.save()
            
            job.queue.successful_jobs += 1
            job.queue.save()
            
            logger.info(f'Job completed: {job.job_id}')
            
            return result
        
        except Exception as e:
            job.error_message = str(e)
            job.retry_count += 1
            
            if job.retry_count <= job.max_retries:
                job.status = 'retry'
                # Schedule retry with backoff
                backoff = 2 ** job.retry_count
                job.scheduled_time = timezone.now() + timedelta(seconds=backoff)
            else:
                job.status = 'failed'
                QueueManager.move_to_dead_letter(job)
            
            job.save()
            
            job.queue.failed_jobs += 1
            job.queue.save()
            
            logger.error(f'Job failed: {job.job_id}, Error: {str(e)}')
    
    @staticmethod
    def move_to_dead_letter(job):
        """Move failed job to dead letter queue"""
        from apps.queues.models import DeadLetterQueue
        
        DeadLetterQueue.objects.create(
            original_job=job,
            final_error=job.error_message,
            failure_count=job.retry_count,
        )
    
    @staticmethod
    def get_queue_stats(queue_name):
        """Get queue statistics"""
        from apps.queues.models import JobQueue, QueuedJob
        
        queue = JobQueue.objects.get(name=queue_name)
        
        stats = {
            'name': queue.name,
            'priority': queue.priority,
            'total_jobs': queue.total_jobs,
            'successful': queue.successful_jobs,
            'failed': queue.failed_jobs,
            'pending': QueuedJob.objects.filter(queue=queue, status='pending').count(),
            'processing': QueuedJob.objects.filter(queue=queue, status='processing').count(),
            'retry': QueuedJob.objects.filter(queue=queue, status='retry').count(),
        }
        
        return stats
    
    @staticmethod
    def get_system_health():
        """Get overall queue system health"""
        from apps.queues.models import JobQueue, QueuedJob
        
        total_pending = QueuedJob.objects.filter(status='pending').count()
        total_processing = QueuedJob.objects.filter(status='processing').count()
        total_failed = QueuedJob.objects.filter(status='failed').count()
        
        queues = JobQueue.objects.all()
        total_jobs = sum(q.total_jobs for q in queues)
        successful_rate = (sum(q.successful_jobs for q in queues) / total_jobs * 100) if total_jobs > 0 else 0
        
        health = {
            'pending_jobs': total_pending,
            'processing_jobs': total_processing,
            'failed_jobs': total_failed,
            'success_rate': successful_rate,
            'status': 'healthy' if successful_rate > 95 and total_failed < 10 else 'degraded',
        }
        
        return health


# ============================================================
# CELERY TASKS
# ============================================================

"""
from celery import shared_task

@shared_task
def process_queue():
    '''Process queued jobs'''
    from apps.queues.models import QueuedJob, JobQueue
    
    # Get pending jobs
    pending = QueuedJob.objects.filter(
        status='pending',
        scheduled_time__lte=timezone.now()
    ).order_by('-priority')[:100]
    
    for job in pending:
        # Check if queue has capacity
        processing = QueuedJob.objects.filter(
            queue=job.queue,
            status='processing'
        ).count()
        
        if processing < job.queue.max_concurrent:
            try:
                QueueManager.process_job(job)
            except Exception as e:
                logger.error(f'Failed to process job {job.job_id}: {e}')

@shared_task
def cleanup_old_jobs():
    '''Archive/delete old jobs'''
    from apps.queues.models import QueuedJob
    
    cutoff = timezone.now() - timedelta(days=30)
    QueuedJob.objects.filter(
        status__in=['completed', 'failed'],
        completed_at__lt=cutoff
    ).delete()

@shared_task
def alert_dead_letter_queue():
    '''Alert on dead letter queue buildup'''
    from apps.queues.models import DeadLetterQueue
    
    dead_letters = DeadLetterQueue.objects.filter(
        resolved=False,
        requires_review=True
    ).count()
    
    if dead_letters > 10:
        # Send alert
        logger.warning(f'Dead letter queue has {dead_letters} items requiring review')

# Add to CELERY_BEAT_SCHEDULE:
'process-queue': {
    'task': 'apps.queues.tasks.process_queue',
    'schedule': 60.0,  # Every minute
},
'cleanup-old-jobs': {
    'task': 'apps.queues.tasks.cleanup_old_jobs',
    'schedule': 604800.0,  # Weekly
},
'alert-dlq': {
    'task': 'apps.queues.tasks.alert_dead_letter_queue',
    'schedule': 3600.0,  # Hourly
},
"""