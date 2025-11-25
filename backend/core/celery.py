import os
from celery import Celery
from celery.schedules import crontab

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
    # Replace daily update-all-pricing with weekly dump + full import
    "weekly-infracost-dump": {
        "task": "cloud_pricing.tasks.weekly_pricing_dump_update",
        # Run every Sunday at 04:00 AM (adjust timezone / hour to your preference)
        "schedule": crontab(hour=4, minute=0, day_of_week="sun"),
    },
}

app.conf.timezone = 'UTC'

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')