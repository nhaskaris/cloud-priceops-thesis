# feature_repo/schema.py
from datetime import timedelta
from feast import Entity, FeatureView, Field, PushSource
from feast.types import Float64
from feast import ValueType
from feast.infra.offline_stores.contrib.postgres_offline_store.postgres_source import PostgreSQLSource

# -------------------------
# ENTITY
# -------------------------
pricing_data = Entity(
    name="pricing_data",
    join_keys=["pricing_data_id"],
    value_type=ValueType.INT64,
)

# -------------------------
# OFFLINE SOURCE (PostgreSQL)
# -------------------------
pricing_postgres_source = PostgreSQLSource(
    name="pricing_features_source",
    query="SELECT * FROM pricing_features",
    timestamp_field="event_timestamp",
)

# -------------------------
# PUSH SOURCE (for online store)
# -------------------------
pricing_data_push = PushSource(
    name="pricing_data_push_source",
    batch_source=pricing_postgres_source
)

# -------------------------
# FEATURE VIEW
# -------------------------
pricing_fv = FeatureView(
    name="pricing_data_features",
    entities=[pricing_data],
    ttl=timedelta(days=365),
    schema=[
        Field(name="current_price", dtype=Float64),
    ],
    source=pricing_data_push,  # use push source for real-time feature updates
    online=True,  # allow push to online store for real-time retrieval
)
