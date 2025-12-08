from django.db import models


class PricingFeatureRecord(models.Model):
    """
    This table stores historical features for Feast offline store.
    Feast expects the schema + event_timestamp + created columns.
    """

    pricing_data_id = models.BigIntegerField(db_index=True)
    event_timestamp = models.DateTimeField()  # Feast-required column
    current_price = models.FloatField(null=True)

    class Meta:
        db_table = "pricing_features"
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
