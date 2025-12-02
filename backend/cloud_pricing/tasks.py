import os
import gzip
import json
import tempfile
import logging
import requests

from django.utils import timezone
from decimal import Decimal
from datetime import datetime, timedelta, timezone

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
    Optimized weekly pricing dump importer:
    - downloads gz CSV to staging
    - loads staging via COPY
    - processes in batches using bulk_create/bulk_update
    - avoids per-row .save()
    """
    if not INFRACOST_API_KEY:
        logger.error("INFRACOST_API_KEY not set")
        return "FAIL: no API key"

    def _row_hash_for_compare(rowdict):
        """Create a hash of the row data for duplicate detection"""
        import hashlib
        data_string = json.dumps(rowdict, sort_keys=True)
        return hashlib.md5(data_string.encode()).hexdigest()
    
    # Helper functions to make the flow easier to read
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
            # cleanup partially written file
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

            copy_sql = f"""
                COPY {staging_table}
                (productHash, sku, vendorName, region, service,
                 productFamily, attributes, prices)
                FROM STDIN WITH CSV HEADER
            """
            with gzip.open(tmp_path, "rt") as gzfile:
                try:
                    cur.copy_expert(copy_sql, gzfile)
                except Exception:
                    logger.exception("COPY failed")
                    raise
            connection.commit()
        logger.info("Staging load complete into %s", staging_table)
        return staging_table
    
    # 1-3. Orchestrate metadata fetch, download, and staging load
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

    # 4. Prepare provider & currency objects
    provider, _ = CloudProvider.objects.get_or_create(
        name="infracost", defaults={"display_name": "Infracost"})
    currency, _ = Currency.objects.get_or_create(
        code="USD", defaults={"name": "US Dollar", "symbol": "$"})

    # Initialize caches
    categories_cache = {c.name: c for c in ServiceCategory.objects.all()}
    # Use getattr to prefer the auto-created "<field>_id" when available, otherwise fall back to the related object's id
    services_cache = {(getattr(s, "provider_id", s.provider.id), s.service_code): s for s in CloudService.objects.all()}
    regions_cache = {(getattr(r, "provider_id", r.provider.id), r.region_code): r for r in Region.objects.all()}
    pricing_model_cache = {m.name: m for m in PricingModel.objects.all()}

    def get_or_create_category(name):
        name = name or "General"
        if name in categories_cache:
            return categories_cache[name]
        obj, created = ServiceCategory.objects.get_or_create(name=name)
        categories_cache[name] = obj
        return obj

    def get_or_create_service(provider_obj, service_code, service_name, category):
        key = (provider_obj.id, service_code)
        if key in services_cache:
            return services_cache[key]
        try:
            obj, created = CloudService.objects.get_or_create(
                provider=provider_obj,
                service_code=service_code,
                defaults={"service_name": service_name, "category": category}
            )
        except IntegrityError:
            # race — fetch existing
            transaction.rollback()
            obj = CloudService.objects.filter(provider=provider_obj, service_code=service_code).first()
            if obj is None:
                raise
        services_cache[key] = obj
        return obj

    def get_or_create_region(provider_obj, region_code):
        key = (provider_obj.id, region_code)
        if key in regions_cache:
            return regions_cache[key]
        try:
            obj, created = Region.objects.get_or_create(
                provider=provider_obj,
                region_code=region_code,
                defaults={"region_name": region_code}
            )
        except IntegrityError:
            transaction.rollback()
            obj = Region.objects.filter(provider=provider_obj, region_code=region_code).first()
            if obj is None:
                raise
        regions_cache[key] = obj
        return obj

    def get_or_create_pricing_model(name):
        name = name or "on_demand"
        if name in pricing_model_cache:
            return pricing_model_cache[name]
        try:
            obj, created = PricingModel.objects.get_or_create(
                name=name,
                defaults={"display_name": name.replace("_", " ").title()}
            )
        except IntegrityError:
            transaction.rollback()
            obj = PricingModel.objects.filter(name=name).first()
            if obj is None:
                raise
        pricing_model_cache[name] = obj
        return obj

    # 5. Process staging in batches with proper memory management
    BULK_CHUNK = 100
    total_saved = 0
    product_hashes_in_dump = set()  # Track which products are in the new dump

    with connection.cursor() as cur:
        # Fixed indentation
        cur.execute(f"SELECT * FROM {staging_table} ORDER BY productHash")
        
        raw_objs_to_create = []
        npd_objs_to_create = []
        
        while True:
            rows = cur.fetchmany(BULK_CHUNK)
            if not rows:
                break
                
            for row in rows:
                rowdict = dict(zip([desc[0] for desc in cur.description], row))
                pid = rowdict.get("productHash")
                product_hashes_in_dump.add(pid)  # Track this product

                # Check for duplicates
                prev_raw = RawPricingData.objects.filter(provider=provider, node_id=pid).order_by('-fetched_at').first()
                this_hash = _row_hash_for_compare(rowdict)
                if prev_raw and prev_raw.digest == this_hash:
                    continue  # skip duplicate

                # Parse JSON fields
                parsed_attrs = {}
                if rowdict.get("attributes"):
                    try:
                        parsed_attrs = json.loads(rowdict["attributes"])
                    except Exception:
                        parsed_attrs = {"raw": rowdict["attributes"]}

                parsed_prices = {}
                if rowdict.get("prices"):
                    try:
                        parsed_prices = json.loads(rowdict["prices"])
                    except Exception:
                        parsed_prices = {"raw": rowdict["prices"]}

                # Extract first price
                first_price = None
                for v in parsed_prices.values():
                    if isinstance(v, list) and v:
                        first_price = v[0]
                        break

                price_val = None
                if first_price:
                    try:
                        price_val = Decimal(str(first_price.get("USD")))
                    except Exception:
                        price_val = None

                # Build RawPricingData object
                raw_obj = RawPricingData(
                    provider=provider,
                    node_id=pid,
                    raw_json=json.dumps(rowdict),
                    digest=this_hash,
                    source_api="infracost_dump"
                )
                raw_objs_to_create.append(raw_obj)

                # Build NormalizedPricingData object
                category = get_or_create_category(rowdict.get("productFamily") or "General")
                service = get_or_create_service(provider, rowdict.get("service") or "", rowdict.get("service") or "", category)
                region = get_or_create_region(provider, rowdict.get("region") or "")
                purchase = first_price.get("purchaseOption") if first_price else "on_demand"
                pricing_model = get_or_create_pricing_model(purchase)

                npd = NormalizedPricingData(
                    provider=provider,
                    service=service,
                    region=region,
                    pricing_model=pricing_model,
                    currency=currency,
                    product_family=rowdict.get("productFamily") or "",
                    instance_type=parsed_attrs.get("instanceType") or "",
                    operating_system=parsed_attrs.get("operatingSystem") or "",
                    tenancy=parsed_attrs.get("tenancy") or "",
                    price_per_unit=price_val,
                    price_unit=first_price.get("unit") if first_price else "",
                    attributes=parsed_attrs,
                    effective_date=timezone.now(),
                    source_api="infracost_dump",
                    is_active=True,
                )
                npd_objs_to_create.append(npd)
                total_saved += 1

            # Bulk insert the current batch
            if raw_objs_to_create:
                with transaction.atomic():
                    RawPricingData.objects.bulk_create(raw_objs_to_create)
                raw_objs_to_create.clear()

            if npd_objs_to_create:
                with transaction.atomic():
                    NormalizedPricingData.objects.bulk_create(npd_objs_to_create)
                npd_objs_to_create.clear()
    
    # 5b. Archive old/deleted prices to PriceHistory and mark as inactive
    logger.info("Archiving deleted/not updated prices...")
    
    # Find all RawPricingData NOT in the new dump
    old_raw_not_in_dump = RawPricingData.objects.filter(
        provider=provider,
        source_api="infracost_dump"
    ).exclude(node_id__in=product_hashes_in_dump)
    
    # Get NPD records linked to deleted raw data
    npd_to_archive = NormalizedPricingData.objects.filter(
        provider=provider,
        is_active=True,
        raw_entry__in=old_raw_not_in_dump
    )
    
    # Archive each to price history
    price_history_records = []
    for npd in npd_to_archive:
        price_history_records.append(
            PriceHistory(
                pricing_data=npd,
                previous_price=npd.price_per_unit,
                current_price=None,  # Null indicates deletion
                change_type='price_removed',
                recorded_at=timezone.now()
            )
        )
    
    # Bulk insert price history for deleted items
    if price_history_records:
        PriceHistory.objects.bulk_create(price_history_records)
        logger.info(f"Archived {len(price_history_records)} deleted prices to history")
        
        # Mark these NPD records as inactive
        npd_to_archive.update(is_active=False)
        logger.info(f"Marked {len(price_history_records)} records as inactive")

    # 6. Clean up
    try:
        os.remove(tmp_path)
    except OSError:
        logger.warning("Could not delete %s", tmp_path)

    # 7. Log API call
    try:
        APICallLog.objects.create(
            provider=provider,
            api_endpoint=DATA_DOWNLOAD_URL,
            status_code=200,
            response_time=0.0,
            records_updated=total_saved,
            error_message=""
        )
    except Exception:
        logger.exception("Failed to write APICallLog")

    logger.info("Import finished, saved %d normalized rows", total_saved)
    
    # 8. Clean up staging table using SQL (fast)
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
