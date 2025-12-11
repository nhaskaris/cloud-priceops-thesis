import os
import logging

from django.utils import timezone

from .models import (
    CloudProvider,
    Currency,
    APICallLog,
)

from celery import shared_task
from django.db import connection

logger = logging.getLogger(__name__)

DATA_DOWNLOAD_URL = "https://pricing.api.infracost.io/data-download/latest"
INFRACOST_API_KEY = os.getenv("INFRACOST_API_KEY")

def _return_sql_string_to_execute():
    return """
WITH

-- -----------------------------------------------
-- 1. Extract normalized rows from staging
-- -----------------------------------------------
normalized_input AS (
    SELECT
        cp.id AS provider_id,
        cs.id AS service_id,
        cr.id AS region_id,
        pm.id AS pricing_model_id,
        c.id AS currency_id,

        COALESCE(s.attributes::jsonb->>'instanceFamily', '') AS product_family,
        COALESCE(s.attributes::jsonb->>'instanceType', '') AS instance_type,
        COALESCE(s.attributes::jsonb->>'operatingSystem', '') AS operating_system,
        COALESCE(s.attributes::jsonb->>'tenancy', '') AS tenancy,

        (price_elem->>'USD')::numeric AS price_per_unit,
        price_elem->>'unit' AS price_unit,

        COALESCE(price_elem->>'description', '') AS description,
        COALESCE(regexp_replace(price_elem->>'termLength', '\D', '', 'g'), '') AS term_length_year,

        CASE
            WHEN price_elem->>'effectiveDateStart' ~ '^[A-Z][a-z]{2} [A-Z][a-z]{2}' THEN
                to_timestamp(
                    regexp_replace(
                        price_elem->>'effectiveDateStart',
                        '^([A-Za-z]{3}) ([A-Za-z]{3}) (\\d{2}) (\\d{4}) (\\d{2}:\\d{2}:\\d{2}).*$',
                        '\\4-\\2-\\3 \\5',
                        'g'
                    ),
                    'YYYY-Mon-DD HH24:MI:SS'
                ) AT TIME ZONE 'UTC'
            ELSE
                (price_elem->>'effectiveDateStart')::timestamptz
        END AS effective_date,

        s.producthash AS product_hash,
        NOW() AS created_at,
        NOW() AS updated_at,
        'infracost' AS source_api

    FROM infracost_staging_prices s
    CROSS JOIN LATERAL jsonb_each(s.prices::jsonb) AS top_level(key, value)
    CROSS JOIN LATERAL jsonb_array_elements(value) AS price_elem
    JOIN cloud_pricing_cloudprovider cp ON cp.name = LOWER(s.vendorname)
    JOIN cloud_pricing_cloudservice cs ON cs.provider_id = cp.id AND cs.name = s.service
    JOIN cloud_pricing_region cr ON cr.provider_id = cp.id AND cr.name = s.region
    JOIN cloud_pricing_pricingmodel pm ON pm.name = COALESCE(price_elem->>'purchaseOption', 'on_demand')
    JOIN cloud_pricing_currency c ON c.code = 'USD'
    WHERE (price_elem->>'USD') IS NOT NULL
),

-- -----------------------------------------------
-- 2. Insert missing normalized pricing rows
-- -----------------------------------------------
inserted_rows AS (
    INSERT INTO normalized_pricing_data (
        provider_id, service_id, region_id, pricing_model_id, currency_id,
        product_family, instance_type, operating_system, tenancy,
        price_per_unit, price_unit,
        description, term_length_year,
        raw_entry_id,
        effective_date, is_active, source_api,
        created_at, updated_at
    )
    SELECT
        n.provider_id, n.service_id, n.region_id, n.pricing_model_id, n.currency_id,
        n.product_family, n.instance_type, n.operating_system, n.tenancy,
        n.price_per_unit, n.price_unit,
        n.description, n.term_length_year,
        r.id AS raw_entry_id,
        n.effective_date, TRUE, n.source_api,
        n.created_at, n.updated_at
    FROM normalized_input n
    JOIN cloud_pricing_rawpricingdata r ON r.product_hash = n.product_hash
    WHERE NOT EXISTS (
        SELECT 1
        FROM normalized_pricing_data x
        WHERE x.provider_id = n.provider_id
          AND x.service_id = n.service_id
          AND x.region_id = n.region_id
          AND x.pricing_model_id = n.pricing_model_id
          AND x.currency_id = n.currency_id
          AND x.product_family = n.product_family
          AND x.instance_type = n.instance_type
          AND x.operating_system = n.operating_system
          AND x.tenancy = n.tenancy
          AND x.price_unit = n.price_unit
    )
    RETURNING id AS new_id
),

-- -----------------------------------------------
-- 3. Detect price changes
-- -----------------------------------------------
changed AS (
    SELECT
        old.id AS normalized_id,
        old.price_per_unit AS old_price,
        newd.price_per_unit AS new_price
    FROM normalized_pricing_data old
    JOIN normalized_input newd
        ON old.provider_id = newd.provider_id
       AND old.service_id = newd.service_id
       AND old.region_id = newd.region_id
       AND old.pricing_model_id = newd.pricing_model_id
       AND old.currency_id = newd.currency_id
       AND old.product_family = newd.product_family
       AND old.instance_type = newd.instance_type
       AND old.operating_system = newd.operating_system
       AND old.tenancy = newd.tenancy
       AND old.price_unit = newd.price_unit
    WHERE old.price_per_unit <> newd.price_per_unit
),

-- -----------------------------------------------
-- 4. Insert price history
-- -----------------------------------------------
history_insert AS (
    INSERT INTO price_history (pricing_data_id, price_per_unit, change_percentage, recorded_at)
    SELECT
        normalized_id,
        new_price,
        CASE WHEN old_price = 0 THEN NULL
             ELSE ROUND(((new_price - old_price) / old_price) * 100.0, 2)
        END,
        NOW()
    FROM changed
    RETURNING pricing_data_id
),

-- -----------------------------------------------
-- 5. Update existing normalized records
-- -----------------------------------------------
updated_rows AS (
    UPDATE normalized_pricing_data dst
    SET
        price_per_unit = src.price_per_unit,
        description = src.description,
        term_length_year = src.term_length_year,
        effective_date = src.effective_date,
        updated_at = NOW()
    FROM normalized_input src
    WHERE dst.provider_id = src.provider_id
      AND dst.service_id = src.service_id
      AND dst.region_id = src.region_id
      AND dst.pricing_model_id = src.pricing_model_id
      AND dst.currency_id = src.currency_id
      AND dst.product_family = src.product_family
      AND dst.instance_type = src.instance_type
      AND dst.operating_system = src.operating_system
      AND dst.tenancy = src.tenancy
      AND dst.price_unit = src.price_unit
    RETURNING dst.id
)

-- -----------------------------------------------
-- 6. Return counts
-- -----------------------------------------------
SELECT 
    (SELECT COUNT(*) FROM inserted_rows) AS inserted_count,
    (SELECT COUNT(*) FROM updated_rows) AS updated_count;
"""

def _return_sql_string_raw():
    return """
INSERT INTO cloud_pricing_rawpricingdata (
    product_hash,
    raw_json,
    source_api,
    fetched_at
)
SELECT
    s.producthash AS product_hash,
    s.prices::jsonb::text AS raw_json,
    'infracost' AS source_api,
    NOW() AS fetched_at
FROM infracost_staging_prices s
ON CONFLICT (product_hash) DO NOTHING;
"""

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
        logger.info("Fetched download URL")
        logger.info("Download URL: %s", download_url)
        return download_url

    def _download_to_tempfile(download_url):
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv.gz")
        tmp_path = tmp.name
        tmp.close()
        try:
            with requests.get(download_url, stream=True, timeout=120) as r2:
                r2.raise_for_status()
                total_size = int(r2.headers.get('content-length', 0))
                downloaded = 0
                last_logged_progress = 0
                with open(tmp_path, "wb") as f:
                    for chunk in r2.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size:
                                progress = (downloaded / total_size) * 100
                                if progress - last_logged_progress >= 10:
                                    logger.info("Download progress: %.1f%% (%d / %d bytes)", 
                                              progress, downloaded, total_size)
                                    last_logged_progress = progress
                            else:
                                logger.info("Downloaded: %d bytes", downloaded)
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
    LOCAL_DIR = "/app/data"
    LOCAL_PATH = os.path.join(LOCAL_DIR, "dump.csv.gz")
    os.makedirs(LOCAL_DIR, exist_ok=True)

    # --- If local dump exists, skip network ---
    if os.path.exists(LOCAL_PATH):
        logger.info("Using local Infracost dump: %s", LOCAL_PATH)
        tmp_path = LOCAL_PATH
    else:
        logger.info("Local dump not found. Downloading new dump...")
        
        try:
            download_url = _get_download_url()
        except ValueError:
            return "FAIL: no downloadUrl"
        except Exception as e:
            return f"FAIL: metadata error {e}"

        # Download and save locally
        tmp_path = LOCAL_PATH
        try:
            with requests.get(download_url, stream=True, timeout=120) as r2:
                r2.raise_for_status()
                with open(tmp_path, "wb") as f:
                    for chunk in r2.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
            logger.info("Downloaded dump to %s", tmp_path)
        except Exception:
            logger.exception("Download error")
            try:
                os.remove(tmp_path)
            except Exception:
                pass
            return "FAIL: download crashed"

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

    # Insert Cloud Service
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
            ON CONFLICT (provider_id, name) DO NOTHING;
        """)
        inserted = cur.rowcount
        connection.commit()
        logger.info("Inserted %d cloud service records", inserted)

    # Insert Region
    with connection.cursor() as cur:
        cur.execute(f"""
            INSERT INTO cloud_pricing_region
            (provider_id, name, is_active, created_at)
            SELECT
                cp.id,
                s.region AS name,
                TRUE,
                NOW()
            FROM (
                SELECT DISTINCT region, vendorName FROM {staging_table}
                WHERE region IS NOT NULL AND region != ''
            ) s
            JOIN cloud_pricing_cloudprovider cp
              ON cp.name = LOWER(s.vendorName)
            ON CONFLICT (provider_id, name) DO NOTHING;
        """)
        inserted = cur.rowcount
        connection.commit()
        logger.info("Inserted %d region records", inserted)

    # Insert Pricing Model
    with connection.cursor() as cur:
        sql = f"""
            INSERT INTO cloud_pricing_pricingmodel (name)
            SELECT DISTINCT
                COALESCE(elem->>'purchaseOption', 'on_demand')
            FROM (
                SELECT json_array_elements(value)::json AS elem
                FROM {staging_table},
                    json_each(prices::json) AS t(key, value)
            ) sub
            WHERE COALESCE(elem->>'purchaseOption', '') <> ''
            ON CONFLICT (name) DO NOTHING;
        """

        cur.execute(sql)
        inserted = cur.rowcount
        connection.commit()
        logger.info("Inserted %d pricing model records", inserted)

    # Insert RawPricingData
    sql = _return_sql_string_raw()
    with connection.cursor() as cur:
        cur.execute(sql)
        inserted = cur.rowcount
        connection.commit()
        total_saved += inserted
        logger.info("Inserted %d raw pricing data records", inserted)

    # Upsert NormalizedPricingData
    sql = _return_sql_string_to_execute()
    with connection.cursor() as cur:
        cur.execute(sql)
        inserted_count, updated_count = cur.fetchone()
        connection.commit()
        total_saved += inserted_count + updated_count
        logger.info("Inserted %d normalized rows, updated %d rows", inserted_count, updated_count)


    final_elapsed = time.time() - start_time
    logger.info("✓ SQL processing complete: %d records processed in %.1fs", total_saved, final_elapsed)

    # cleanup
    try:
        os.remove(tmp_path)
    except OSError:
        logger.warning("Could not delete %s", tmp_path)

    # APICallLog(s)
    try:
        APICallLog.objects.create(
            api_endpoint=DATA_DOWNLOAD_URL,  # the URL you fetched
            status_code=200,                  # success
            records_updated=total_saved,      # number of rows upserted
            called_at=timezone.now()          # timestamp
        )
    except Exception:
        logger.exception("Failed to create APICallLog")

    # drop staging
    try:
        with connection.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {staging_table}")
            connection.commit()
        logger.info("Staging table %s dropped successfully", staging_table)
    except Exception as e:
        logger.warning("Could not drop staging table %s: %s", staging_table, e)

    return f"OK: saved {total_saved}"