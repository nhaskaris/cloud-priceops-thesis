"""
Celery tasks for periodic pricing data updates
"""
from celery import shared_task
from django.utils import timezone
from datetime import datetime, timedelta
import logging

from .services import CloudPricingOrchestrator
from .models import (
    CloudProvider, 
    PricingData, 
    Region, 
    CloudService, 
    PricingModel,
    Currency,
    APICallLog
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
    """Task to update pricing data for specific provider"""
    logger.info(f"Starting pricing data update for {provider_name}")
    
    orchestrator = CloudPricingOrchestrator()
    
    try:
        pricing_data = orchestrator.fetch_provider_pricing(provider_name)
        updated_count = _process_provider_pricing_data(provider_name, pricing_data)
        
        logger.info(f"Successfully updated {updated_count} pricing records for {provider_name}")
        return f"Updated {updated_count} pricing records for {provider_name}"
        
    except Exception as e:
        logger.error(f"Error updating pricing data for {provider_name}: {str(e)}")
        raise


def _process_provider_pricing_data(provider_name: str, services_data: dict) -> int:
    """Process and save pricing data for a provider"""
    updated_count = 0
    
    try:
        provider = CloudProvider.objects.get(name=provider_name)
    except CloudProvider.DoesNotExist:
        logger.error(f"Provider {provider_name} not found in database")
        return 0
    
    # Get or create default currency (USD)
    currency, _ = Currency.objects.get_or_create(
        code='USD',
        defaults={
            'name': 'US Dollar',
            'symbol': '$',
            'exchange_rate_to_usd': 1.0
        }
    )
    
    # Get or create default pricing model (On-Demand)
    pricing_model, _ = PricingModel.objects.get_or_create(
        name='on_demand',
        defaults={
            'display_name': 'On-Demand',
            'description': 'Pay-as-you-go pricing'
        }
    )
    
    for service_type, pricing_items in services_data.items():
        for item in pricing_items:
            try:
                updated_count += _save_pricing_item(
                    provider, 
                    service_type, 
                    item, 
                    currency, 
                    pricing_model
                )
            except Exception as e:
                logger.error(f"Error saving pricing item: {str(e)}")
                continue
    
    return updated_count


def _save_pricing_item(provider, service_type, item, currency, pricing_model) -> int:
    """Save individual pricing item to database"""
    
    # Get or create service
    service, _ = CloudService.objects.get_or_create(
        provider=provider,
        service_code=service_type,
        defaults={
            'service_name': item.get('service_name', service_type.title()),
            'description': item.get('description', ''),
        }
    )
    
    # Get or create region
    region_code = item.get('region', 'global')
    region_name = item.get('region', 'Global')
    region, _ = Region.objects.get_or_create(
        provider=provider,
        region_code=region_code,
        defaults={
            'region_name': region_name,
        }
    )
    
    # Create or update pricing data
    pricing_data, created = PricingData.objects.update_or_create(
        provider=provider,
        service=service,
        region=region,
        pricing_model=pricing_model,
        instance_type=item.get('instance_type', ''),
        operating_system=item.get('operating_system', ''),
        defaults={
            'currency': currency,
            'product_family': item.get('service_code', ''),
            'tenancy': item.get('tenancy', ''),
            'price_per_hour': item.get('price_per_hour', 0),
            'price_per_month': item.get('price_per_month', 0),
            'price_per_unit': item.get('price_per_unit', 0),
            'price_unit': item.get('price_unit', ''),
            'attributes': item.get('attributes', {}),
            'effective_date': timezone.now(),
            'source_api': f"{provider.name}_pricing_api",
            'raw_data': item.get('raw_data', {}),
            'is_active': True,
        }
    )
    
    if created:
        logger.info(f"Created new pricing record for {provider.name} {service.service_name}")
    else:
        logger.info(f"Updated pricing record for {provider.name} {service.service_name}")
    
    return 1


@shared_task
def cleanup_old_pricing_data(days_to_keep: int = 30):
    """Task to cleanup old pricing data"""
    logger.info(f"Starting cleanup of pricing data older than {days_to_keep} days")
    
    cutoff_date = timezone.now() - timedelta(days=days_to_keep)
    
    try:
        # Soft delete old pricing data by marking as inactive
        old_records = PricingData.objects.filter(
            created_at__lt=cutoff_date,
            is_active=True
        )
        
        count = old_records.count()
        old_records.update(is_active=False)
        
        logger.info(f"Marked {count} old pricing records as inactive")
        return f"Cleaned up {count} old pricing records"
        
    except Exception as e:
        logger.error(f"Error cleaning up old pricing data: {str(e)}")
        raise


@shared_task
def generate_pricing_report(provider_name: str = None, service_type: str = None):
    """Task to generate pricing analysis reports"""
    logger.info("Generating pricing report")
    
    try:
        filters = {'is_active': True}
        
        if provider_name:
            filters['provider__name'] = provider_name
        
        if service_type:
            filters['service__service_code'] = service_type
        
        pricing_data = PricingData.objects.filter(**filters)
        
        report = {
            'total_records': pricing_data.count(),
            'providers': list(pricing_data.values_list('provider__name', flat=True).distinct()),
            'services': list(pricing_data.values_list('service__service_name', flat=True).distinct()),
            'regions': list(pricing_data.values_list('region__region_name', flat=True).distinct()),
            'generated_at': timezone.now().isoformat(),
        }
        
        # Add price statistics
        if pricing_data.exists():
            hourly_prices = pricing_data.exclude(price_per_hour__isnull=True).values_list('price_per_hour', flat=True)
            if hourly_prices:
                report['price_statistics'] = {
                    'min_hourly_price': min(hourly_prices),
                    'max_hourly_price': max(hourly_prices),
                    'avg_hourly_price': sum(hourly_prices) / len(hourly_prices),
                }
        
        logger.info(f"Generated pricing report with {report['total_records']} records")
        return report
        
    except Exception as e:
        logger.error(f"Error generating pricing report: {str(e)}")
        raise


@shared_task
def log_api_call(provider_name: str, endpoint: str, status_code: int, response_time: float, records_updated: int = 0, error_message: str = ""):
    """Task to log API calls for monitoring"""
    try:
        provider = CloudProvider.objects.get(name=provider_name)
        
        APICallLog.objects.create(
            provider=provider,
            api_endpoint=endpoint,
            status_code=status_code,
            response_time=response_time,
            records_updated=records_updated,
            error_message=error_message
        )
        
        logger.info(f"Logged API call for {provider_name}")
        
    except Exception as e:
        logger.error(f"Error logging API call: {str(e)}")


@shared_task
def check_price_alerts():
    """Task to check and trigger price alerts"""
    logger.info("Checking price alerts")
    
    try:
        from .models import PriceAlert, PriceHistory
        
        active_alerts = PriceAlert.objects.filter(is_active=True)
        triggered_alerts = []
        
        for alert in active_alerts:
            latest_price = alert.pricing_data.price_per_hour
            
            # Get the previous price for comparison
            previous_prices = PriceHistory.objects.filter(
                pricing_data=alert.pricing_data
            ).order_by('-recorded_at')[:2]
            
            if len(previous_prices) >= 2 and latest_price:
                previous_price = previous_prices[1].price_per_hour
                
                if previous_price and previous_price > 0:
                    price_change = ((latest_price - previous_price) / previous_price) * 100
                    
                    should_trigger = False
                    
                    if alert.alert_type == 'increase' and price_change > 0:
                        if not alert.percentage_change or price_change >= alert.percentage_change:
                            should_trigger = True
                    
                    elif alert.alert_type == 'decrease' and price_change < 0:
                        if not alert.percentage_change or abs(price_change) >= alert.percentage_change:
                            should_trigger = True
                    
                    elif alert.alert_type == 'threshold' and alert.threshold_value:
                        if latest_price >= alert.threshold_value:
                            should_trigger = True
                    
                    if should_trigger:
                        triggered_alerts.append({
                            'alert_id': alert.id,
                            'user': alert.user.username,
                            'pricing_data': str(alert.pricing_data),
                            'price_change': price_change,
                            'current_price': latest_price,
                            'previous_price': previous_price,
                        })
        
        logger.info(f"Found {len(triggered_alerts)} triggered alerts")
        
        # Here you would send notifications (email, webhook, etc.)
        for alert_info in triggered_alerts:
            logger.info(f"Alert triggered: {alert_info}")
        
        return f"Processed {len(triggered_alerts)} price alerts"
        
    except Exception as e:
        logger.error(f"Error checking price alerts: {str(e)}")
        raise