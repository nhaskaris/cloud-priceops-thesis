from rest_framework import serializers
from ..models import (
    CloudProvider, CloudService, Region, ServiceCategory,
    PricingModel, Currency, PricingData, PriceHistory, PriceAlert
)


class CloudProviderSerializer(serializers.ModelSerializer):
    class Meta:
        model = CloudProvider
        fields = "__all__"


class ServiceCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceCategory
        fields = "__all__"


class CloudServiceSerializer(serializers.ModelSerializer):
    provider = CloudProviderSerializer(read_only=True)
    provider_id = serializers.PrimaryKeyRelatedField(
        queryset=CloudProvider.objects.all(), write_only=True, source="provider"
    )

    class Meta:
        model = CloudService
        fields = "__all__"


class RegionSerializer(serializers.ModelSerializer):
    provider = CloudProviderSerializer(read_only=True)
    provider_id = serializers.PrimaryKeyRelatedField(
        queryset=CloudProvider.objects.all(), write_only=True, source="provider"
    )

    class Meta:
        model = Region
        fields = "__all__"


class PricingModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = PricingModel
        fields = "__all__"


class CurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Currency
        fields = "__all__"


class PricingDataSerializer(serializers.ModelSerializer):
    provider = CloudProviderSerializer(read_only=True)
    service = CloudServiceSerializer(read_only=True)
    region = RegionSerializer(read_only=True)
    pricing_model = PricingModelSerializer(read_only=True)
    currency = CurrencySerializer(read_only=True)

    provider_id = serializers.PrimaryKeyRelatedField(
        queryset=CloudProvider.objects.all(), write_only=True, source="provider"
    )
    service_id = serializers.PrimaryKeyRelatedField(
        queryset=CloudService.objects.all(), write_only=True, source="service"
    )
    region_id = serializers.PrimaryKeyRelatedField(
        queryset=Region.objects.all(), write_only=True, source="region"
    )
    pricing_model_id = serializers.PrimaryKeyRelatedField(
        queryset=PricingModel.objects.all(), write_only=True, source="pricing_model"
    )
    currency_id = serializers.PrimaryKeyRelatedField(
        queryset=Currency.objects.all(), write_only=True, source="currency"
    )

    class Meta:
        model = PricingData
        fields = "__all__"


class PriceHistorySerializer(serializers.ModelSerializer):
    pricing_data = PricingDataSerializer(read_only=True)

    class Meta:
        model = PriceHistory
        fields = "__all__"


class PriceAlertSerializer(serializers.ModelSerializer):
    pricing_data = PricingDataSerializer(read_only=True)
    user = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = PriceAlert
        fields = "__all__"
