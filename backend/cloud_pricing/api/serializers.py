from rest_framework import serializers
from ..models import (
    CloudProvider,
    CloudService,
    Region,
    PricingData,
    PriceHistory,
    PriceAlert,
    ServiceCategory,
    PricingModel,
    Currency
)


class CloudProviderSerializer(serializers.ModelSerializer):
    class Meta:
        model = CloudProvider
        fields = ['id', 'name', 'display_name', 'is_active', 'created_at']


class ServiceCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceCategory
        fields = ['id', 'name', 'description']


class CloudServiceSerializer(serializers.ModelSerializer):
    provider = CloudProviderSerializer(read_only=True)
    category = ServiceCategorySerializer(read_only=True)
    
    class Meta:
        model = CloudService
        fields = ['id', 'provider', 'service_name', 'service_code', 'category', 'description', 'is_active']


class RegionSerializer(serializers.ModelSerializer):
    provider = CloudProviderSerializer(read_only=True)
    
    class Meta:
        model = Region
        fields = ['id', 'provider', 'region_code', 'region_name', 'is_active']


class PricingModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = PricingModel
        fields = ['id', 'name', 'display_name', 'description']


class CurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Currency
        fields = ['id', 'code', 'name', 'symbol', 'exchange_rate_to_usd']


class PricingDataSerializer(serializers.ModelSerializer):
    provider = CloudProviderSerializer(read_only=True)
    service = CloudServiceSerializer(read_only=True)
    region = RegionSerializer(read_only=True)
    pricing_model = PricingModelSerializer(read_only=True)
    currency = CurrencySerializer(read_only=True)
    
    class Meta:
        model = PricingData
        fields = [
            'id', 'provider', 'service', 'region', 'pricing_model', 'currency',
            'product_family', 'instance_type', 'operating_system', 'tenancy',
            'price_per_hour', 'price_per_month', 'price_per_year', 'price_per_unit', 'price_unit',
            'attributes', 'effective_date', 'end_date', 'is_active', 'created_at', 'updated_at'
        ]


class PricingDataDetailSerializer(PricingDataSerializer):
    """Detailed serializer including raw data"""
    class Meta(PricingDataSerializer.Meta):
        fields = PricingDataSerializer.Meta.fields + ['source_api', 'raw_data']


class PriceHistorySerializer(serializers.ModelSerializer):
    pricing_data = PricingDataSerializer(read_only=True)
    
    class Meta:
        model = PriceHistory
        fields = ['id', 'pricing_data', 'price_per_hour', 'price_per_month', 'price_per_unit', 'change_percentage', 'recorded_at']


class PriceAlertSerializer(serializers.ModelSerializer):
    pricing_data = PricingDataSerializer(read_only=True)
    
    class Meta:
        model = PriceAlert
        fields = ['id', 'pricing_data', 'alert_type', 'threshold_value', 'percentage_change', 'is_active', 'created_at']


class PriceComparisonSerializer(serializers.Serializer):
    """Serializer for price comparison between providers"""
    service_type = serializers.CharField()
    instance_type = serializers.CharField(required=False)
    region = serializers.CharField(required=False)
    providers = serializers.ListField(child=serializers.CharField(), required=False)


class PricingAnalyticsSerializer(serializers.Serializer):
    """Serializer for pricing analytics data"""
    provider = serializers.CharField(required=False)
    service = serializers.CharField(required=False)
    region = serializers.CharField(required=False)
    date_range = serializers.CharField(required=False)  # e.g., "7d", "30d", "90d"