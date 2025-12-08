from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class MLModel(models.Model):
    """
    A registered ML model owned by a user.
    """
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='models')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)  # active/deprecated
    latest_version = models.BooleanField(default=True)

    class Meta:
        unique_together = ('name', 'owner')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} (v{self.latest_version})"

class ModelVersion(models.Model):
    """
    A specific version of an ML model.
    """
    model = models.ForeignKey(MLModel, on_delete=models.CASCADE, related_name='versions')
    version = models.IntegerField()
    description = models.TextField(blank=True)
    file_path = models.CharField(max_length=1024)
    created_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=50, choices=[
        ('staging', 'Staging'),
        ('production', 'Production'),
        ('archived', 'Archived'),
    ], default='staging')

    class Meta:
        unique_together = ('model', 'version')
        ordering = ['-version']

    def __str__(self):
        return f"{self.model.name} v{self.version} ({self.status})"

class ModelMetric(models.Model):
    version = models.ForeignKey(ModelVersion, on_delete=models.CASCADE, related_name='metrics')
    key = models.CharField(max_length=100)
    value = models.FloatField()
    created_at = models.DateTimeField(default=timezone.now)