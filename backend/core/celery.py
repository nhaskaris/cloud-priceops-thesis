import os
from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

app = Celery('cloud_priceops')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Celery beat schedule for periodic tasks
app.conf.beat_schedule = {
    'update-all-pricing-daily': {
        'task': 'cloud_pricing.tasks.update_all_pricing_data',
        'schedule': 24 * 60 * 60,  # Run daily (24 hours)
    },
    'cleanup-old-pricing-weekly': {
        'task': 'cloud_pricing.tasks.cleanup_old_pricing_data',
        'schedule': 7 * 24 * 60 * 60,  # Run weekly
        'kwargs': {'days_to_keep': 90}
    },
    'check-price-alerts-hourly': {
        'task': 'cloud_pricing.tasks.check_price_alerts',
        'schedule': 60 * 60,  # Run hourly
    },
}

app.conf.timezone = 'UTC'

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')