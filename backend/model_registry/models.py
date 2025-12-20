from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid

class MLEngine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # The 'Name' identifies the business goal (e.g., "AWS_Compute_Pricing")
    name = models.CharField(
        max_length=255, 
        help_text="The functional name of the engine."
    )
    
    # The 'Model Type' identifies the methodology (e.g., "Hedonic_Regression", "XGBoost")
    model_type = models.CharField(
        max_length=100, 
        help_text="The algorithm or methodology used."
    )
    
    version = models.CharField(max_length=50, help_text="e.g., 2025.12.18.01")
    
    # Files: The 'Brain' and the 'Translator'
    model_binary = models.FileField(upload_to='models/binaries/')
    encoder_binary = models.FileField(upload_to='models/encoders/', null=True, blank=True)
    scaler_binary = models.FileField(upload_to='models/scalers/', null=True, blank=True, help_text="Feature scaler for models like Ridge")
    
    # Logic Mapping: Used for reconstructing the input vector during prediction
    feature_names = models.JSONField(help_text="Ordered list of columns: ['const', 'log_Vcpu', ...]")
    log_transformed_features = models.JSONField(default=list, blank=True)
    categorical_features = models.JSONField(default=list, blank=True)
    
    # Performance Stats
    r_squared = models.FloatField(validators=[MinValueValidator(0.0), MaxValueValidator(1.0)], null=True, blank=True)
    mape = models.FloatField(help_text="Mean Absolute Percentage Error.")
    rmse = models.FloatField(null=True, blank=True)
    training_sample_size = models.IntegerField(null=True, blank=True)
    
    # Flexible JSON store for everything else (hyperparams, data lineage, etc.)
    metadata = models.JSONField(default=dict, blank=True)

    # Status & Champion logic
    is_active = models.BooleanField(default=False, help_text="Is this the current 'Champion' for this name?")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ('name', 'version')
        verbose_name = "ML Engine"

    def __str__(self):
        return f"{self.name} ({self.model_type}) - v{self.version}"

    def save(self, *args, **kwargs):
        """
        If this engine is set to active, deactivate all other versions 
        sharing the same 'name'.
        """
        if self.is_active:
            MLEngine.objects.filter(
                name=self.name, 
                is_active=True
            ).exclude(id=self.id).update(is_active=False)
        super().save(*args, **kwargs)

class ModelCoefficient(models.Model):
    """
    Specifically useful for Hedonic Regression to store 'Shadow Prices'.
    """
    engine = models.ForeignKey(MLEngine, on_delete=models.CASCADE, related_name='coefficients')
    feature_name = models.CharField(max_length=255)
    value = models.FloatField()
    
    # Allows tracking if a coefficient is statistically significant (p < 0.05)
    p_value = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"{self.engine.name} - {self.feature_name}: {self.value}"