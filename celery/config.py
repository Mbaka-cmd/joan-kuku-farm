import os
from celery import Celery
from celery.schedules import crontab

# Set Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Create Celery app
app = Celery('jkf_poultry')

# Load configuration from Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from all installed apps
app.autodiscover_tasks()

# Celery beat schedule
app.conf.beat_schedule = {
    # Check low stock every 6 hours
    'check-low-stock': {
        'task': 'apps.orders.tasks.send_low_stock_alert',
        'schedule': crontab(minute=0, hour='*/6'),
    },
    # Send daily summary at 9 AM
    'daily-sales-summary': {
        'task': 'apps.analytics.tasks.send_daily_summary',
        'schedule': crontab(hour=9, minute=0),
    },
    # Cleanup old payment logs daily
    'cleanup-payment-logs': {
        'task': 'apps.payments.tasks.cleanup_old_logs',
        'schedule': crontab(hour=2, minute=0),
    },
}

@app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery"""
    print(f'Request: {self.request!r}')