from django.db import models


class PricingFeatureRecord(models.Model):
    """
    This table stores historical features for Feast offline store.
    Feast expects the schema + event_timestamp + created columns.
    """

    pricing_data_id = models.BigIntegerField(db_index=True)

    event_timestamp = models.DateTimeField()  # Feast-required column

    current_price = models.FloatField(null=True)
    previous_price = models.FloatField(null=True)
    price_diff_abs = models.FloatField(null=True)
    price_diff_pct = models.FloatField(null=True)
    days_since_price_change = models.FloatField(null=True)
    price_change_frequency_90d = models.FloatField(null=True)

    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pricing_features"  # MUST match Feast PostgreSQLSource table
        indexes = [
            models.Index(fields=["pricing_data_id"]),
            models.Index(fields=["event_timestamp"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["pricing_data_id", "event_timestamp"],
                name="uq_pricing_data_event"
            )
        ]
