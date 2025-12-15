from rest_framework import serializers
from ..models import (
    CloudProvider, CloudService, Region,
    PricingModel, Currency, NormalizedPricingData, PriceHistory
)
from ..models import RawPricingData

class PricingDataSerializer(serializers.ModelSerializer):
    """
    Serializer for NormalizedPricingData model.

    Returns:
        dict: Serialized pricing data with normalized fields for API responses.
    """
    provider = serializers.StringRelatedField()
    service = serializers.StringRelatedField()
    region = serializers.StringRelatedField()
    pricing_model = serializers.StringRelatedField()
    currency = serializers.StringRelatedField()

    class Meta:
        model = NormalizedPricingData
        exclude = ['raw_entry', 'source_api', 'created_at', 'updated_at', 'is_active', 'description']
