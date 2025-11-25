from django.apps import AppConfig
import logging
import os
import sys

logger = logging.getLogger(__name__)


class CloudPricingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'cloud_pricing'

    def ready(self):
        # Avoid circular imports until app registry is ready
        try:
            from .tasks import weekly_pricing_dump_update
        except Exception:
            logger.exception('Could not import update_all_pricing_data task')
            return

        # Only trigger this when running the Django development server (not during manage.py migrate, tests, celery, etc.)
        runserver = any('runserver' in arg for arg in sys.argv)
        # Different environments set RUN_MAIN differently; accept several truthy values
        is_reloader_child = os.environ.get('RUN_MAIN') in ('true', '1', 'True')

        # If you rely on Celery, prefer using Celery Beat (configured in core.celery) for periodic jobs.
        # This ready hook is just a convenient dev-time kick-off.
        if runserver and is_reloader_child:
            try:
                logger.info('Triggering update_all_pricing_data task from AppConfig.ready()')
                weekly_pricing_dump_update.delay()
            except Exception:
                logger.exception('Failed to enqueue update_all_pricing_data')
