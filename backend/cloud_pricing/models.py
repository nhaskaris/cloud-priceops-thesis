from django.db import models
from django.contrib.auth.models import User
from datetime import datetime


class CloudProvider(models.Model):
    """Model to store cloud provider information"""
    PROVIDER_CHOICES = [
        ('aws', 'Amazon Web Services'),
        ('azure', 'Microsoft Azure'),
        ('gcp', 'Google Cloud Platform'),
    ]
    
    name = models.CharField(max_length=10, choices=PROVIDER_CHOICES, unique=True)
    display_name = models.CharField(max_length=50)
    api_endpoint = models.URLField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.display_name


class ServiceCategory(models.Model):
    """Model to store service categories (Compute, Storage, Network, etc.)"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Service Categories"

    def __str__(self):
        return self.name


class CloudService(models.Model):
    """Model to store cloud services information"""
    provider = models.ForeignKey(CloudProvider, on_delete=models.CASCADE, related_name='services')
    service_name = models.CharField(max_length=100)
    service_code = models.CharField(max_length=50)  # e.g., EC2, S3, etc.
    category = models.ForeignKey(ServiceCategory, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['provider', 'service_code']

    def __str__(self):
        return f"{self.provider.name.upper()} - {self.service_name}"


class Region(models.Model):
    """Model to store cloud regions"""
    provider = models.ForeignKey(CloudProvider, on_delete=models.CASCADE, related_name='regions')
    region_code = models.CharField(max_length=50)  # e.g., us-east-1, eastus
    region_name = models.CharField(max_length=100)  # e.g., US East (N. Virginia)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['provider', 'region_code']

    def __str__(self):
        return f"{self.provider.name.upper()} - {self.region_name}"


class PricingModel(models.Model):
    """Model to store different pricing models (On-Demand, Reserved, Spot, etc.)"""
    PRICING_TYPE_CHOICES = [
        ('on_demand', 'On-Demand'),
        ('reserved', 'Reserved'),
        ('spot', 'Spot'),
        ('committed_use', 'Committed Use'),
        ('pay_as_you_go', 'Pay-as-you-go'),
    ]
    
    name = models.CharField(max_length=20, choices=PRICING_TYPE_CHOICES, unique=True)
    display_name = models.CharField(max_length=50)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.display_name


class Currency(models.Model):
    """Model to store currency information"""
    code = models.CharField(max_length=3, unique=True)  # USD, EUR, GBP
    name = models.CharField(max_length=50)
    symbol = models.CharField(max_length=5)
    exchange_rate_to_usd = models.DecimalField(max_digits=10, decimal_places=6, default=1.0)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Currencies"

    def __str__(self):
        return f"{self.code} - {self.name}"


class PricingData(models.Model):
    """Main model to store pricing information"""
    provider = models.ForeignKey(CloudProvider, on_delete=models.CASCADE)
    service = models.ForeignKey(CloudService, on_delete=models.CASCADE)
    region = models.ForeignKey(Region, on_delete=models.CASCADE)
    pricing_model = models.ForeignKey(PricingModel, on_delete=models.CASCADE)
    currency = models.ForeignKey(Currency, on_delete=models.CASCADE)
    
    # Product details
    product_family = models.CharField(max_length=100, blank=True)  # Instance, Storage, etc.
    instance_type = models.CharField(max_length=50, blank=True)    # t3.micro, Standard_D2s_v3
    operating_system = models.CharField(max_length=50, blank=True)  # Linux, Windows
    tenancy = models.CharField(max_length=20, blank=True)          # Shared, Dedicated
    
    # Pricing details
    price_per_hour = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    price_per_month = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    price_per_year = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    price_per_unit = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    price_unit = models.CharField(max_length=50, blank=True)       # GB, requests, etc.
    
    # Additional attributes (JSON field for flexible storage)
    attributes = models.JSONField(default=dict, blank=True)
    
    # Metadata
    effective_date = models.DateTimeField(default=datetime.now)
    end_date = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Data source tracking
    source_api = models.CharField(max_length=100, blank=True)
    raw_data = models.JSONField(default=dict, blank=True)  # Store original API response

    class Meta:
        indexes = [
            models.Index(fields=['provider', 'service', 'region']),
            models.Index(fields=['instance_type']),
            models.Index(fields=['effective_date']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        base_str = f"{self.provider.name.upper()} - {self.service.service_name}"
        if self.instance_type:
            return f"{base_str} - {self.instance_type}"
        return base_str


class PriceHistory(models.Model):
    """Model to track pricing history for analysis"""
    pricing_data = models.ForeignKey(PricingData, on_delete=models.CASCADE, related_name='history')
    price_per_hour = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    price_per_month = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    price_per_unit = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    change_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-recorded_at']

    def __str__(self):
        return f"Price history for {self.pricing_data} at {self.recorded_at}"


class PriceAlert(models.Model):
    """Model to store price alerts for users"""
    ALERT_TYPES = [
        ('increase', 'Price Increase'),
        ('decrease', 'Price Decrease'),
        ('threshold', 'Price Threshold'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='price_alerts')
    pricing_data = models.ForeignKey(PricingData, on_delete=models.CASCADE)
    alert_type = models.CharField(max_length=10, choices=ALERT_TYPES)
    threshold_value = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    percentage_change = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Alert for {self.user.username} - {self.pricing_data}"


class APICallLog(models.Model):
    """Model to log API calls for monitoring and rate limiting"""
    provider = models.ForeignKey(CloudProvider, on_delete=models.CASCADE)
    api_endpoint = models.URLField()
    status_code = models.IntegerField()
    response_time = models.DecimalField(max_digits=8, decimal_places=3)  # in seconds
    records_updated = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)
    called_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-called_at']

    def __str__(self):
        return f"{self.provider.name.upper()} API call at {self.called_at}"
