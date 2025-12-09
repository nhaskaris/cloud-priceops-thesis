from rest_framework import serializers
from ..models import (
    CloudProvider, CloudService, Region,
    PricingModel, Currency, NormalizedPricingData, PriceHistory
)
from ..models import RawPricingData


class CloudProviderSerializer(serializers.ModelSerializer):
    class Meta:
        model = CloudProvider
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
        model = NormalizedPricingData
        fields = "__all__"


class PriceHistorySerializer(serializers.ModelSerializer):
    pricing_data = PricingDataSerializer(read_only=True)

    class Meta:
        model = PriceHistory
        fields = "__all__"



class RawPricingDataSerializer(serializers.ModelSerializer):
    provider = CloudProviderSerializer(read_only=True)
    provider_id = serializers.PrimaryKeyRelatedField(
        queryset=CloudProvider.objects.all(), write_only=True, source="provider"
    )
    normalized = PricingDataSerializer(read_only=True)
    normalized_id = serializers.PrimaryKeyRelatedField(
        queryset=NormalizedPricingData.objects.all(), write_only=True, source="normalized", allow_null=True, required=False
    )

    class Meta:
        model = RawPricingData
        fields = "__all__"


class TCORequestSerializer(serializers.Serializer):
    name = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Optional name for this TCO request.",
    )

    RESOURCE_CHOICES = ('cpu', 'gpu', 'memory', 'storage', 'generic')
    resource_type = serializers.ChoiceField(
        choices=RESOURCE_CHOICES,
        required=False,
        default='cpu',
        help_text="Type of resource to optimize for. Default: cpu.",
    )

    cpu_hours_per_month = serializers.DecimalField(
        max_digits=12,
        decimal_places=3,
        required=False,
        default=720,
        help_text="Compute hours per month. Default = 720 (full-time).",
    )

    storage_gb = serializers.DecimalField(
        max_digits=12,
        decimal_places=3,
        required=False,
        default=0,
        help_text="Optional storage requirement in GB.",
    )

    egress_gb = serializers.DecimalField(
        max_digits=12,
        decimal_places=3,
        required=False,
        default=0,
        help_text="Optional network egress in GB.",
    )

    duration_months = serializers.IntegerField(
        required=False,
        default=12,
        help_text="Total project duration in months.",
    )

    region_preferences = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
        help_text="List of preferred regions, e.g. ['us-east-1', 'eu-west-1'].",
    )

    providers = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
        help_text="Cloud providers to evaluate. Defaults to ['aws','azure','gcp'].",
    )
