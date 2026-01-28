from rest_framework import serializers
from ..models import MLEngine, ModelCoefficient

class ModelCoefficientSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModelCoefficient
        fields = ['feature_name', 'value', 'p_value']

class MLEngineSerializer(serializers.ModelSerializer):
    coefficients = ModelCoefficientSerializer(many=True, required=False)
    
    # We explicitly define these to show Swagger they are JSON-formatted strings
    feature_names = serializers.JSONField(help_text="JSON list of strings: ['const', 'log_vcpu', ...]")
    log_transformed_features = serializers.JSONField(required=False, help_text="JSON list: ['vcpu', 'ram']")
    categorical_features = serializers.JSONField(required=False, help_text="JSON list: ['region', 'os']")
    metadata = serializers.JSONField(required=False, help_text="JSON object for extra metadata")

    class Meta:
        model = MLEngine
        fields = '__all__'

    def create(self, validated_data):
        coeffs_data = validated_data.pop('coefficients', [])
        # If coefficients is a string (from multipart), parse it
        if isinstance(coeffs_data, str):
            import json
            coeffs_data = json.loads(coeffs_data)
        engine = MLEngine.objects.create(**validated_data)
        for coeff in coeffs_data:
            ModelCoefficient.objects.create(engine=engine, **coeff)
        return engine


class MLEngineSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = MLEngine
        # Expose only identifying info and metrics, excluding any file fields
        fields = [
            'id',
            'name',
            'model_type',
            'version',
            'r_squared',
            'mape',
            'rmse',
            'training_sample_size',
            'is_active',
            'timestamp_created',
            'created_at',
            'updated_at',
        ]