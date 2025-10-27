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
    Region,
    CloudService,
    PricingModel,
    Currency,
    APICallLog,
)

logger = logging.getLogger(__name__)


@shared_task
def update_all_pricing_data():
    """Task to update pricing data from all cloud providers"""
    logger.info("Starting pricing data update for all providers")

    orchestrator = CloudPricingOrchestrator()

    try:
        all_pricing_data = orchestrator.fetch_all_pricing_data()
        total_updated = 0

        for provider_name, services_data in all_pricing_data.items():
            updated_count = _process_provider_pricing_data(provider_name, services_data)
            total_updated += updated_count

        logger.info(f"Successfully updated {total_updated} pricing records")
        return f"Updated {total_updated} pricing records"

    except Exception as e:
        logger.error(f"Error updating pricing data: {str(e)}")
        raise


@shared_task
def update_provider_pricing_data(provider_name: str):
    """Task to update pricing data for a specific provider"""
    logger.info(f"Starting pricing data update for {provider_name}")

    orchestrator = CloudPricingOrchestrator()

    try:
        pricing_data = orchestrator.fetch_provider_pricing(provider_name)
        updated_count = _process_provider_pricing_data(provider_name, pricing_data.get(provider_name, []))
        logger.info(f"Successfully updated {updated_count} records for {provider_name}")
        return f"Updated {updated_count} records for {provider_name}"
    except Exception as e:
        logger.error(f"Error updating pricing data for {provider_name}: {str(e)}")
        raise


def _process_provider_pricing_data(provider_name: str, services_data: list) -> int:
    """Process and save pricing data for provider (Infracost version)"""
    updated_count = 0

    try:
        provider = CloudProvider.objects.get(name=provider_name)
    except CloudProvider.DoesNotExist:
        logger.error(f"Provider {provider_name} not found in database")
        return 0

    currency, _ = Currency.objects.get_or_create(
        code="USD",
        defaults={"name": "US Dollar", "symbol": "$", "exchange_rate_to_usd": 1.0},
    )

    pricing_model, _ = PricingModel.objects.get_or_create(
        name="on_demand",
        defaults={"display_name": "On-Demand", "description": "Pay-as-you-go pricing"},
    )

    for product in services_data:
        for price in product.get("prices", []):
            usd_value = float(price.get("USD", 0)) if price.get("USD") else 0
            item = {
                "instance_type": price.get("description", ""),
                "price_per_unit": usd_value,
                "price_per_hour": usd_value,
                "price_per_month": usd_value * 730,  # Convert hourly → monthly estimate
                "price_unit": price.get("unit", ""),
                "service_code": "compute",
                "region": "auto",
                "service_name": f"{provider_name.upper()} Compute",
                "description": price.get("description", ""),
                "raw_data": price,
            }

            try:
                updated_count += _save_pricing_item(provider, "compute", item, currency, pricing_model)
            except Exception as e:
                logger.error(f"Error saving Infracost item for {provider_name}: {str(e)}")
                continue

    return updated_count


def _save_pricing_item(provider, service_type, item, currency, pricing_model) -> int:
    """Save individual pricing item to database"""
    service, _ = CloudService.objects.get_or_create(
        provider=provider,
        service_code=service_type,
        defaults={
            "service_name": item.get("service_name", service_type.title()),
            "description": item.get("description", ""),
        },
    )

    region_code = item.get("region", "global")
    region_name = item.get("region", "Global")
    region, _ = Region.objects.get_or_create(
        provider=provider,
        region_code=region_code,
        defaults={"region_name": region_name},
    )

    pricing_data, created = PricingData.objects.update_or_create(
        provider=provider,
        service=service,
        region=region,
        pricing_model=pricing_model,
        instance_type=item.get("instance_type", ""),
        defaults={
            "currency": currency,
            "product_family": item.get("service_code", ""),
            "price_per_hour": item.get("price_per_hour", 0),
            "price_per_month": item.get("price_per_month", 0),
            "price_per_unit": item.get("price_per_unit", 0),
            "price_unit": item.get("price_unit", ""),
            "attributes": item.get("attributes", {}),
            "effective_date": timezone.now(),
            "source_api": f"{provider.name}_infracost_api",
            "raw_data": item.get("raw_data", {}),
            "is_active": True,
        },
    )

    if created:
        logger.info(f"Created new pricing record for {provider.name} {service.service_name}")
    else:
        logger.info(f"Updated pricing record for {provider.name} {service.service_name}")

    return 1


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
