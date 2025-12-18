import os
import logging

from django.utils import timezone

from .models import (
    CloudProvider,
    Currency,
    APICallLog,
    NormalizedPricingData
)

import csv
from celery import shared_task
from django.conf import settings
from django.core.files.storage import default_storage
from datetime import datetime

from django.db.models import Case, When, Value, FloatField, Q

from celery import shared_task
from django.db import connection

from .api.serializers import PricingDataSerializer 

# Import the base DRF serializers module for type checking
from rest_framework import serializers
logger = logging.getLogger(__name__)

DATA_DOWNLOAD_URL = "https://pricing.api.infracost.io/data-download/latest"
INFRACOST_API_KEY = os.getenv("INFRACOST_API_KEY")

def _return_sql_insert_normalized():
    return f"""
            -- CTE 1: Stage 1 data preparation
            WITH normalized_input_stage1 AS (
                SELECT
                    s.*,
                    price_elem,
                    cp.id AS provider_id,
                    cs.id AS service_id,
                    cr.id AS region_id,
                    c.id AS currency_id,
                    price_elem->>'USD' AS raw_price,
                    price_elem->>'unit' AS price_unit_raw,
                    price_elem->>'termPurchaseOption' AS term_purchase_option,
                    
                    -- The raw term length field
                    price_elem->>'termLength' AS term_length_year_raw, 

                    -- 1a. UNIFIED TERM EXTRACTION: Prioritize termLength, then purchaseOption/Pricing Model name
                    CASE
                        -- 1. Use termLength field if present and not empty (e.g., '3yr')
                        WHEN price_elem->>'termLength' IS NOT NULL AND price_elem->>'termLength' != '' 
                            THEN price_elem->>'termLength'
                        -- 2. Extract from purchaseOption/Pricing Model name (e.g., 'Commit3Yr' -> '3yr')
                        WHEN price_elem->>'purchaseOption' LIKE 'Commit%Yr' THEN 
                            regexp_replace(price_elem->>'purchaseOption', '[^0-9\.]', '', 'g') || 'yr'
                        WHEN price_elem->>'purchaseOption' LIKE 'Commit%Mo' THEN 
                            regexp_replace(price_elem->>'purchaseOption', '[^0-9\.]', '', 'g') || 'mo'
                        ELSE NULL -- Default to NULL if no term info is found
                    END AS extracted_term_length,

                    -- 1b. CLASSIFY the FINAL PRICING MODEL ID 
                    -- If a term was extracted, set model ID to NULL. Otherwise, use the ID from the (now LEFT) joined table.
                    CASE
                        -- If a term was extracted, set model ID to NULL
                        WHEN 
                            price_elem->>'termLength' IS NOT NULL AND price_elem->>'termLength' != '' OR
                            price_elem->>'purchaseOption' LIKE 'Commit%Yr' OR 
                            price_elem->>'purchaseOption' LIKE 'Commit%Mo'
                            THEN NULL 
                        -- Otherwise, use the ID derived from the pm table (which will be NULL if the LEFT JOIN failed)
                        ELSE pm.id 
                    END AS pricing_model_id,
                    
                    -- 2. CALCULATE NORMALIZED UNIT (rest of stage 1 remains the same)
                    CASE
                        WHEN LOWER(price_elem->>'unit') IN ('hrs', 'hours', 'hour', '1 hour', '1/hour', 'gibibyte/hour') THEN 'Hour'
                        WHEN LOWER(price_elem->>'unit') IN ('month', '1/month', 'user-month', 'gibibyte month') THEN 'Month'
                        WHEN LOWER(price_elem->>'unit') IN ('1 gb/month', '1 gb', 'gibibyte') THEN 'GB' 
                        WHEN price_elem->>'unit' IN ('1', '100', '1K', '10K', '1M', '1B', 'Quantity') THEN 'Unit' 
                        WHEN LOWER(price_elem->>'unit') = '1/day' THEN 'Day'
                        ELSE price_elem->>'unit' 
                    END AS normalized_price_unit,
                    
                    -- 3. PIVOT PRICE INTO TEMPORARY COLUMNS
                    CASE WHEN LOWER(price_elem->>'unit') IN ('hrs', 'hours', 'hour', '1 hour', '1/hour', 'gibibyte/hour') THEN (price_elem->>'USD')::numeric ELSE NULL END AS price_per_hour,
                    CASE WHEN LOWER(price_elem->>'unit') = '1/day' THEN (price_elem->>'USD')::numeric ELSE NULL END AS price_per_day,
                    CASE WHEN LOWER(price_elem->>'unit') IN ('month', '1/month', 'user-month', 'gibibyte month') THEN (price_elem->>'USD')::numeric ELSE NULL END AS price_per_month,
                    CASE WHEN LOWER(price_elem->>'unit') IN ('1 gb/month', '1 gb', 'gibibyte') THEN (price_elem->>'USD')::numeric ELSE NULL END AS price_per_gb,
                    
                    -- Price per Unit Count
                    CASE
                        WHEN price_elem->>'unit' = 'Quantity' OR price_elem->>'unit' IN ('1', '100') THEN (price_elem->>'USD')::numeric
                        WHEN price_elem->>'unit' = '1K' THEN (price_elem->>'USD')::numeric / 1000.0
                        WHEN price_elem->>'unit' = '10K' THEN (price_elem->>'USD')::numeric / 10000.0
                        WHEN price_elem->>'unit' = '1M' THEN (price_elem->>'USD')::numeric / 1000000.0
                        WHEN price_elem->>'unit' = '1B' THEN (price_elem->>'USD')::numeric / 1000000000.0
                        ELSE NULL
                    END AS price_per_unit_count

                FROM infracost_staging_prices s
                CROSS JOIN LATERAL jsonb_each(s.prices::jsonb) AS top_level(key, value)
                CROSS JOIN LATERAL jsonb_array_elements(value) AS price_elem
                JOIN cloud_pricing_cloudprovider cp ON cp.name = LOWER(s.vendorname)
                JOIN cloud_pricing_cloudservice cs ON cs.provider_id = cp.id AND cs.name = s.service
                JOIN cloud_pricing_region cr ON cr.provider_id = cp.id AND cr.name = s.region
                
                -- *** FIX APPLIED HERE: Changed from INNER JOIN to LEFT JOIN ***
                LEFT JOIN cloud_pricing_pricingmodel pm ON pm.name = COALESCE(price_elem->>'purchaseOption', 'on_demand')
                
                JOIN cloud_pricing_currency c ON c.code = 'USD'
                WHERE (price_elem->>'USD') IS NOT NULL
            ),
            -- CTE 2: Final normalization and calculation of features
            normalized_input AS (
                SELECT
                    s1.provider_id,
                    s1.service_id,
                    s1.region_id,
                    s1.pricing_model_id, -- Now correctly NULL for skipped models, or populated for joined models
                    s1.currency_id,
                    COALESCE(s1.attributes::jsonb->>'instanceFamily', '') AS product_family,
                    COALESCE(s1.attributes::jsonb->>'instanceType', '') AS instance_type,
                    COALESCE(s1.attributes::jsonb->>'operatingSystem', '') AS operating_system,
                    COALESCE(s1.attributes::jsonb->>'tenancy', '') AS tenancy,
                    s1.raw_price::numeric AS price_per_unit,

                    -- FINAL TERM LENGTH CLEANUP: Numeric years (Decimal) from extracted_term_length
                    CASE 
                        -- Check for year-based terms ('1yr', '3yr', etc.)
                        WHEN s1.extracted_term_length LIKE '%yr%' 
                        THEN NULLIF(regexp_replace(s1.extracted_term_length, '\D', '', 'g'), '')::numeric
                        
                        -- Check for month-based terms ('1mo', etc.) and convert to years by dividing by 12.0
                        WHEN s1.extracted_term_length LIKE '%mo%' 
                        THEN 
                            NULLIF(regexp_replace(s1.extracted_term_length, '\D', '', 'g'), '')::numeric / 12.0
                        ELSE NULL 
                    END AS term_length_year_clean,

                    -- 3. CALCULATE EFFECTIVE PRICE PER HOUR (Target Variable) (Logic unchanged)
                    (
                    COALESCE(
                        CASE 
                            -- 3A. AMORTIZE UPFRONT/QUANTITY FEES 
                            WHEN s1.normalized_price_unit IN ('Unit', 'Quantity') 
                                AND s1.term_purchase_option IS NOT NULL 
                                AND s1.term_purchase_option != 'No Upfront' 
                                AND (
                                        CASE
                                            WHEN s1.extracted_term_length LIKE '%yr%' THEN NULLIF(regexp_replace(s1.extracted_term_length, '\D', '', 'g'), '')::numeric
                                            WHEN s1.extracted_term_length LIKE '%mo%' THEN NULLIF(regexp_replace(s1.extracted_term_length, '\D', '', 'g'), '')::numeric / 12.0
                                            ELSE NULL 
                                        END
                                    ) IS NOT NULL
                            THEN 
                                (s1.raw_price::numeric) / 
                                (
                                    (
                                        CASE
                                            WHEN s1.extracted_term_length LIKE '%yr%' THEN NULLIF(regexp_replace(s1.extracted_term_length, '\D', '', 'g'), '')::numeric
                                            WHEN s1.extracted_term_length LIKE '%mo%' THEN NULLIF(regexp_replace(s1.extracted_term_length, '\D', '', 'g'), '')::numeric / 12.0
                                            ELSE NULL 
                                        END
                                    ) * 8766.0
                                ) 
                                
                            -- 3B. EXISTING LOGIC (Hourly, Daily, Monthly, GB)
                            WHEN s1.price_per_hour IS NOT NULL THEN s1.price_per_hour
                            WHEN s1.price_per_day IS NOT NULL  THEN s1.price_per_day / 24.0
                            WHEN s1.price_per_month IS NOT NULL THEN s1.price_per_month / 730.0
                            WHEN s1.normalized_price_unit = 'GB' AND s1.price_per_gb IS NOT NULL THEN s1.price_per_gb / 730.0 
                            
                            ELSE 0.0 
                        END, 
                        0.0
                    )) AS effective_price_per_hour,

                    -- 4. CONDITIONAL PRICE UNIT SELECTION (Logic unchanged)
                    CASE
                        WHEN 
                            COALESCE(
                                CASE 
                                    -- Check for Amortization case 
                                    WHEN s1.normalized_price_unit IN ('Unit', 'Quantity') 
                                        AND s1.term_purchase_option IS NOT NULL
                                        AND s1.term_purchase_option != 'No Upfront'
                                        AND (
                                                CASE
                                                    WHEN s1.extracted_term_length LIKE '%yr%' THEN NULLIF(regexp_replace(s1.extracted_term_length, '\D', '', 'g'), '')::numeric
                                                    WHEN s1.extracted_term_length LIKE '%mo%' THEN NULLIF(regexp_replace(s1.extracted_term_length, '\D', '', 'g'), '')::numeric / 12.0
                                                    ELSE NULL 
                                                END
                                            ) IS NOT NULL 
                                    THEN 1.0 
                                    
                                    -- Check for Standard Hourly/Daily/Monthly cases
                                    WHEN s1.price_per_hour IS NOT NULL THEN 1.0
                                    WHEN s1.price_per_day IS NOT NULL  THEN 1.0
                                    WHEN s1.price_per_month IS NOT NULL THEN 1.0
                                    WHEN s1.normalized_price_unit = 'GB' AND s1.price_per_gb IS NOT NULL THEN 1.0 
                                    
                                    ELSE 0.0
                                END, 
                                0.0
                            ) = 0.0 
                        THEN s1.price_unit_raw 
                        ELSE NULL
                    END AS price_unit,

                    -- 5. COMMITMENT FLAGS (Logic unchanged)
                    COALESCE(s1.term_purchase_option = 'All Upfront', FALSE) AS is_all_upfront,
                    COALESCE(s1.term_purchase_option = 'Partial Upfront', FALSE) AS is_partial_upfront,
                    COALESCE(s1.term_purchase_option = 'No Upfront', FALSE) AS is_no_upfront,
                    
                    COALESCE(s1.price_elem->>'description', '') AS description,
                    COALESCE(s1.term_length_year_raw, '') AS term_length_year_raw,
                    
                    NULLIF(regexp_replace(s1.attributes::jsonb->>'vcpu', '[^0-9]', '', 'g'), '')::integer AS vcpu_count,
                    CASE 
                        WHEN LOWER(COALESCE(s1.attributes::jsonb->>'storageType', '')) LIKE '%ssd%' THEN 'ssd'
                        WHEN LOWER(COALESCE(s1.attributes::jsonb->>'storageType', '')) LIKE '%hdd%' THEN 'hdd'
                        ELSE COALESCE(s1.attributes::jsonb->>'storageType', '')
                    END AS storage_type,
                    
                    -- memory_gb calculation
                    (
                        CASE 
                            WHEN s1.attributes::jsonb->>'memory' IS NULL OR s1.attributes::jsonb->>'memory' = '' THEN NULL
                            
                            ELSE 
                                (
                                    NULLIF(
                                        regexp_replace(s1.attributes::jsonb->>'memory', '[^0-9\.]', '', 'g'), 
                                        ''
                                    )
                                )::numeric 
                                * CASE 
                                    WHEN LOWER(s1.attributes::jsonb->>'memory') LIKE '%tib%' THEN 1024.0
                                    WHEN LOWER(s1.attributes::jsonb->>'memory') LIKE '%kib%' THEN 1.0 / 1048576.0 
                                    WHEN LOWER(s1.attributes::jsonb->>'memory') LIKE '%mib%' THEN 1.0 / 1024.0 
                                    WHEN LOWER(s1.attributes::jsonb->>'memory') LIKE '%gib%' THEN 1.0
                                    ELSE 1.0
                                END
                        END
                    ) AS memory_gb,
                    
                    classify_domain(
                        s1.service, 
                        s1.attributes::jsonb->>'instanceType'
                    ) AS domain_label,
                    s1.producthash AS product_hash,
                    NOW() AS created_at,
                    NOW() AS updated_at,
                    'infracost' AS source_api
                FROM normalized_input_stage1 s1
            ),
            -- CTE 3: Final INSERT statement (Unchanged)
            inserted_rows AS (
                INSERT INTO normalized_pricing_data (
                    provider_id, service_id, region_id, pricing_model_id, currency_id,
                    product_family, instance_type, operating_system, tenancy,
                    price_per_unit, price_unit,
                    description, term_length_years,
                    raw_entry_id,
                    effective_date, is_active, source_api,
                    created_at, updated_at, vcpu_count, storage_type, domain_label,
                    memory_gb,
                    effective_price_per_hour,
                    
                    -- NEW COLUMNS MAPPING
                    is_all_upfront,
                    is_partial_upfront,
                    is_no_upfront
                )
                SELECT
                    n.provider_id, n.service_id, n.region_id, n.pricing_model_id, n.currency_id,
                    n.product_family, n.instance_type, n.operating_system, n.tenancy,
                    n.price_per_unit, n.price_unit,
                    n.description, n.term_length_year_clean,
                    r.id AS raw_entry_id,
                    NOW(), TRUE, n.source_api,
                    n.created_at, n.updated_at, n.vcpu_count, n.storage_type, n.domain_label,
                    n.memory_gb,
                    n.effective_price_per_hour,
                    
                    -- NEW COLUMNS SELECTION
                    n.is_all_upfront,
                    n.is_partial_upfront,
                    n.is_no_upfront
                    
                FROM normalized_input n
                JOIN cloud_pricing_rawpricingdata r ON r.product_hash = n.product_hash
                RETURNING id
            )
            SELECT COUNT(*) AS inserted_count FROM inserted_rows;
            """

def _return_sql_check_updates_normalized():
    return """
            WITH normalized_input AS (
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

                    COALESCE(s.attributes::jsonb->>'vcpu', NULL)::integer AS vcpu_count,
                    CASE 
                        WHEN LOWER(COALESCE(s.attributes::jsonb->>'storageType', '')) LIKE '%ssd%' THEN 'ssd'
                        WHEN LOWER(COALESCE(s.attributes::jsonb->>'storageType', '')) LIKE '%hdd%' THEN 'hdd'
                        ELSE COALESCE(s.attributes::jsonb->>'storageType', '')
                    END AS storage_type,

                    s.producthash AS product_hash,
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
            updated_rows AS (
                UPDATE normalized_pricing_data dst
                SET
                    price_per_unit = src.price_per_unit,
                    description = src.description,
                    term_length_year = src.term_length_year,
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
            SELECT 
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

    import os

    def _create_and_load_staging(tmp_path):
        staging_table = "infracost_staging_prices"
        max_rows = 10000 if os.getenv("DEV", "").lower() in ("1", "true", "yes") else None
        total_rows = 0

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

            # Always use batch insert in DEV
            use_batch_insert = bool(max_rows)

            if not use_batch_insert:
                # PROD: try COPY first
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
                        # estimate total rows from file
                        with gzip.open(tmp_path, "rt") as f:
                            total_rows = sum(1 for _ in f) - 1  # minus header
                except Exception as e:
                    logger.warning("psycopg2 COPY failed, falling back to batch insert: %s", e)
                    use_batch_insert = True

            if use_batch_insert:
                # DEV or fallback: batch insert with max_rows
                with gzip.open(tmp_path, "rt") as gzfile:
                    import csv
                    reader = csv.DictReader(gzfile)
                    batch_size = 1000
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
                        total_rows += 1
                        if len(rows_batch) >= batch_size:
                            cur.executemany(f"""
                                INSERT INTO {staging_table}
                                (productHash, sku, vendorName, region, service,
                                product_family, attributes, prices)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            """, rows_batch)
                            connection.commit()
                            rows_batch.clear()

                        if max_rows and total_rows >= max_rows:
                            break

                    if rows_batch:
                        cur.executemany(f"""
                            INSERT INTO {staging_table}
                            (productHash, sku, vendorName, region, service,
                            product_family, attributes, prices)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """, rows_batch)
                        connection.commit()

        logger.info("Staging load complete into %s (loaded %d rows)", staging_table, total_rows)
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

    with connection.cursor() as cur:
        sql = f"""
            INSERT INTO cloud_pricing_pricingmodel (name)
            SELECT DISTINCT
                -- 1. Normalize the name for insertion
                CASE
                    -- Normalize all forms of Spot/Low Priority pricing
                    WHEN LOWER(COALESCE(elem->>'purchaseOption', '')) IN ('spot', 'low priority', 'preemptible', 'cmt cud premium', 'reserved') 
                         OR LOWER(COALESCE(elem->>'purchaseOption', '')) LIKE '%spot%'
                         OR LOWER(COALESCE(elem->>'purchaseOption', '')) LIKE '%low priority%'
                         THEN 'Spot'
                    
                    -- Normalize all forms of On-Demand/Consumption pricing
                    WHEN LOWER(COALESCE(elem->>'purchaseOption', '')) IN ('consumption', 'devtestconsumption', 'on_demand')
                         OR LOWER(COALESCE(elem->>'purchaseOption', '')) LIKE '%ondemand%'
                         THEN 'OnDemand'

                    -- If it's a known non-standard term, keep the original (or use 'Reserved' if needed)
                    WHEN LOWER(COALESCE(elem->>'purchaseOption', '')) = 'reservation' THEN 'Reserved'
                    WHEN LOWER(COALESCE(elem->>'purchaseOption', '')) = 'preemptible' THEN 'Preemptible'

                    -- Default to OnDemand for anything not explicitly handled, 
                    -- which should be rare if the filters below work.
                    ELSE COALESCE(elem->>'purchaseOption', 'OnDemand')
                END AS normalized_name
            FROM (
                SELECT json_array_elements(value)::json AS elem
                FROM {staging_table},
                    json_each(prices::json) AS t(key, value)
            ) sub
            WHERE 
                COALESCE(elem->>'purchaseOption', '') <> ''
                -- 2. FILTER OUT: Skip inserting specific commitment terms
                AND LOWER(COALESCE(elem->>'purchaseOption', '')) NOT LIKE '%commit%yr%'
                AND LOWER(COALESCE(elem->>'purchaseOption', '')) NOT LIKE '%commit%mo%'
                AND LOWER(COALESCE(elem->>'purchaseOption', '')) NOT LIKE '%reservation%' -- Also filter generic Reservation model names
                AND LOWER(COALESCE(elem->>'purchaseOption', '')) NOT LIKE '%reserved%'
            
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
    
    # 1. Only check updates if normalized table is not empty
    with connection.cursor() as cur:
        cur.execute("SELECT EXISTS (SELECT 1 FROM normalized_pricing_data LIMIT 1);")
        normalized_has_rows = cur.fetchone()[0]
    
    # 2. Insert new rows
    with connection.cursor() as cur:
        cur.execute(_return_sql_insert_normalized())
        inserted_count = cur.fetchone()[0]
        connection.commit()
        total_saved += inserted_count
        logger.info("Inserted %d new normalized rows", inserted_count)

    # 3. Update changed rows
    if normalized_has_rows:
        with connection.cursor() as cur:
            cur.execute(_return_sql_check_updates_normalized())
            updated_count = cur.fetchone()[0]
            connection.commit()
            total_saved += updated_count
            logger.info("Updated %d normalized rows", updated_count)

    final_elapsed = time.time() - start_time
    logger.info("✓ SQL processing complete: %d records processed in %.1fs", total_saved, final_elapsed)

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
    # try:
    #     with connection.cursor() as cur:
    #         cur.execute(f"DROP TABLE IF EXISTS {staging_table}")
    #         connection.commit()
    #     logger.info("Staging table %s dropped successfully", staging_table)
    # except Exception as e:
    #     logger.warning("Could not drop staging table %s: %s", staging_table, e)

    return f"OK: saved {total_saved}"

@shared_task(bind=True)
def export_pricing_data_to_csv(self, filters):
    """
    Queries the database based on client filters, generates a CSV, and saves it,
    using the fields defined in PricingDataSerializer.
    """

    logger.info(f"Starting CSV export task {self.request.id} with filters: {filters}")
    
    # Base QuerySet - must match the mandatory filters from the view's get_queryset
    queryset = NormalizedPricingData.objects.filter(is_active=True, effective_price_per_hour__gt=0)
    
    # Apply Filters (Example handling for 'domain_label' from query params)
    domain_label_list = filters.get('domain_label')
    if domain_label_list:
        queryset = queryset.filter(domain_label=domain_label_list[0])

    min_data_completeness_val = filters.get('min_data_completeness')

    if min_data_completeness_val and str(min_data_completeness_val[0]).lower() == 'true':
        queryset = queryset.exclude(
            Q(vcpu_count__isnull=True) | 
            Q(memory_gb__isnull=True) | 
            Q(product_family='') |
            Q(product_family__isnull=True)
        )
        logger.info("Filtering for complete data only (min_data_completeness=True)")
    
    # Limit to 10k rows in DEV mode
    if os.getenv("DEV", "").lower() in ("1", "true", "yes"):
        queryset = queryset[:10000]

    # --- START REFACTORED SECTION ---
    
    # 1. Define Fields and Headers using the Serializer
    
    # Instantiate the serializer (it doesn't need data, just field definitions)
    serializer_instance = PricingDataSerializer()
    
    fields_to_export = []
    headers = []
    
    serializer_instance = PricingDataSerializer()
    
    for field_name, field_object in serializer_instance.fields.items():
        # 1. Determine the database lookup
        db_lookup = field_name
        if isinstance(field_object, serializers.StringRelatedField):
            db_lookup = f'{field_name}__name'
        
        fields_to_export.append(db_lookup)
        
        # 2. Keep the header EXACTLY the same as the serializer field name
        # Do NOT use .title() or .replace('_', ' ')
        headers.append(field_name) 

    # 3. Fetch data
    data_values = queryset.values_list(*fields_to_export)
    
    # --- END REFACTORED SECTION ---
    
    # 3. Save the CSV to a temporary location
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    file_name = f'pricing_export_{timestamp}_{self.request.id}.csv' 
    temp_path = default_storage.path(file_name) 

    try:
        with open(temp_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(headers)
            writer.writerows(data_values)
        
        os.chmod(temp_path, 0o644)

        file_size = default_storage.size(file_name)
        logger.info(f"Task {self.request.id}: CSV file generated successfully at {temp_path}. Size: {file_size}")

        # 4. Return the result path
        return {'file_name': file_name, 'file_size': file_size}
    
    except Exception as e:
        logger.error(f"Task {self.request.id} failed during CSV generation: {e}")
        raise