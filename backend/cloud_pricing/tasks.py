"""
Celery tasks for periodic pricing data updates using Infracost
"""
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

from .services import CloudPricingOrchestrator
from .models import (
    CloudProvider,
    PricingData,
    APICallLog,
)

logger = logging.getLogger(__name__)


@shared_task
def update_all_pricing_data():
    orchestrator = CloudPricingOrchestrator()
    total_saved = orchestrator.fetch_all_pricing_data()
    logger.info(f"Saved {total_saved} pricing records for all providers")
    return f"Saved {total_saved} pricing records"

@shared_task
def update_provider_pricing_data(provider_name: str):
    orchestrator = CloudPricingOrchestrator()
    saved_count = orchestrator.fetch_provider_pricing(provider_name)
    logger.info(f"Saved {saved_count} pricing records for {provider_name}")
    return f"Saved {saved_count} pricing records for {provider_name}"

@shared_task
def cleanup_old_pricing_data(days_to_keep: int = 30):
    """Clean up old pricing data"""
    logger.info(f"Cleaning up pricing data older than {days_to_keep} days")
    cutoff_date = timezone.now() - timedelta(days=days_to_keep)

    try:
        old_records = PricingData.objects.filter(created_at__lt=cutoff_date, is_active=True)
        count = old_records.count()
        old_records.update(is_active=False)
        logger.info(f"Marked {count} old records inactive")
        return f"Cleaned {count} old records"
    except Exception as e:
        logger.error(f"Error cleaning pricing data: {str(e)}")
        raise


@shared_task
def log_api_call(provider_name: str, endpoint: str, status_code: int, response_time: float, records_updated: int = 0, error_message: str = ""):
    """Log API call metrics"""
    try:
        provider = CloudProvider.objects.get(name=provider_name)
        APICallLog.objects.create(
            provider=provider,
            api_endpoint=endpoint,
            status_code=status_code,
            response_time=response_time,
            records_updated=records_updated,
            error_message=error_message,
        )
        logger.info(f"Logged API call for {provider_name}")
    except Exception as e:
        logger.error(f"Error logging API call: {str(e)}")
