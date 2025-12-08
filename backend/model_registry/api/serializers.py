from rest_framework import serializers
from ..models import MLModel, ModelVersion

class ModelVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModelVersion
        fields = ['id', 'version', 'description', 'file_path', 'status', 'created_at']

class MLModelSerializer(serializers.ModelSerializer):
    versions = ModelVersionSerializer(many=True, read_only=True)

    class Meta:
        model = MLModel
        fields = ['id', 'name', 'description', 'latest_version', 'is_active', 'created_at', 'updated_at', 'versions']
