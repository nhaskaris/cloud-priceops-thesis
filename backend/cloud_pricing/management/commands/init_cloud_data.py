from django.core.management.base import BaseCommand
from cloud_pricing.models import (
    CloudProvider, 
    PricingModel, 
    Currency,
    Region
)


class Command(BaseCommand):
    help = 'Initialize the database with basic cloud provider data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-regions',
            action='store_true',
            help='Skip creating default regions',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Initializing cloud provider data...'))

        # Create cloud providers
        providers_data = [
            {'name': 'aws', 'display_name': 'Amazon Web Services', 'api_endpoint': 'https://pricing.us-east-1.amazonaws.com'},
            {'name': 'azure', 'display_name': 'Microsoft Azure', 'api_endpoint': 'https://prices.azure.com/api/retail/prices'},
            {'name': 'gcp', 'display_name': 'Google Cloud Platform', 'api_endpoint': 'https://cloudbilling.googleapis.com'},
        ]

        for provider_data in providers_data:
            provider, created = CloudProvider.objects.get_or_create(
                name=provider_data['name'],
                defaults=provider_data
            )
            if created:
                self.stdout.write(f'Created provider: {provider.display_name}')
            else:
                self.stdout.write(f'Provider already exists: {provider.display_name}')

        # Create pricing models
        pricing_models = [
            {'name': 'on_demand', 'display_name': 'On-Demand', 'description': 'Pay-as-you-go pricing'},
            {'name': 'reserved', 'display_name': 'Reserved Instances', 'description': 'Reserved capacity with discounts'},
            {'name': 'spot', 'display_name': 'Spot Instances', 'description': 'Bid for unused capacity'},
            {'name': 'committed_use', 'display_name': 'Committed Use', 'description': 'Commit to usage for discounts'},
            {'name': 'pay_as_you_go', 'display_name': 'Pay-as-you-go', 'description': 'Usage-based pricing'},
        ]

        for model_data in pricing_models:
            pricing_model, created = PricingModel.objects.get_or_create(
                name=model_data['name'],
                defaults=model_data
            )
            if created:
                self.stdout.write(f'Created pricing model: {pricing_model.display_name}')

        # Create currencies
        currencies = [
            {'code': 'USD', 'name': 'US Dollar', 'symbol': '$', 'exchange_rate_to_usd': 1.0},
            {'code': 'EUR', 'name': 'Euro', 'symbol': '€', 'exchange_rate_to_usd': 0.85},
            {'code': 'GBP', 'name': 'British Pound', 'symbol': '£', 'exchange_rate_to_usd': 0.73},
            {'code': 'JPY', 'name': 'Japanese Yen', 'symbol': '¥', 'exchange_rate_to_usd': 110.0},
        ]

        for currency_data in currencies:
            currency, created = Currency.objects.get_or_create(
                code=currency_data['code'],
                defaults=currency_data
            )
            if created:
                self.stdout.write(f'Created currency: {currency.name}')

        # Create default regions if not skipped
        if not options['skip_regions']:
            self._create_default_regions()

        self.stdout.write(self.style.SUCCESS('Successfully initialized cloud provider data!'))

    def _create_default_regions(self):
        """Create default regions for each provider"""
        regions_data = {
            'aws': [
                {'region_code': 'us-east-1', 'region_name': 'US East (N. Virginia)'},
                {'region_code': 'us-west-2', 'region_name': 'US West (Oregon)'},
                {'region_code': 'eu-west-1', 'region_name': 'Europe (Ireland)'},
                {'region_code': 'ap-southeast-1', 'region_name': 'Asia Pacific (Singapore)'},
            ],
            'azure': [
                {'region_code': 'eastus', 'region_name': 'East US'},
                {'region_code': 'westus2', 'region_name': 'West US 2'},
                {'region_code': 'westeurope', 'region_name': 'West Europe'},
                {'region_code': 'southeastasia', 'region_name': 'Southeast Asia'},
            ],
            'gcp': [
                {'region_code': 'us-central1', 'region_name': 'Iowa'},
                {'region_code': 'us-west1', 'region_name': 'Oregon'},
                {'region_code': 'europe-west1', 'region_name': 'Belgium'},
                {'region_code': 'asia-southeast1', 'region_name': 'Singapore'},
            ]
        }

        for provider_name, regions in regions_data.items():
            try:
                provider = CloudProvider.objects.get(name=provider_name)
                for region_data in regions:
                    region, created = Region.objects.get_or_create(
                        provider=provider,
                        region_code=region_data['region_code'],
                        defaults={
                            'region_name': region_data['region_name'],
                        }
                    )
                    if created:
                        self.stdout.write(f'Created region: {provider_name.upper()} - {region.region_name}')
            except CloudProvider.DoesNotExist:
                self.stdout.write(f'Provider {provider_name} not found, skipping regions')