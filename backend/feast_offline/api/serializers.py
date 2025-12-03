from rest_framework import serializers


class FeatureRequestSerializer(serializers.Serializer):
    """
    Serializer for requesting features from Feast.
    Takes pricing_data_ids, optional columns, and optional timestamp for historical features.
    """
    pricing_data_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="List of pricing_data IDs to fetch features for"
    )
    columns = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_null=True,
        help_text="List of columns to return: current_price, previous_price, price_diff_abs, price_diff_pct, days_since_price_change, price_change_frequency_90d. If not provided, returns all columns."
    )
    timestamp = serializers.DateTimeField(
        required=False,
        allow_null=True,
        help_text="Optional timestamp for historical features (defaults to now)"
    )


class FeatureResponseSerializer(serializers.Serializer):
    """Serializer for feature response from Feast."""
    pricing_data_id = serializers.IntegerField()
    current_price = serializers.FloatField(allow_null=True)
    previous_price = serializers.FloatField(allow_null=True)
    price_diff_abs = serializers.FloatField(allow_null=True)
    price_diff_pct = serializers.FloatField(allow_null=True)
    days_since_price_change = serializers.FloatField(allow_null=True)
    price_change_frequency_90d = serializers.FloatField(allow_null=True)
    event_timestamp = serializers.DateTimeField()


class OnlineFeatureResponseSerializer(serializers.Serializer):
    """Serializer for online feature response (latest features from Redis)."""
    pricing_data_id = serializers.IntegerField()
    current_price = serializers.FloatField(allow_null=True)
    previous_price = serializers.FloatField(allow_null=True)
    price_diff_abs = serializers.FloatField(allow_null=True)
    price_diff_pct = serializers.FloatField(allow_null=True)
    days_since_price_change = serializers.FloatField(allow_null=True)
    price_change_frequency_90d = serializers.FloatField(allow_null=True)


class TrainingDataResponseSerializer(serializers.Serializer):
    """Serializer for training data response (historical features from Postgres)."""
    pricing_data_id = serializers.IntegerField()
    current_price = serializers.FloatField(allow_null=True)
    previous_price = serializers.FloatField(allow_null=True)
    price_diff_abs = serializers.FloatField(allow_null=True)
    price_diff_pct = serializers.FloatField(allow_null=True)
    days_since_price_change = serializers.FloatField(allow_null=True)
    price_change_frequency_90d = serializers.FloatField(allow_null=True)
    event_timestamp = serializers.DateTimeField()


class FeatureBatchResponseSerializer(serializers.Serializer):
    """Serializer for batch feature response."""
    status = serializers.CharField()
    count = serializers.IntegerField()
    features = FeatureResponseSerializer(many=True)
    errors = serializers.ListField(child=serializers.CharField(), required=False)


class OnlineFeatureBatchResponseSerializer(serializers.Serializer):
    """Serializer for batch online feature response."""
    status = serializers.CharField()
    count = serializers.IntegerField()
    features = OnlineFeatureResponseSerializer(many=True)
    errors = serializers.ListField(child=serializers.CharField(), required=False)


class TrainingDataBatchResponseSerializer(serializers.Serializer):
    """Serializer for batch training data response."""
    status = serializers.CharField()
    count = serializers.IntegerField()
    training_data = TrainingDataResponseSerializer(many=True)
    errors = serializers.ListField(child=serializers.CharField(), required=False)
