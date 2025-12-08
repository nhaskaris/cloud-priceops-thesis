from rest_framework import serializers
from ..models import MLModel, ModelVersion, ModelMetric

class ModelVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModelVersion
        fields = ['id', 'version', 'description', 'file_path', 'status', 'created_at']

class MLModelSerializer(serializers.ModelSerializer):
    versions = ModelVersionSerializer(many=True, read_only=True)

    class Meta:
        model = MLModel
        fields = ['id', 'name', 'description', 'latest_version', 'is_active', 'created_at', 'updated_at', 'versions']

class ModelMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModelMetric
        fields = ['id', 'version', 'key', 'value', 'created_at']
        read_only_fields = ['id', 'created_at']