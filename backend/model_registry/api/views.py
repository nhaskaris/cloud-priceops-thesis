from rest_framework import generics, permissions
from ..models import MLModel, ModelVersion, ModelMetric
from .serializers import MLModelSerializer, ModelVersionSerializer, ModelMetricSerializer

# List and create models for the authenticated user
class MLModelListCreateView(generics.ListCreateAPIView):
    serializer_class = MLModelSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return MLModel.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class MLModelDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = MLModelSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return MLModel.objects.filter(owner=self.request.user)


class ModelVersionListCreateView(generics.ListCreateAPIView):
    serializer_class = ModelVersionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        model_id = self.kwargs['model_id']
        return ModelVersion.objects.filter(model__id=model_id, model__owner=self.request.user)

    def perform_create(self, serializer):
        model_id = self.kwargs['model_id']
        model = MLModel.objects.get(id=model_id, owner=self.request.user)
        # Find the latest version number for this model
        latest_version_obj = ModelVersion.objects.filter(model=model).order_by('-version').first()
        next_version = (latest_version_obj.version + 1) if latest_version_obj else 1
        serializer.save(model=model, version=next_version)
        # Mark this model as having its latest version (True)
        model.latest_version = True
        model.save()

class ModelMetricListCreateView(generics.ListCreateAPIView):
    serializer_class = ModelMetricSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        version_id = self.kwargs['version_id']
        return ModelMetric.objects.filter(version__id=version_id, version__model__owner=self.request.user)

    def perform_create(self, serializer):
        version_id = self.kwargs['version_id']
        version = ModelVersion.objects.get(id=version_id, model__owner=self.request.user)
        serializer.save(version=version)