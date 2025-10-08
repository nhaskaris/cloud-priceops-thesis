"""
Cloud pricing services for fetching data from AWS, Azure, and GCP APIs
"""
import boto3
import requests
from google.cloud.billing_v1.services.cloud_catalog import CloudCatalogClient
from google.oauth2.service_account import Credentials
from datetime import datetime
import json
import logging
from typing import Dict, List, Optional
from django.conf import settings


logger = logging.getLogger(__name__)


class AWSPricingService:
    """Service to fetch pricing data from AWS Pricing API"""
    
    def __init__(self):
        self.client = boto3.client(
            'pricing',
            region_name='us-east-1',  # Pricing API is only available in us-east-1
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )
    
    def get_ec2_pricing(self, region: str = 'us-east-1', instance_type: str = None) -> List[Dict]:
        """Fetch EC2 pricing data"""
        try:
            filters = [
                {'Type': 'TERM_MATCH', 'Field': 'ServiceCode', 'Value': 'AmazonEC2'},
                {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': self._get_region_name(region)},
                {'Type': 'TERM_MATCH', 'Field': 'tenancy', 'Value': 'Shared'},
                {'Type': 'TERM_MATCH', 'Field': 'operating-system', 'Value': 'Linux'},
                {'Type': 'TERM_MATCH', 'Field': 'pre-installed-sw', 'Value': 'NA'},
                {'Type': 'TERM_MATCH', 'Field': 'capacitystatus', 'Value': 'Used'},
            ]
            
            if instance_type:
                filters.append({
                    'Type': 'TERM_MATCH', 
                    'Field': 'instanceType', 
                    'Value': instance_type
                })
            
            response = self.client.get_products(
                ServiceCode='AmazonEC2',
                Filters=filters,
                MaxResults=100
            )
            
            pricing_data = []
            for price_item in response['PriceList']:
                price_data = json.loads(price_item)
                pricing_data.append(self._parse_aws_pricing_data(price_data))
            
            return pricing_data
            
        except Exception as e:
            logger.error(f"Error fetching AWS EC2 pricing: {str(e)}")
            return []
    
    def get_s3_pricing(self, region: str = 'us-east-1') -> List[Dict]:
        """Fetch S3 pricing data"""
        try:
            filters = [
                {'Type': 'TERM_MATCH', 'Field': 'ServiceCode', 'Value': 'AmazonS3'},
                {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': self._get_region_name(region)},
                {'Type': 'TERM_MATCH', 'Field': 'storageClass', 'Value': 'General Purpose'},
            ]
            
            response = self.client.get_products(
                ServiceCode='AmazonS3',
                Filters=filters,
                MaxResults=100
            )
            
            pricing_data = []
            for price_item in response['PriceList']:
                price_data = json.loads(price_item)
                pricing_data.append(self._parse_aws_pricing_data(price_data))
            
            return pricing_data
            
        except Exception as e:
            logger.error(f"Error fetching AWS S3 pricing: {str(e)}")
            return []
    
    def _get_region_name(self, region_code: str) -> str:
        """Convert AWS region code to region name used in pricing API"""
        region_mapping = {
            'us-east-1': 'US East (N. Virginia)',
            'us-west-2': 'US West (Oregon)',
            'eu-west-1': 'Europe (Ireland)',
            'ap-southeast-1': 'Asia Pacific (Singapore)',
            # Add more mappings as needed
        }
        return region_mapping.get(region_code, region_code)
    
    def _parse_aws_pricing_data(self, price_data: Dict) -> Dict:
        """Parse AWS pricing data into standardized format"""
        product = price_data.get('product', {})
        attributes = product.get('attributes', {})
        terms = price_data.get('terms', {})
        
        parsed_data = {
            'provider': 'aws',
            'service_code': product.get('productFamily', ''),
            'instance_type': attributes.get('instanceType', ''),
            'region': attributes.get('location', ''),
            'operating_system': attributes.get('operatingSystem', ''),
            'tenancy': attributes.get('tenancy', ''),
            'attributes': attributes,
            'raw_data': price_data
        }
        
        # Extract pricing information
        on_demand = terms.get('OnDemand', {})
        if on_demand:
            for term_key, term_data in on_demand.items():
                price_dimensions = term_data.get('priceDimensions', {})
                for price_key, price_info in price_dimensions.items():
                    price_per_unit = price_info.get('pricePerUnit', {}).get('USD', '0')
                    parsed_data['price_per_hour'] = float(price_per_unit) if price_per_unit else 0
                    parsed_data['price_unit'] = price_info.get('unit', '')
                    break
                break
        
        return parsed_data


class AzurePricingService:
    """Service to fetch pricing data from Azure Pricing API"""
    
    def __init__(self):
        self.base_url = "https://prices.azure.com/api/retail/prices"
    
    def get_vm_pricing(self, region: str = 'eastus', vm_size: str = None) -> List[Dict]:
        """Fetch Azure VM pricing data"""
        try:
            filters = f"serviceName eq 'Virtual Machines' and armRegionName eq '{region}'"
            if vm_size:
                filters += f" and armSkuName eq '{vm_size}'"
            
            params = {
                '$filter': filters,
                'api-version': '2023-01-01-preview'
            }
            
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            
            data = response.json()
            pricing_data = []
            
            for item in data.get('Items', []):
                pricing_data.append(self._parse_azure_pricing_data(item))
            
            return pricing_data
            
        except Exception as e:
            logger.error(f"Error fetching Azure VM pricing: {str(e)}")
            return []
    
    def get_storage_pricing(self, region: str = 'eastus') -> List[Dict]:
        """Fetch Azure Storage pricing data"""
        try:
            filters = f"serviceName eq 'Storage' and armRegionName eq '{region}'"
            
            params = {
                '$filter': filters,
                'api-version': '2023-01-01-preview'
            }
            
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            
            data = response.json()
            pricing_data = []
            
            for item in data.get('Items', []):
                pricing_data.append(self._parse_azure_pricing_data(item))
            
            return pricing_data
            
        except Exception as e:
            logger.error(f"Error fetching Azure Storage pricing: {str(e)}")
            return []
    
    def _parse_azure_pricing_data(self, item: Dict) -> Dict:
        """Parse Azure pricing data into standardized format"""
        return {
            'provider': 'azure',
            'service_code': item.get('serviceName', ''),
            'service_name': item.get('productName', ''),
            'instance_type': item.get('armSkuName', ''),
            'region': item.get('armRegionName', ''),
            'price_per_hour': item.get('unitPrice', 0),
            'price_unit': item.get('unitOfMeasure', ''),
            'currency': item.get('currencyCode', 'USD'),
            'effective_date': item.get('effectiveStartDate', ''),
            'attributes': {
                'meter_name': item.get('meterName', ''),
                'product_name': item.get('productName', ''),
                'sku_name': item.get('skuName', ''),
                'type': item.get('type', ''),
            },
            'raw_data': item
        }


class GCPPricingService:
    """Service to fetch pricing data from Google Cloud Pricing API"""
    
    def __init__(self):
        if settings.GOOGLE_APPLICATION_CREDENTIALS:
            self.credentials = Credentials.from_service_account_file(
                settings.GOOGLE_APPLICATION_CREDENTIALS
            )
            self.client = CloudCatalogClient(credentials=self.credentials)
        else:
            self.client = CloudCatalogClient()
    
    def get_compute_pricing(self, project_id: str = None) -> List[Dict]:
        """Fetch GCP Compute Engine pricing data"""
        try:
            project_id = project_id or settings.GCP_PROJECT_ID
            parent = f"projects/{project_id}"
            
            # List all services
            services = self.client.list_services(parent=parent)
            
            pricing_data = []
            for service in services:
                if 'compute' in service.display_name.lower():
                    skus = self.client.list_skus(parent=service.name)
                    for sku in skus:
                        pricing_data.append(self._parse_gcp_pricing_data(sku))
            
            return pricing_data
            
        except Exception as e:
            logger.error(f"Error fetching GCP Compute pricing: {str(e)}")
            return []
    
    def get_storage_pricing(self, project_id: str = None) -> List[Dict]:
        """Fetch GCP Storage pricing data"""
        try:
            project_id = project_id or settings.GCP_PROJECT_ID
            parent = f"projects/{project_id}"
            
            services = self.client.list_services(parent=parent)
            
            pricing_data = []
            for service in services:
                if 'storage' in service.display_name.lower():
                    skus = self.client.list_skus(parent=service.name)
                    for sku in skus:
                        pricing_data.append(self._parse_gcp_pricing_data(sku))
            
            return pricing_data
            
        except Exception as e:
            logger.error(f"Error fetching GCP Storage pricing: {str(e)}")
            return []
    
    def _parse_gcp_pricing_data(self, sku) -> Dict:
        """Parse GCP pricing data into standardized format"""
        pricing_info = sku.pricing_info[0] if sku.pricing_info else None
        pricing_expression = pricing_info.pricing_expression if pricing_info else None
        
        base_unit_price = 0
        if pricing_expression and pricing_expression.tiered_rates:
            base_unit_price = float(pricing_expression.tiered_rates[0].unit_price.nanos) / 1e9
        
        return {
            'provider': 'gcp',
            'service_code': sku.category.service_display_name,
            'service_name': sku.display_name,
            'description': sku.description,
            'price_per_unit': base_unit_price,
            'price_unit': pricing_expression.usage_unit if pricing_expression else '',
            'currency': pricing_info.currency_code if pricing_info else 'USD',
            'geo_taxonomy': list(sku.geo_taxonomy.regions) if sku.geo_taxonomy else [],
            'attributes': {
                'sku_id': sku.sku_id,
                'category': sku.category.resource_family,
                'usage_type': sku.category.usage_type,
            },
            'raw_data': {
                'name': sku.name,
                'sku_id': sku.sku_id,
                'description': sku.description,
                'category': {
                    'service_display_name': sku.category.service_display_name,
                    'resource_family': sku.category.resource_family,
                    'resource_group': sku.category.resource_group,
                    'usage_type': sku.category.usage_type,
                }
            }
        }


class CloudPricingOrchestrator:
    """Orchestrator class to manage all cloud pricing services"""
    
    def __init__(self):
        self.aws_service = AWSPricingService()
        self.azure_service = AzurePricingService()
        self.gcp_service = GCPPricingService()
    
    def fetch_all_pricing_data(self) -> Dict[str, List[Dict]]:
        """Fetch pricing data from all cloud providers"""
        results = {
            'aws': {
                'ec2': self.aws_service.get_ec2_pricing(),
                's3': self.aws_service.get_s3_pricing(),
            },
            'azure': {
                'vm': self.azure_service.get_vm_pricing(),
                'storage': self.azure_service.get_storage_pricing(),
            },
            'gcp': {
                'compute': self.gcp_service.get_compute_pricing(),
                'storage': self.gcp_service.get_storage_pricing(),
            }
        }
        
        return results
    
    def fetch_provider_pricing(self, provider: str) -> Dict[str, List[Dict]]:
        """Fetch pricing data for a specific provider"""
        if provider.lower() == 'aws':
            return {
                'ec2': self.aws_service.get_ec2_pricing(),
                's3': self.aws_service.get_s3_pricing(),
            }
        elif provider.lower() == 'azure':
            return {
                'vm': self.azure_service.get_vm_pricing(),
                'storage': self.azure_service.get_storage_pricing(),
            }
        elif provider.lower() == 'gcp':
            return {
                'compute': self.gcp_service.get_compute_pricing(),
                'storage': self.gcp_service.get_storage_pricing(),
            }
        else:
            raise ValueError(f"Unsupported provider: {provider}")