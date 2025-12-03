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
    ServiceCategory,
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
                  productFamily text,
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
                         productFamily, attributes, prices)
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
                            row.get('productFamily'),
                            row.get('attributes'),
                            row.get('prices')
                        ))
                        if len(rows_batch) >= batch_size:
                            cur.executemany(f"""
                                INSERT INTO {staging_table}
                                (productHash, sku, vendorName, region, service,
                                 productFamily, attributes, prices)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            """, rows_batch)
                            connection.commit()
                            rows_batch.clear()
                    if rows_batch:
                        cur.executemany(f"""
                            INSERT INTO {staging_table}
                            (productHash, sku, vendorName, region, service,
                             productFamily, attributes, prices)
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

    # # debug sample
    # try:
    #     logger.info("Showing first 5 lines of downloaded file for debugging:")
    #     with gzip.open(tmp_path, "rt") as gzfile:
    #         rdr = csv.reader(gzfile)
    #         for i, row in enumerate(rdr):
    #             logger.warning(row)
    #             if i >= 4:
    #                 break
    # except Exception as e:
    #     logger.error("Could not read downloaded file for debug: %s", e)

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

    for key in ("aws", "gcp", "azure"):
        if key in seen_providers:
            display = {"aws": "Amazon Web Services", "gcp": "Google Cloud Platform", "azure": "Microsoft Azure"}[key]
            CloudProvider.objects.get_or_create(name=key, defaults={"display_name": display})

    currency, _ = Currency.objects.get_or_create(code="USD", defaults={"name": "US Dollar", "symbol": "$"})

    # ---- SQL processing (normalized keys + dedupe) ----
    logger.info("Processing staging data (normalized & deduped) with SQL...")
    start_time = time.time()

    with connection.cursor() as cur:
        # 1. service categories
        logger.info("[1/6] Creating service categories...")
        cur.execute(f"""
            INSERT INTO cloud_pricing_servicecategory (name, created_at)
            SELECT DISTINCT COALESCE(NULLIF(productFamily, ''), 'General'), NOW()
            FROM {staging_table}
            ON CONFLICT (name) DO NOTHING
        """)
        connection.commit()

        # 1b. create cloud services using normalized service_code and deduped rows
        logger.info("[1b/6] Creating cloud services (normalized & deduped UPSERT)...")
        # We'll compute a normalized service_code: lower, remove spaces and punctuation common noise
        cur.execute(f"""
            WITH raw_as_normalized AS (
                SELECT DISTINCT
                    -- normalized service: lower, trim whitespace, remove spaces and parentheses
                    regexp_replace(lower(trim(st.service)), '[\\s\\(\\)\\/]+', '', 'g') as norm_service_code,
                    trim(st.service) as orig_service,
                    COALESCE(NULLIF(st.productFamily, ''), 'General') as product_family,
                    CASE
                      WHEN lower(st.vendorName) LIKE '%amazon%' OR lower(st.vendorName) LIKE '%aws%' THEN 'aws'
                      WHEN lower(st.vendorName) LIKE '%google%' OR lower(st.vendorName) LIKE '%gcp%' THEN 'gcp'
                      WHEN lower(st.vendorName) LIKE '%microsoft%' OR lower(st.vendorName) LIKE '%azure%' THEN 'azure'
                      ELSE lower(st.vendorName)
                    END as provider_code
                FROM {staging_table} st
                WHERE st.service IS NOT NULL AND st.service != ''
            ),
            deduped AS (
                -- ensure each (provider_code, norm_service_code) appears only once
                SELECT provider_code, norm_service_code, min(orig_service) as service_name, min(product_family) as product_family
                FROM raw_as_normalized
                GROUP BY provider_code, norm_service_code
            ),
            to_insert AS (
                SELECT
                    p.id as provider_id,
                    d.service_name,
                    d.norm_service_code as service_code,
                    (SELECT id FROM cloud_pricing_servicecategory sc WHERE sc.name = d.product_family LIMIT 1) as category_id
                FROM deduped d
                JOIN cloud_pricing_cloudprovider p ON p.name = d.provider_code
            )
            INSERT INTO cloud_pricing_cloudservice
                (provider_id, service_name, service_code, category_id, description, is_active, infracost_service, created_at, updated_at)
            SELECT provider_id, service_name, service_code, category_id, '', true, true, NOW(), NOW()
            FROM to_insert
            ON CONFLICT (provider_id, service_code) DO UPDATE
            SET service_name = EXCLUDED.service_name,
                category_id = COALESCE(EXCLUDED.category_id, cloud_pricing_cloudservice.category_id),
                updated_at = NOW()
        """)
        connection.commit()

        # 1c. create regions (normalized)
        logger.info("[1c/6] Creating regions (normalized)...")
        cur.execute(f"""
            WITH rr AS (
                SELECT DISTINCT
                    CASE
                      WHEN lower(region) IS NULL THEN NULL
                      ELSE regexp_replace(lower(trim(region)), '[\\s\\(\\)\\/]+', '', 'g')
                    END as norm_region_code,
                    region,
                    vendorName
                FROM {staging_table}
                WHERE region IS NOT NULL AND region != ''
            ),
            prov AS (
                SELECT
                    r.region,
                    r.norm_region_code,
                    CASE
                      WHEN lower(r.vendorName) LIKE '%amazon%' OR lower(r.vendorName) LIKE '%aws%' THEN 'aws'
                      WHEN lower(r.vendorName) LIKE '%google%' OR lower(r.vendorName) LIKE '%gcp%' THEN 'gcp'
                      WHEN lower(r.vendorName) LIKE '%microsoft%' OR lower(r.vendorName) LIKE '%azure%' THEN 'azure'
                      ELSE lower(r.vendorName)
                    END as provider_code
                FROM rr r
            )
            INSERT INTO cloud_pricing_region (provider_id, region_code, region_name, is_active, created_at)
            SELECT p.id, 'global', 'Global', true, NOW()
            FROM cloud_pricing_cloudprovider p
            WHERE NOT EXISTS (
                SELECT 1 FROM cloud_pricing_region r WHERE r.provider_id = p.id AND r.region_code = 'global'
            )
        """)
        connection.commit()

        # 2. pricing models (normalize purchaseOption)
        logger.info("[2/6] Creating pricing models...")
        cur.execute(f"""
            INSERT INTO cloud_pricing_pricingmodel (name, display_name, description)
            SELECT DISTINCT
                LOWER(REPLACE(COALESCE(
                    NULLIF((prices::jsonb -> 0 ->> 'purchaseOption'), ''),
                    NULLIF(prices::jsonb ->> 'purchaseOption', ''),
                    'on_demand'
                ), ' ', '_')) AS name,
                initcap(replace(COALESCE(
                    NULLIF((prices::jsonb -> 0 ->> 'purchaseOption'), ''),
                    NULLIF(prices::jsonb ->> 'purchaseOption', ''),
                    'on_demand'
                ), '_', ' ')) AS display_name,
                ''
            FROM {staging_table}
            WHERE prices IS NOT NULL AND prices != ''
            ON CONFLICT (name) DO NOTHING
        """)
        connection.commit()

        # 3. create staging_parsed with normalized keys (norm_service_code, norm_region_code)
        logger.info("[3/6] Parsing JSON into staging_parsed (normalized keys)...")
        cur.execute(f"""
            CREATE TEMP TABLE staging_parsed AS
            SELECT 
                productHash,
                sku,
                vendorName,
                region,
                service,
                productFamily,
                attributes::jsonb AS attr_json,
                prices::jsonb AS prices_json,
                COALESCE(
                    NULLIF(prices::jsonb ->> 'USD', ''),
                    (prices::jsonb -> 0 ->> 'USD'),
                    (prices::jsonb -> '*'::text -> 0 ->> 'USD')
                )::numeric AS price_usd,
                COALESCE(
                    NULLIF(prices::jsonb ->> 'unit', ''),
                    (prices::jsonb -> 0 ->> 'unit'),
                    (prices::jsonb -> '*'::text -> 0 ->> 'unit'),
                    'hourly'
                ) AS price_unit,
                LOWER(REPLACE(COALESCE(
                    NULLIF(prices::jsonb ->> 'purchaseOption', ''),
                    (prices::jsonb -> 0 ->> 'purchaseOption'),
                    'on_demand'
                ), ' ', '_')) AS purchase_option,
                COALESCE(NULLIF((attributes::jsonb ->> 'instanceType'), ''), '') AS instance_type,
                COALESCE(NULLIF((attributes::jsonb ->> 'operatingSystem'), ''), '') AS operating_system,
                COALESCE(NULLIF((attributes::jsonb ->> 'tenancy'), ''), '') AS tenancy,
                -- normalized service and region codes for stable joins:
                regexp_replace(lower(trim(service)), '[\\s\\(\\)\\/]+', '', 'g') AS norm_service_code,
                regexp_replace(lower(trim(region)), '[\\s\\(\\)\\/]+', '', 'g') AS norm_region_code,
                CASE
                  WHEN lower(vendorName) LIKE '%amazon%' OR lower(vendorName) LIKE '%aws%' THEN 'aws'
                  WHEN lower(vendorName) LIKE '%google%' OR lower(vendorName) LIKE '%gcp%' THEN 'gcp'
                  WHEN lower(vendorName) LIKE '%microsoft%' OR lower(vendorName) LIKE '%azure%' THEN 'azure'
                  ELSE lower(vendorName)
                END as provider_code,
                md5(COALESCE(productHash, '') || COALESCE(sku, '') || COALESCE(vendorName, '') || COALESCE(region, '') || COALESCE(service, ''))::text as digest
            FROM {staging_table}
            WHERE prices IS NOT NULL AND prices != ''
        """)
        connection.commit()

        cur.execute("SELECT COUNT(*) FROM staging_parsed")
        total_rows = cur.fetchone()[0]
        elapsed = time.time() - start_time
        logger.info("[3/6] Parsed %d rows in %.1fs", total_rows, elapsed)
        # sanity check joins
        with connection.cursor() as cur:
            # check service join
            cur.execute("""
                SELECT sp.productHash, sp.service, sp.norm_service_code, p.name AS provider
                FROM staging_parsed sp
                JOIN cloud_pricing_cloudprovider p 
                ON LOWER(TRIM(p.name)) = LOWER(TRIM(sp.provider_code))
                LEFT JOIN cloud_pricing_cloudservice cs
                ON cs.provider_id = p.id
                AND cs.service_code = sp.norm_service_code
                WHERE cs.id IS NULL
                LIMIT 20
            """)
            missing_service_rows = cur.fetchall()
            for row in missing_service_rows:
                logger.warning("Missing service join: %s", row)

            # check region join
            cur.execute("""
                SELECT sp.productHash, sp.region, sp.norm_region_code, p.name AS provider
                FROM staging_parsed sp
                JOIN cloud_pricing_cloudprovider p 
                ON LOWER(TRIM(p.name)) = LOWER(TRIM(sp.provider_code))
                LEFT JOIN cloud_pricing_region r
                ON r.provider_id = p.id
                AND r.region_code = sp.norm_region_code
                WHERE r.id IS NULL
                LIMIT 20
            """)
            missing_region_rows = cur.fetchall()
            for row in missing_region_rows:
                logger.warning("Missing region join: %s", row)

            # check pricing model join
            cur.execute("""
                SELECT sp.productHash, sp.purchase_option, pm.name AS model
                FROM staging_parsed sp
                LEFT JOIN cloud_pricing_pricingmodel pm
                ON LOWER(TRIM(pm.name)) = LOWER(TRIM(sp.purchase_option))
                WHERE pm.id IS NULL
                LIMIT 20
            """)
            missing_model_rows = cur.fetchall()
            for row in missing_model_rows:
                logger.warning("Missing pricing model join: %s", row)
        
        # 4. Insert into raw_pricing_data (bulk) by joining on provider_code -> provider id
        logger.info("[4/6] Inserting raw pricing data...")
        cur.execute(f"""
            INSERT INTO cloud_pricing_rawpricingdata
            (provider_id, node_id, raw_json, digest, source_api, fetched_at)
            SELECT DISTINCT
                p.id,
                sp.productHash,
                json_build_object(
                    'productHash', sp.productHash,
                    'sku', sp.sku,
                    'vendorName', sp.vendorName,
                    'region', sp.region,
                    'service', sp.service,
                    'productFamily', sp.productFamily,
                    'attributes', sp.attr_json,
                    'prices', sp.prices_json
                )::text,
                COALESCE(sp.digest, md5(COALESCE(sp.productHash,'') || COALESCE(sp.sku,'') || COALESCE(sp.vendorName,'') || COALESCE(sp.region,'') || COALESCE(sp.service,''))),
                'infracost_dump',
                NOW()
            FROM staging_parsed sp
            JOIN cloud_pricing_cloudprovider p ON p.name = sp.provider_code
            WHERE sp.digest IS NOT NULL
            ON CONFLICT (provider_id, node_id, digest) DO NOTHING
        """)
        raw_inserted = cur.rowcount
        connection.commit()
        elapsed = time.time() - start_time
        logger.info("[4/6] Inserted %d raw pricing records in %.1fs total", raw_inserted, elapsed)

        # 5a. Deactivate existing normalized rows for providers in this file
        logger.info("[5a/6] Deactivating old normalized rows for present providers...")
        cur.execute(f"""
            UPDATE normalized_pricing_data npd
            SET is_active = false, updated_at = NOW()
            FROM (
                SELECT DISTINCT p.id as provider_id
                FROM (SELECT DISTINCT provider_code FROM staging_parsed) sp
                JOIN cloud_pricing_cloudprovider p ON p.name = sp.provider_code
            ) prov
            WHERE npd.provider_id = prov.provider_id AND npd.is_active = true
        """)
        deactivated_old = cur.rowcount
        connection.commit()
        logger.info("[5a/6] Deactivated %d old pricing records", deactivated_old)

        # 5b. Insert new normalized rows using normalized keys for lookups
        logger.info("[5/6] Upserting normalized pricing data (robust version with logging)...")
        with connection.cursor() as cur:
            # Log a few raw staging rows for debugging
            cur.execute("""
                SELECT productHash, sku, vendorName, region, service, prices_json
                FROM staging_parsed
                LIMIT 5
            """)
            sample_rows = cur.fetchall()
            for row in sample_rows:
                logger.warning("Staging sample: %s", row)

            # Insert normalized pricing data with robust joins
            cur.execute(f"""
                WITH service_lookups AS (
                    SELECT sp.productHash, sp.service, cs.id AS service_id, p.id AS provider_id
                    FROM staging_parsed sp
                    JOIN cloud_pricing_cloudprovider p 
                    ON LOWER(TRIM(p.name)) = LOWER(TRIM(sp.provider_code))
                    LEFT JOIN cloud_pricing_cloudservice cs
                    ON cs.provider_id = p.id
                    AND LOWER(TRIM(cs.service_code)) = LOWER(TRIM(sp.service))
                ),
                region_lookups AS (
                    SELECT sp.productHash, r.id AS region_id, p.id AS provider_id
                    FROM staging_parsed sp
                    JOIN cloud_pricing_cloudprovider p
                    ON LOWER(TRIM(p.name)) = LOWER(TRIM(sp.provider_code))
                    LEFT JOIN cloud_pricing_region r
                    ON r.provider_id = p.id
                    AND LOWER(TRIM(r.region_code)) = LOWER(TRIM(sp.region))
                ),
                model_lookups AS (
                    SELECT sp.productHash, pm.id AS pricing_model_id
                    FROM staging_parsed sp
                    JOIN cloud_pricing_pricingmodel pm
                    ON LOWER(TRIM(pm.name)) = LOWER(TRIM(sp.purchase_option))
                ),
                raw_lookups AS (
                    SELECT sp.productHash, rpd.id AS raw_entry_id, p.id AS provider_id
                    FROM staging_parsed sp
                    JOIN cloud_pricing_cloudprovider p 
                    ON LOWER(TRIM(p.name)) = LOWER(TRIM(sp.provider_code))
                    JOIN cloud_pricing_rawpricingdata rpd
                    ON rpd.provider_id = p.id
                    AND rpd.node_id = sp.productHash
                )
                INSERT INTO normalized_pricing_data (
                    provider_id, service_id, region_id, pricing_model_id, currency_id,
                    product_family, instance_type, operating_system, tenancy,
                    price_per_unit, price_unit, attributes, effective_date,
                    source_api, is_active, created_at, updated_at, raw_entry_id
                )
                SELECT
                    p.id,
                    sl.service_id,
                    rl.region_id,
                    ml.pricing_model_id,
                    %s,
                    COALESCE(NULLIF(sp.productFamily, ''), ''),
                    sp.instance_type,
                    sp.operating_system,
                    sp.tenancy,
                    COALESCE(sp.price_usd, 0),
                    sp.price_unit,
                    sp.attr_json,
                    NOW(),
                    'infracost_dump',
                    true,
                    NOW(),
                    NOW(),
                    rlu.raw_entry_id
                FROM staging_parsed sp
                JOIN cloud_pricing_cloudprovider p 
                ON LOWER(TRIM(p.name)) = LOWER(TRIM(sp.provider_code))
                JOIN service_lookups sl ON sl.productHash = sp.productHash AND sl.provider_id = p.id
                JOIN region_lookups rl ON rl.productHash = sp.productHash AND rl.provider_id = p.id
                JOIN model_lookups ml ON ml.productHash = sp.productHash
                JOIN raw_lookups rlu ON rlu.productHash = sp.productHash AND rlu.provider_id = p.id
                WHERE sp.price_usd IS NOT NULL
            """, [currency.id])
            npd_inserted = cur.rowcount
            connection.commit()
            logger.info("[5/6] Inserted %d new normalized pricing records (robust) in %.1fs total", npd_inserted, time.time() - start_time)


        # 5c. Archive price changes
        logger.info("[5b/6] Recording price changes...")
        cur.execute(f"""
            INSERT INTO price_history (
                pricing_data_id, price_per_unit, change_percentage, recorded_at
            )
            SELECT 
                new.id,
                new.price_per_unit,
                CASE 
                    WHEN old.price_per_unit != 0 
                    THEN ((new.price_per_unit - old.price_per_unit) / old.price_per_unit * 100)::numeric(6,2)
                    ELSE NULL
                END,
                NOW()
            FROM normalized_pricing_data new
            LEFT JOIN LATERAL (
                SELECT price_per_unit
                FROM normalized_pricing_data old
                WHERE old.provider_id = new.provider_id
                    AND old.service_id = new.service_id
                    AND old.region_id = new.region_id
                    AND old.pricing_model_id = new.pricing_model_id
                    AND old.instance_type = new.instance_type
                    AND old.operating_system = new.operating_system
                    AND old.tenancy = new.tenancy
                    AND old.is_active = false
                    AND old.id != new.id
                ORDER BY old.updated_at DESC
                LIMIT 1
            ) old ON true
            WHERE new.source_api = 'infracost_dump'
                AND new.is_active = true
                AND old.price_per_unit IS NOT NULL
                AND new.price_per_unit IS NOT NULL
                AND ABS(old.price_per_unit - new.price_per_unit) > 0.0001
                AND NOT EXISTS (
                    SELECT 1 FROM price_history ph WHERE ph.pricing_data_id = new.id
                )
        """)
        price_changes = cur.rowcount
        connection.commit()
        elapsed = time.time() - start_time
        logger.info("[5b/6] Recorded %d price changes in %.1fs total", price_changes, elapsed)

        # get count
        cur.execute("SELECT COUNT(*) FROM staging_parsed")
        total_saved = cur.fetchone()[0]

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
    try:
        with connection.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {staging_table}")
            connection.commit()
        logger.info("Staging table %s dropped successfully", staging_table)
    except Exception as e:
        logger.warning("Could not drop staging table %s: %s", staging_table, e)

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
