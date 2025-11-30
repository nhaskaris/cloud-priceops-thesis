import os
import gzip
import json
import tempfile
import logging
import requests

from django.utils import timezone
from decimal import Decimal
from datetime import timedelta
import gc

from celery import shared_task
from django.db import connection, transaction
from django.db.utils import IntegrityError
from django.conf import settings

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
)
from hashlib import sha1

logger = logging.getLogger(__name__)


def _get_rss_kb():
    """Return current process RSS in KB. Works in Linux containers by reading /proc/self/status."""
    try:
        with open('/proc/self/status', 'r') as f:
            for line in f:
                if line.startswith('VmRSS:'):
                    parts = line.split()
                    # parts e.g. ['VmRSS:', '123456', 'kB']
                    return int(parts[1])
    except Exception:
        pass
    return None

DATA_DOWNLOAD_URL = "https://pricing.api.infracost.io/data-download/latest"
INFRACOST_API_KEY = os.getenv("INFRACOST_API_KEY")


def _truncate(value, max_length, field_name=None):
    if value is None:
        return None
    s = str(value)
    if len(s) > max_length:
        if field_name:
            logger.warning("Truncating %s to %d chars (was %d)", field_name, max_length, len(s))
        return s[:max_length]
    return s


def _row_hash_for_compare(rowdict):
    """
    Create a compact hash of the raw row for duplicate detection.
    Use a stable string representation of key fields.
    """
    # We choose the fields which determine whether a row is 'the same' as previous ingestion:
    # node id, region, service, attributes JSON (sorted), prices JSON (sorted)
    node = rowdict.get("productHash")
    region = rowdict.get("region") or ""
    service = rowdict.get("service") or ""
    attrs = rowdict.get("attributes") or ""
    prices = rowdict.get("prices") or ""

    # ensure deterministic encoding of JSON-like strings
    try:
        if isinstance(attrs, str):
            parsed = json.loads(attrs)
            attrs_ser = json.dumps(parsed, sort_keys=True, separators=(",", ":"))
        else:
            attrs_ser = json.dumps(attrs, sort_keys=True, separators=(",", ":"))
    except Exception:
        attrs_ser = str(attrs)

    try:
        if isinstance(prices, str):
            parsed = json.loads(prices)
            prices_ser = json.dumps(parsed, sort_keys=True, separators=(",", ":"))
        else:
            prices_ser = json.dumps(prices, sort_keys=True, separators=(",", ":"))
    except Exception:
        prices_ser = str(prices)

    s = "|".join([str(node), region, service, attrs_ser, prices_ser])
    return sha1(s.encode("utf-8")).hexdigest()


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
    return f"OK: saved {total_saved}"

@shared_task(bind=True)
def materialize_features_to_duckdb(self, batch_size=2000, duckdb_path=None):
    """Compute basic features and materialize them into the DuckDB offline store.

    This task reads `NormalizedPricingData` and `PriceHistory` to generate
    feature rows and inserts them into the offline DuckDB store managed by
    `feature_repo.duckdb_client`.
    """
    try:
        from feature_repo.duckdb_client import path_for_store, ensure_feature_values_table, insert_feature_values
    except Exception as e:
        logger.exception('DuckDB helper import failed: %s', e)
        raise

    try:
        from .models import NormalizedPricingData, PriceHistory
    except Exception as e:
        logger.exception('Model import failed in materialize task: %s', e)
        raise

    store_path = duckdb_path or path_for_store()
    ensure_feature_values_table(store_path)

    offset = 0
    total_inserted = 0
    while True:
        qs = list(NormalizedPricingData.objects.select_related('provider', 'service', 'region')[offset:offset+batch_size])
        if not qs:
            break

        rows = []
        for rec in qs:
            try:
                # Compute requested features
                now = timezone.now()

                # current price (primary feature)
                current_price = float(rec.price_per_unit) if rec.price_per_unit is not None else None

                # previous price: try to find the most recent previous NormalizedPricingData
                prev_qs = NormalizedPricingData.objects.filter(
                    provider=rec.provider,
                    service=rec.service,
                    region=rec.region,
                    instance_type=rec.instance_type,
                    operating_system=rec.operating_system,
                    tenancy=rec.tenancy,
                    pricing_model=rec.pricing_model,
                ).exclude(id=rec.id).order_by('-effective_date')
                prev_np = prev_qs.first()
                previous_price = float(prev_np.price_per_unit) if (prev_np and prev_np.price_per_unit is not None) else None

                # absolute and percent diffs
                price_diff_abs = None
                price_diff_pct = None
                try:
                    if current_price is not None and previous_price is not None:
                        price_diff_abs = float(Decimal(str(current_price)) - Decimal(str(previous_price)))
                        if previous_price != 0:
                            price_diff_pct = float((Decimal(str(current_price)) - Decimal(str(previous_price))) / Decimal(str(previous_price)))
                except Exception:
                    logger.exception('Error computing price diffs for id=%s', getattr(rec, 'id', None))

                # days since this price became effective (how long stable)
                days_since_price_change = None
                try:
                    if rec.effective_date:
                        days_since_price_change = (now - rec.effective_date).days
                except Exception:
                    logger.exception('Error computing days_since_price_change for id=%s', getattr(rec, 'id', None))

                # frequency of price changes in the last 90 days for this product
                freq_90d = 0
                try:
                    since = now - timedelta(days=90)
                    freq_90d = PriceHistory.objects.filter(
                        pricing_data__provider=rec.provider,
                        pricing_data__service=rec.service,
                        pricing_data__region=rec.region,
                        pricing_data__instance_type=rec.instance_type,
                        recorded_at__gte=since
                    ).count()
                except Exception:
                    logger.exception('Error computing freq_90d for id=%s', getattr(rec, 'id', None))

                rows.append({
                    'feature': 'current_price',
                    'pricing_data_id': rec.id,
                    'node_id': None,
                    'value': current_price,
                    'raw_value': {'unit': rec.price_unit or ''},
                    'computed_at': now,
                })

                rows.append({
                    'feature': 'previous_price',
                    'pricing_data_id': rec.id,
                    'node_id': None,
                    'value': previous_price,
                    'raw_value': {'prev_id': prev_np.id if prev_np else None},
                    'computed_at': now,
                })

                rows.append({
                    'feature': 'price_diff_abs',
                    'pricing_data_id': rec.id,
                    'node_id': None,
                    'value': price_diff_abs,
                    'raw_value': {'abs': price_diff_abs},
                    'computed_at': now,
                })

                rows.append({
                    'feature': 'price_diff_pct',
                    'pricing_data_id': rec.id,
                    'node_id': None,
                    'value': price_diff_pct,
                    'raw_value': {'pct': price_diff_pct},
                    'computed_at': now,
                })

                rows.append({
                    'feature': 'days_since_price_change',
                    'pricing_data_id': rec.id,
                    'node_id': None,
                    'value': float(days_since_price_change) if days_since_price_change is not None else None,
                    'raw_value': {'days': days_since_price_change},
                    'computed_at': now,
                })

                rows.append({
                    'feature': 'price_change_frequency_90d',
                    'pricing_data_id': rec.id,
                    'node_id': None,
                    'value': float(freq_90d),
                    'raw_value': {'count_90d': freq_90d},
                    'computed_at': now,
                })
            except Exception:
                logger.exception('Failed computing features for record id=%s', getattr(rec, 'id', None))
                continue

        inserted = insert_feature_values(rows, store_path)
        # Also push current batch to online store (Feast/Redis)
        try:
            from feature_repo.feast_utils import push_to_online, register_features
            # ensure feast feature defs exist (best-effort)
            try:
                register_features()
            except Exception:
                logger.debug('register_features call failed or skipped')
            pushed = push_to_online(rows)
            logger.info('Pushed %d feature rows to online store', pushed)
        except Exception:
            logger.exception('Failed to push batch to online store')
        total_inserted += inserted
        offset += batch_size
        logger.info('Materialize batch inserted=%d offset=%d', inserted, offset)

    logger.info('Materialize finished, total_inserted=%d into %s', total_inserted, store_path)
    return {'inserted': total_inserted, 'path': store_path}
