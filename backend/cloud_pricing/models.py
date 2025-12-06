from django.db import models
from django.contrib.auth.models import User
from datetime import datetime
from django.utils import timezone

class CloudProvider(models.Model):
    """Cloud provider information (Infracost supports AWS, Azure, GCP)"""
    PROVIDER_CHOICES = [
        ('aws', 'Amazon Web Services'),
        ('azure', 'Microsoft Azure'),
        ('gcp', 'Google Cloud Platform'),
    ]

    name = models.CharField(max_length=50, choices=PROVIDER_CHOICES, unique=True)
    display_name = models.CharField(max_length=100)
    api_endpoint = models.URLField(
        blank=True,
        null=True,
        help_text="Optional API endpoint; for Infracost, all use same endpoint."
    )
    is_active = models.BooleanField(default=True)
    uses_infracost = models.BooleanField(
        default=True,
        help_text="Indicates whether this provider's pricing is sourced from Infracost"
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.display_name



class CloudService(models.Model):
    """Cloud services (e.g. EC2, Azure VMs, GCP Compute Engine)"""
    provider = models.ForeignKey(CloudProvider, on_delete=models.CASCADE, related_name='services')
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ['provider', 'name']

    def __str__(self):
        return f"{self.provider.name.upper()} - {self.name}"


class Region(models.Model):
    """Cloud regions"""
    provider = models.ForeignKey(CloudProvider, on_delete=models.CASCADE, related_name='regions')
    name = models.CharField(max_length=100)  # e.g., us-east-1, eastus
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ['provider', 'name']

    def __str__(self):
        return f"{self.provider.name.upper()} - {self.name}"


class PricingModel(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Currency(models.Model):
    """Currency information"""
    code = models.CharField(max_length=10, unique=True)  # USD, EUR, GBP
    name = models.CharField(max_length=100)
    symbol = models.CharField(max_length=10)
    exchange_rate_to_usd = models.DecimalField(max_digits=18, decimal_places=10, null=True, blank=True)
    last_updated = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name_plural = "Currencies"

    def __str__(self):
        return f"{self.code} - {self.name}"


class NormalizedPricingData(models.Model):
    """Main normalized pricing record for Infracost and other providers"""
    provider = models.ForeignKey(CloudProvider, on_delete=models.CASCADE)
    service = models.ForeignKey(CloudService, on_delete=models.CASCADE)
    region = models.ForeignKey(Region, on_delete=models.CASCADE)
    pricing_model = models.ForeignKey(PricingModel, on_delete=models.CASCADE)
    currency = models.ForeignKey(Currency, on_delete=models.CASCADE)

    # Product details
    product_family = models.CharField(max_length=100, blank=True)  # Compute, Storage, etc.
    instance_type = models.CharField(max_length=100, blank=True)
    operating_system = models.CharField(max_length=100, blank=True)
    tenancy = models.CharField(max_length=50, blank=True)
    term_length = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)

    # Pricing values
    price_per_unit = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    price_unit = models.CharField(max_length=100, blank=True)

    raw_entry = models.ForeignKey('RawPricingData', on_delete=models.SET_NULL, null=True, blank=True, related_name='canonical_normalized')

    # Lifecycle tracking
    effective_date = models.DateTimeField(default=datetime.now)
    end_date = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    source_api = models.CharField(max_length=100, blank=True, default="infracost")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "normalized_pricing_data"
        indexes = [
            models.Index(fields=['provider', 'service', 'region']),
            models.Index(fields=['instance_type']),
            models.Index(fields=['effective_date']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        name = f"{self.provider.name.upper()} - {self.service.name}"
        if self.instance_type:
            return f"{name} - {self.instance_type}"
        return name


class PriceHistory(models.Model):
    """Historical pricing data"""
    pricing_data = models.ForeignKey('NormalizedPricingData', on_delete=models.CASCADE, related_name='history')
    price_per_unit = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    change_percentage = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    recorded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "price_history"
        ordering = ['-recorded_at']

    def __str__(self):
        return f"History for {self.pricing_data} at {self.recorded_at}"


class APICallLog(models.Model):
    """API call logs for monitoring and rate-limiting"""
    api_endpoint = models.URLField()
    status_code = models.IntegerField()
    records_updated = models.IntegerField(default=0)
    called_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-called_at']

    def __str__(self):
        return f"API call at {self.called_at}"


class RawPricingData(models.Model):
    """Raw pricing payloads from upstream sources (e.g. Infracost).

    Each price node received from an external API is stored here verbatim
    and uniquely identified by `product_hash`. Optionally linked to a normalized
    `NormalizedPricingData` record.
    """

    product_hash = models.CharField(
        max_length=200,
        unique=True,
        help_text="Unique hash of the raw pricing entry for deduplication"
    )
    raw_json = models.TextField(
        blank=True,
        null=True,
        help_text="Optional raw JSON payload for auditing/debugging"
    )
    normalized = models.ForeignKey(
        'NormalizedPricingData',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='raw_entries'
    )
    source_api = models.CharField(
        max_length=100,
        blank=True,
        default='infracost'
    )
    fetched_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "cloud_pricing_rawpricingdata"
        indexes = [
            models.Index(fields=['product_hash']),
            models.Index(fields=['fetched_at']),
        ]

    def __str__(self):
        return f"RawPricingData {self.product_hash} @ {self.fetched_at}"