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
    pricing_model = models.ForeignKey(PricingModel, on_delete=models.CASCADE, null=True, blank=True)
    currency = models.ForeignKey(Currency, on_delete=models.CASCADE)

    # Product details
    product_family = models.CharField(max_length=100, blank=True)
    instance_type = models.CharField(max_length=100, blank=True)
    operating_system = models.CharField(max_length=100, blank=True)
    tenancy = models.CharField(max_length=50, blank=True)
    term_length_years = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    description = models.TextField(blank=True)
    vcpu_count = models.IntegerField(null=True, blank=True)
    memory_gb = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    storage_type = models.CharField(max_length=100, blank=True, null=True)
    domain_label = models.CharField(max_length=100, blank=True, null=True)

    # Pricing values
    price_per_unit = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    price_unit = models.CharField(max_length=100, blank=True, null=True)
    effective_price_per_hour = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    is_all_upfront = models.BooleanField(
        default=False,
    )
    is_partial_upfront = models.BooleanField(
        default=False,
    )
    is_no_upfront = models.BooleanField(
        default=False,
    )

    raw_entry = models.ForeignKey('RawPricingData', on_delete=models.SET_NULL, null=True, blank=True, related_name='canonical_normalized')

    # Lifecycle tracking
    effective_date = models.DateTimeField(default=datetime.now, null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    source_api = models.CharField(max_length=100, blank=True, default="infracost")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "normalized_pricing_data"
        # UNIQUE constraint for ON CONFLICT upserts

        indexes = [
            # Existing useful indexes
            models.Index(fields=['effective_date']),
            models.Index(fields=['is_active']),
            models.Index(fields=['price_per_unit'], name='idx_price_positive', condition=models.Q(price_per_unit__gt=0)),

            # Index for raw_entry joins
            models.Index(fields=['raw_entry'], name='idx_npd_raw_entry'),

            # Composite index for effective date filtering
            models.Index(
                fields=['is_active', 'effective_date'],
                name='idx_npd_active_effective'
            ),

            # Index for source_api queries
            models.Index(fields=['source_api'], name='idx_npd_source_api'),

            # Index for provider-service-region combinations
            models.Index(
                fields=['provider', 'service', 'region'],
                name='idx_npd_prov_serv_reg'
            ),
        ]

    def __str__(self):
        name = f"{self.provider.name.upper()} - {self.service.name}"
        if self.instance_type:
            return f"{name} - {self.instance_type}"
        return name


class APICallLog(models.Model):
    """API call logs and system performance metrics for KPI tracking"""
    # API Call Information
    api_endpoint = models.URLField(blank=True, null=True)
    status_code = models.IntegerField(null=True, blank=True)
    
    # Performance Metrics
    duration_seconds = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="Time taken to complete the operation in seconds"
    )
    records_processed = models.IntegerField(
        default=0,
        help_text="Total number of records processed"
    )
    records_updated = models.IntegerField(default=0)
    records_inserted = models.IntegerField(default=0, help_text="Number of new records created")
    records_failed = models.IntegerField(default=0, help_text="Number of records that failed processing")
    
    # Data Quality Metrics
    normalization_success_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Percentage of records successfully normalized (0-100)"
    )
    
    # Throughput Metrics
    throughput_records_per_second = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Number of records processed per second"
    )
    
    # Additional Context
    error_message = models.TextField(
        blank=True,
        null=True,
        help_text="Error details if operation failed"
    )
    metadata = models.JSONField(
        null=True,
        blank=True,
        help_text="Additional metadata about the operation (JSON format)"
    )
    
    # Timestamps
    called_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-called_at']
        indexes = [
            models.Index(fields=['called_at']),
            models.Index(fields=['-called_at']),
        ]

    def __str__(self):
        return f"API call at {self.called_at}"
    
    def calculate_metrics(self):
        """Calculate derived metrics based on recorded data"""
        if self.records_processed and self.records_processed > 0:
            # Calculate success rate
            successful = self.records_processed - self.records_failed
            self.normalization_success_rate = (successful / self.records_processed) * 100
            
            # Calculate throughput
            if self.duration_seconds and self.duration_seconds > 0:
                self.throughput_records_per_second = self.records_processed / float(self.duration_seconds)
        
        # Calculate duration if completed_at is set
        if self.completed_at and self.called_at:
            delta = self.completed_at - self.called_at
            self.duration_seconds = delta.total_seconds()


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