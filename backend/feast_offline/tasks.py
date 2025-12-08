import os
import pandas as pd
from datetime import timedelta
from celery import shared_task
from django.utils import timezone
from feast import FeatureStore
from feast.data_source import PushMode
import psycopg2
from psycopg2.extras import execute_values

from django.db import connection  # for queries

# Environment variables (no defaults)
POSTGRES_DB = os.environ["POSTGRES_DB"]
POSTGRES_USER = os.environ["POSTGRES_USER"]
POSTGRES_PASSWORD = os.environ["POSTGRES_PASSWORD"]
POSTGRES_HOST = os.environ["POSTGRES_HOST"]
POSTGRES_PORT = int(os.environ["POSTGRES_PORT"])


@shared_task
def materialize_features(batch_size: int = 5000):
    """
    Materialize features into Feast offline (Postgres) + online (Redis) store.
    Stores historical price updates using effective_date or updated_at.
    Uses raw psycopg2 connection for offline inserts to avoid encoding issues.
    """
    fs = FeatureStore(repo_path="feast_offline/feature_repo")
    total_pushed = 0
    last_id = 0

    # Raw psycopg2 connection for offline inserts
    pg_conn = psycopg2.connect(
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
    )

    try:
        while True:
            # -----------------------------
            # 1. Fetch batch from normalized_pricing_data with previous price
            # -----------------------------
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT
                        id,
                        provider_id,
                        service_id,
                        region_id,
                        instance_type,
                        operating_system,
                        tenancy,
                        pricing_model_id,
                        price_per_unit,
                        effective_date,
                        updated_at
                    FROM normalized_pricing_data
                    WHERE id > %s
                      AND price_per_unit > 0
                    ORDER BY id
                    LIMIT %s;
                """, [last_id, batch_size])
                rows = cursor.fetchall()

            if not rows:
                break

            (
                IDX_ID,
                IDX_PROVIDER_ID,
                IDX_SERVICE_ID,
                IDX_REGION_ID,
                IDX_INSTANCE_TYPE,
                IDX_OS,
                IDX_TENANCY,
                IDX_MODEL_ID,
                IDX_PRICE,
                IDX_EFFECTIVE,
                IDX_UPDATED,
            ) = range(11)

            batch_ids = [r[IDX_ID] for r in rows]

            # -----------------------------
            # 3. Build feature rows
            # -----------------------------
            feature_rows = []
            for r in rows:
                rec_id = r[IDX_ID]
                current_price = float(r[IDX_PRICE])
                effective_date = r[IDX_EFFECTIVE]
                updated_at = r[IDX_UPDATED]

                # Stable, deterministic event timestamp
                event_ts = effective_date or updated_at

                feature_rows.append({
                    "pricing_data_id": rec_id,
                    "event_timestamp": event_ts,
                    "current_price": current_price,
                })

            df = pd.DataFrame(feature_rows)

            # -----------------------------
            # 4. Insert into offline store (Postgres) using raw psycopg2
            # -----------------------------
            if not df.empty:
                cols = list(df.columns)
                insert_sql = f"""
                    INSERT INTO pricing_features ({', '.join(cols)})
                    VALUES %s
                    ON CONFLICT (pricing_data_id, event_timestamp) DO UPDATE SET
                        current_price = EXCLUDED.current_price;
                """
                with pg_conn.cursor() as cursor:
                    records = df.astype(object).to_records(index=False)
                    execute_values(cursor, insert_sql, records)
                pg_conn.commit()

            # -----------------------------
            # 5. Push to online store (Redis)
            # -----------------------------
            if not df.empty:
                fs.push(
                    push_source_name="pricing_data_push_source",
                    df=df,
                    to=PushMode.ONLINE
                )

            total_pushed += len(df)
            last_id = batch_ids[-1]

    finally:
        pg_conn.close()

    return {"pushed": total_pushed}
