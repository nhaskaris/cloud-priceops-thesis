import os
import gzip
import json
import tempfile
import logging
import requests

from django.utils import timezone
from decimal import Decimal
from datetime import datetime, timedelta

from celery import shared_task
from django.db import connection, transaction
from django.db.utils import IntegrityError
from django.conf import settings
from django.db.models import OuterRef, Subquery, Count

from .models import (
    CloudProvider,
    NormalizedPricingData,
    RawPricingData,
    CloudService,
    Region,
    PricingModel,
    Currency,
    APICallLog,
    PriceHistory,
)

from feast import FeatureStore
from feast.data_source import PushMode
import pandas as pd
from celery import shared_task
from django.db import connection
from django.utils import timezone as dj_timezone

logger = logging.getLogger(__name__)

DATA_DOWNLOAD_URL = "https://pricing.api.infracost.io/data-download/latest"
INFRACOST_API_KEY = os.getenv("INFRACOST_API_KEY")

@shared_task
def weekly_pricing_dump_update():
    """
    Fixed weekly pricing dump importer.
    - Downloads gz CSV to staging
    - Loads staging via COPY (or batch insert)
    - Creates missing canonical provider/service/region/pricing model/currency records
    - Parses pricing JSON, inserts raw entries, upserts normalized pricing
    """
    import gzip
    import csv
    import time
    import requests
    import tempfile
    import os

    if not INFRACOST_API_KEY:
        logger.error("INFRACOST_API_KEY not set")
        return "FAIL: no API key"

    # ---- helpers ----
    def _get_download_url():
        try:
            resp = requests.get(DATA_DOWNLOAD_URL,
                                headers={"X-Api-Key": INFRACOST_API_KEY},
                                timeout=60)
            resp.raise_for_status()
        except Exception as e:
            logger.exception("Error fetching dump metadata: %s", e)
            raise
        meta = resp.json()
        download_url = meta.get("downloadUrl")
        if not download_url:
            logger.error("downloadUrl not found in response: %s", meta)
            raise ValueError("no downloadUrl")
        return download_url

    def _download_to_tempfile(download_url):
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv.gz")
        tmp_path = tmp.name
        tmp.close()
        try:
            with requests.get(download_url, stream=True, timeout=120) as r2:
                r2.raise_for_status()
                with open(tmp_path, "wb") as f:
                    for chunk in r2.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
            logger.info("Downloaded dump to %s", tmp_path)
            return tmp_path
        except Exception:
            logger.exception("Download error")
            try:
                os.remove(tmp_path)
            except Exception:
                pass
            raise

    def _create_and_load_staging(tmp_path):
        staging_table = "infracost_staging_prices"
        with connection.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {staging_table}")
            cur.execute(f"""
                CREATE TABLE {staging_table} (
                  productHash text,
                  sku text,
                  vendorName text,
                  region text,
                  service text,
                  product_family text,
                  attributes text,
                  prices text
                );
            """)
            connection.commit()

            # Try psycopg2 COPY first, fall back to batch insert
            try:
                import psycopg2
                with gzip.open(tmp_path, "rt") as gzfile:
                    params = connection.get_connection_params()
                    pg2_conn = psycopg2.connect(
                        host=params.get('host', 'localhost'),
                        database=params.get('dbname'),
                        user=params.get('user'),
                        password=params.get('password'),
                        port=params.get('port', 5432)
                    )
                    pg2_cursor = pg2_conn.cursor()
                    pg2_cursor.copy_expert(f"""
                        COPY {staging_table}
                        (productHash, sku, vendorName, region, service,
                         product_family, attributes, prices)
                        FROM STDIN WITH CSV HEADER
                    """, gzfile)
                    pg2_conn.commit()
                    pg2_cursor.close()
                    pg2_conn.close()
            except Exception as e:
                logger.warning("psycopg2 COPY failed, falling back to batch insert: %s", e)
                with gzip.open(tmp_path, "rt") as gzfile:
                    reader = csv.DictReader(gzfile)
                    batch_size = 10000
                    rows_batch = []
                    for row in reader:
                        rows_batch.append((
                            row.get('productHash'),
                            row.get('sku'),
                            row.get('vendorName'),
                            row.get('region'),
                            row.get('service'),
                            row.get('product_family'),
                            row.get('attributes'),
                            row.get('prices')
                        ))
                        if len(rows_batch) >= batch_size:
                            cur.executemany(f"""
                                INSERT INTO {staging_table}
                                (productHash, sku, vendorName, region, service,
                                 product_family, attributes, prices)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            """, rows_batch)
                            connection.commit()
                            rows_batch.clear()
                    if rows_batch:
                        cur.executemany(f"""
                            INSERT INTO {staging_table}
                            (productHash, sku, vendorName, region, service,
                             product_family, attributes, prices)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """, rows_batch)
                        connection.commit()
        logger.info("Staging load complete into %s", staging_table)
        return staging_table

    # ---- orchestrate fetch/load ----
    try:
        download_url = _get_download_url()
    except ValueError:
        return "FAIL: no downloadUrl"
    except Exception as e:
        return f"FAIL: metadata error {e}"

    try:
        tmp_path = _download_to_tempfile(download_url)
    except Exception as e:
        return f"FAIL: download crashed {e}"

    try:
        staging_table = _create_and_load_staging(tmp_path)
    except Exception as e:
        logger.exception("Staging load failed: %s", e)
        return f"FAIL: staging load error {e}"

    # helper for canonical provider
    def canonical_provider_key(vendor_raw):
        if not vendor_raw:
            return None
        vl = vendor_raw.lower()
        if "amazon" in vl or "aws" in vl:
            return "aws"
        if "google" in vl or "gcp" in vl or "google cloud" in vl:
            return "gcp"
        if "microsoft" in vl or "azure" in vl:
            return "azure"
        if "ibm" in vl:
            return "ibm"
        if "oracle" in vl:
            return "oracle"
        return vl.replace(" ", "_").replace(".", "").replace("/", "_")

    # create canonical providers in DB if present
    with connection.cursor() as cur:
        cur.execute(f"""
            SELECT DISTINCT vendorName FROM {staging_table}
            WHERE vendorName IS NOT NULL AND vendorName != ''
        """)
        vendors = [r[0] for r in cur.fetchall()]

    if not vendors:
        logger.error("No vendorName found in staging table")
        return "FAIL: no vendorName in staging"

    seen_providers = set()
    for v in vendors:
        key = canonical_provider_key(v)
        if key in ("aws", "gcp", "azure"):
            seen_providers.add(key)

    for key in ("aws", "gcp", "azure", "ibm"):
        if key in seen_providers:
            display = {"aws": "Amazon Web Services", "gcp": "Google Cloud Platform", "azure": "Microsoft Azure"}[key]
            CloudProvider.objects.get_or_create(name=key, defaults={"display_name": display})

    currency, _ = Currency.objects.get_or_create(code="USD", defaults={"name": "US Dollar", "symbol": "$"})

    # ---- SQL processing (normalized keys + dedupe) ----
    logger.info("Processing staging data (normalized & deduped) with SQL...")
    start_time = time.time()
    total_saved = 0

    # TODO: upsert cloud service
    # From infracost_staging_prices table get service, vendorname to map to provider
    
    with connection.cursor() as cur:
        cur.execute(f"""
            INSERT INTO cloud_pricing_cloudservice
            (provider_id, name, is_active, created_at, updated_at)
            SELECT
                cp.id,
                s.service AS name,
                TRUE,
                NOW(),
                NOW()
            FROM (
                SELECT DISTINCT service, vendorName FROM {staging_table}
                WHERE service IS NOT NULL AND service != ''
            ) s
            JOIN cloud_pricing_cloudprovider cp
              ON cp.name = LOWER(s.vendorName)
        """)
        inserted = cur.rowcount
        connection.commit()
        logger.info("Inserted %d cloud service records", inserted)
    
    return

    # TODO: upsert pricing model
    # TODO: upsert region
    # TODO: upsert service category
    with connection.cursor() as cur:
        upsert_sql = f"""
        WITH staged AS (
            SELECT * FROM {staging_table} sp
            LEFT JOIN cloud_pricing_cloudprovider cp
              ON cp.name = LOWER(sp.vendorName)
            LEFT JOIN cloud_pricing_cloudservice cs
              ON cs.provider_id = cp.id AND cs.service_code = sp.service
        )
        INSERT INTO normalized_pricing_data
        (provider_id, service_id, region_id, pricing_model_id, currency_id,
         price_per_unit, effective_date, raw_entry_id, created_at, updated_at)
        SELECT
            s.provider_id,
            '',
            s.region_id,
            s.pricing_model_id,
            s.currency_id,
            s.price_per_unit,
            s.effective_date,
            re.id AS raw_entry_id,
            NOW(),
            NOW()
        FROM staged s
        """
        cur.execute(upsert_sql)
        total_saved = cur.rowcount

    final_elapsed = time.time() - start_time
    logger.info("✓ SQL processing complete: %d records processed in %.1fs", total_saved, final_elapsed)

    # cleanup
    try:
        os.remove(tmp_path)
    except OSError:
        logger.warning("Could not delete %s", tmp_path)

    # APICallLog(s)
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT DISTINCT provider_code FROM staging_parsed")
            provider_codes = [r[0] for r in cur.fetchall()]
        for pc in provider_codes:
            try:
                prov = CloudProvider.objects.get(name=pc)
            except CloudProvider.DoesNotExist:
                continue
            try:
                APICallLog.objects.create(
                    provider=prov,
                    api_endpoint=DATA_DOWNLOAD_URL,
                    status_code=200,
                    response_time=final_elapsed,
                    records_updated=total_saved,
                    error_message=""
                )
            except Exception:
                logger.exception("Failed to write APICallLog for provider %s", pc)
    except Exception:
        logger.exception("Failed to create APICallLog(s)")

    # drop staging
    # try:
    #     with connection.cursor() as cur:
    #         cur.execute(f"DROP TABLE IF EXISTS {staging_table}")
    #         connection.commit()
    #     logger.info("Staging table %s dropped successfully", staging_table)
    # except Exception as e:
    #     logger.warning("Could not drop staging table %s: %s", staging_table, e)

    return f"OK: saved {total_saved}"

@shared_task
def materialize_features(batch_size: int = 5000):
    """
    Materialize features into Feast offline (Postgres) + online (Redis) store.
    """
    fs = FeatureStore(repo_path="feature_repo")
    total_pushed = 0
    last_id = 0

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
                    LAG(price_per_unit) OVER (
                        PARTITION BY provider_id, service_id, region_id, instance_type,
                                    operating_system, tenancy, pricing_model_id
                        ORDER BY effective_date
                    ) AS previous_price
                FROM normalized_pricing_data
                WHERE id > %s
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
            IDX_PREV_PRICE,
        ) = range(11)
        batch_ids = [r[IDX_ID] for r in rows]

        # -----------------------------
        # 2. Get 90-day price change frequency
        # -----------------------------
        since = dj_timezone.now() - timedelta(days=90)
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT pricing_data_id, COUNT(*) AS cnt
                FROM price_history
                WHERE recorded_at >= %s
                  AND pricing_data_id = ANY(%s)
                GROUP BY pricing_data_id;
            """, [since, batch_ids])
            freq_map = {pid: cnt for pid, cnt in cursor.fetchall()}

        # -----------------------------
        # 3. Build feature rows
        # -----------------------------
        now = datetime.utcnow().replace(tzinfo=timezone.utc)
        feature_rows = []

        for r in rows:
            rec_id = r[IDX_ID]
            current_price = r[IDX_PRICE]
            previous_price = r[IDX_PREV_PRICE]
            effective_date = r[IDX_EFFECTIVE]

            # price diffs
            price_diff_abs = price_diff_pct = None
            if current_price is not None and previous_price is not None:
                try:
                    price_diff_abs = float(Decimal(current_price) - Decimal(previous_price))
                    if previous_price != 0:
                        price_diff_pct = float((Decimal(current_price) - Decimal(previous_price)) / Decimal(previous_price))
                except Exception:
                    pass

            # days since last change
            days_since_change = (now - effective_date).days if effective_date else None

            feature_rows.append({
                "pricing_data_id": rec_id,
                "event_timestamp": effective_date or now,
                "current_price": float(current_price) if current_price is not None else None,
                "previous_price": float(previous_price) if previous_price is not None else None,
                "price_diff_abs": price_diff_abs,
                "price_diff_pct": price_diff_pct,
                "days_since_price_change": float(days_since_change) if days_since_change is not None else None,
                "price_change_frequency_90d": float(freq_map.get(rec_id, 0)),
                "created": now
            })

        df = pd.DataFrame(feature_rows)

        # -----------------------------
        # 4. Insert into offline store table (Postgres)
        # -----------------------------
        if not df.empty:
            with connection.cursor() as cursor:
                cols = list(df.columns)
                values_str = ",".join(
                    cursor.mogrify(
                        f"({','.join(['%s']*len(cols))})", tuple(row)
                    )
                    for row in df.to_numpy()
                )
                insert_sql = f"""
                    INSERT INTO pricing_features ({','.join(cols)})
                    VALUES {values_str}
                    ON CONFLICT (pricing_data_id, event_timestamp) DO UPDATE SET
                        current_price = EXCLUDED.current_price,
                        previous_price = EXCLUDED.previous_price,
                        price_diff_abs = EXCLUDED.price_diff_abs,
                        price_diff_pct = EXCLUDED.price_diff_pct,
                        days_since_price_change = EXCLUDED.days_since_price_change,
                        price_change_frequency_90d = EXCLUDED.price_change_frequency_90d,
                        created = EXCLUDED.created;
                """
                cursor.execute(insert_sql)

        # -----------------------------
        # 5. Push to online store (Redis)
        # -----------------------------
        fs.push(
            push_source_name="pricing_data_push_source",
            df=df,
            to=PushMode.ONLINE
        )

        total_pushed += len(df)
        last_id = batch_ids[-1]

    return {"pushed": total_pushed}
