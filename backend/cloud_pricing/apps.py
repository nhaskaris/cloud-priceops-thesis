from django.apps import AppConfig


class CloudPricingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'cloud_pricing'

    def ready(self):
        # Import here to avoid circular imports
        from .tasks import update_all_pricing_data
        import os

        # Ensure this only runs once in the main process (especially with dev server)
        if os.environ.get('RUN_MAIN') == 'true':
            # Trigger the task asynchronously
            update_all_pricing_data.apply_async()
