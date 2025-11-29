import os
import gzip
import json
import tempfile
import logging
import requests

from django.utils import timezone
from decimal import Decimal
from datetime import timedelta

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

    # 1. Fetch download URL
    try:
        resp = requests.get(DATA_DOWNLOAD_URL,
                            headers={"X-Api-Key": INFRACOST_API_KEY},
                            timeout=60)
        resp.raise_for_status()
    except Exception as e:
        logger.exception("Error fetching dump metadata: %s", e)
        return f"FAIL: metadata error {e}"
    meta = resp.json()
    download_url = meta.get("downloadUrl")
    if not download_url:
        logger.error("downloadUrl not found in response: %s", meta)
        return "FAIL: no downloadUrl"

    # 2. Download .csv.gz to temp file
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
    except Exception as e:
        logger.exception("Download error: %s", e)
        return f"FAIL: download crashed {e}"

    # 3. Load into staging table
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
            except Exception as e:
                logger.exception("COPY failed: %s", e)
                raise
        connection.commit()
    logger.info("Staging load complete into %s", staging_table)

    # 4. Prepare provider & currency objects
    provider, _ = CloudProvider.objects.get_or_create(
        name="infracost", defaults={"display_name": "Infracost"})
    currency, _ = Currency.objects.get_or_create(
        code="USD", defaults={"name": "US Dollar", "symbol": "$"})

    # --- Preload lookup caches to avoid repeated DB hits ---
    def load_cache(qs, keyfunc):
        d = {}
        for obj in qs:
            d[keyfunc(obj)] = obj
        return d

    categories_cache = {c.name: c for c in ServiceCategory.objects.all()}
    services_cache = { (s.provider_id, s.service_code): s for s in CloudService.objects.all() }
    regions_cache = { (r.provider_id, r.region_code): r for r in Region.objects.all() }
    pricing_model_cache = { m.name: m for m in PricingModel.objects.all() }
    # currencies & provider already resolved above

    # Helper getters that create on-miss (and populate cache)
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

    # 5. Process staging in batches, build bulk lists
    BATCH = 5000
    total_saved = 0
    offset = 0

    while True:
        with connection.cursor() as cur:
            cur.execute(f"""
                SELECT * FROM {staging_table}
                ORDER BY productHash
                LIMIT {BATCH} OFFSET {offset}
            """)
            rows = cur.fetchall()
            col_names = [d[0] for d in cur.description]
        if not rows:
            break

        rowdicts = [{col_names[i]: row[i] for i in range(len(col_names))} for row in rows]
        batch_node_ids = [r.get("productHash") for r in rowdicts if r.get("productHash")]

        # Fetch the most recent RawPricingData for each node in this batch, to detect duplicates
        existing_latest_raw = {}
        if batch_node_ids:
            qs = RawPricingData.objects.filter(provider=provider, node_id__in=batch_node_ids).order_by('node_id', '-fetched_at')
            for raw in qs:
                nid = raw.node_id
                if nid and nid not in existing_latest_raw:
                    existing_latest_raw[nid] = raw

        # Prepare lists for bulk creation / updates
        raw_objs_to_create = []
        npd_objs_to_create = []
        prev_normalized_to_close = []   # list of NormalizedPricingData instances to be deactivated
        raw_objs_index_map = []         # map index in raw_objs_to_create -> (rowdict, prev_raw) for linking later

        processed_count = 0
        skipped_count = 0
        created_count = 0

        for rowdict in rowdicts:
            try:
                pid = rowdict.get("productHash")
                prev_raw = existing_latest_raw.get(pid) if pid else None

                # Detect duplicate raw by hashing serialized JSON like before
                this_hash = _row_hash_for_compare(rowdict)
                if prev_raw:
                    try:
                        prev_hash = _row_hash_for_compare(prev_raw.raw_json)
                    except Exception:
                        prev_hash = None
                    if prev_hash == this_hash:
                        # exact duplicate of latest raw -> skip
                        skipped_count += 1
                        processed_count += 1
                        continue

                # Build normalized fields (do not save yet)
                product_family = _truncate(rowdict.get("productFamily") or "", 100, "product_family")
                service_code = _truncate(rowdict.get("service") or rowdict.get("vendorName") or "", 100, "service_code")
                service_name = rowdict.get("service") or service_code
                region_code = _truncate(rowdict.get("region") or "", 50, "region_code")

                # parse attributes & prices safely
                raw_attrs = rowdict.get("attributes")
                parsed_attrs = {}
                if raw_attrs:
                    try:
                        parsed_attrs = json.loads(raw_attrs)
                    except Exception:
                        parsed_attrs = {"raw": raw_attrs}

                raw_prices = rowdict.get("prices")
                if raw_prices:
                    try:
                        parsed_prices = json.loads(raw_prices)
                    except Exception:
                        parsed_prices = {"raw": raw_prices}
                else:
                    parsed_prices = {}

                # pricing model detection
                purchase = parsed_prices.get(next(iter(parsed_prices), ''), [{}])[0].get("purchaseOption", "on_demand")
                pricing_model = get_or_create_pricing_model(purchase)

                # find or create service & region & category
                category = get_or_create_category(product_family or "General")
                service = get_or_create_service(provider, service_code, service_name, category)
                region = get_or_create_region(provider, region_code)

                # pick first price value (USD) as primary price_per_unit (like before)
                first_price = None
                if isinstance(parsed_prices, dict):
                    for k, v in parsed_prices.items():
                        if isinstance(v, list) and v:
                            first_price = v[0]
                            break
                price_val = None
                if first_price:
                    usd_val = first_price.get("USD")
                    try:
                        price_val = Decimal(str(usd_val)) if usd_val is not None else None
                    except Exception:
                        logger.warning("Invalid USD value %r in row %r", usd_val, rowdict)

                # Truncate textual fields
                instance_type_val = _truncate(parsed_attrs.get("instanceType", "") or "", 100, "instance_type")
                operating_system_val = _truncate(parsed_attrs.get("operatingSystem", "") or "", 100, "operating_system")
                tenancy_val = _truncate(parsed_attrs.get("tenancy", "") or "", 50, "tenancy")
                price_unit_val = _truncate(first_price.get("unit", "") if first_price else "", 100, "price_unit")

                # Build RawPricingData object (not saved)
                raw_obj = RawPricingData(
                    provider=provider,
                    node_id=pid,
                    raw_json=rowdict,
                    source_api="infracost_dump"
                )
                raw_objs_to_create.append(raw_obj)
                raw_objs_index_map.append((len(raw_objs_to_create) - 1, rowdict, prev_raw))

                # Build NormalizedPricingData object (link to raw later)
                npd = NormalizedPricingData(
                    provider=provider,
                    service=service,
                    region=region,
                    pricing_model=pricing_model,
                    currency=currency,
                    product_family=product_family or "",
                    instance_type=instance_type_val,
                    operating_system=operating_system_val,
                    tenancy=tenancy_val,
                    price_per_hour=None,
                    price_per_month=None,
                    price_per_year=None,
                    price_per_unit=price_val,
                    price_unit=price_unit_val,
                    attributes=parsed_attrs,
                    effective_date=timezone.now(),
                    source_api="infracost_dump",
                    is_active=True,
                )
                npd_objs_to_create.append(npd)

                # If there is a previous raw -> close its normalized row (if linked)
                if prev_raw and getattr(prev_raw, "normalized", None):
                    prev_np = prev_raw.normalized
                    # schedule prev normalized to be closed (only once)
                    prev_normalized_to_close.append(prev_np)

                processed_count += 1
                created_count += 1
            except Exception as e:
                logger.exception("Error preparing row %r: %s", rowdict, e)
                continue

        # Bulk DB actions - do inside atomic transaction for the batch
        try:
            with transaction.atomic():
                # 1) Bulk create RawPricingData objects (this assigns PKs)
                if raw_objs_to_create:
                    RawPricingData.objects.bulk_create(raw_objs_to_create, batch_size=1000)

                # Django's bulk_create preserves ordering; we can map created raw ids back to our npd list.
                # raw_objs_to_create and npd_objs_to_create are parallel (we appended in same sequence)
                # Link raw entries to normalized objects by assigning raw_entry_id
                for idx, (raw_index, rowdict, prev_raw) in enumerate(raw_objs_index_map):
                    created_raw = raw_objs_to_create[raw_index]
                    # assign FK on corresponding npd object
                    # note: created_raw.id should be available after bulk_create on modern Django/Postgres
                    if idx < len(npd_objs_to_create):
                        npd_objs_to_create[idx].raw_entry = created_raw

                # 2) Bulk create NormalizedPricingData objects
                if npd_objs_to_create:
                    NormalizedPricingData.objects.bulk_create(npd_objs_to_create, batch_size=1000)

                # 3) Close previous normalized rows (set is_active=False and end_date)
                if prev_normalized_to_close:
                    # dedupe list
                    prev_normalized_unique = {p.id: p for p in prev_normalized_to_close}.values()
                    now = timezone.now()
                    for p in prev_normalized_unique:
                        p.is_active = False
                        p.end_date = now
                        # updated_at will be updated by bulk_update? Not automatically; include updated_at if desired.
                    NormalizedPricingData.objects.bulk_update(list(prev_normalized_unique), ['is_active', 'end_date'])

                # 4) Optionally create PriceHistory rows for each newly created npd (best-effort)
                # NOTE: creating PriceHistory per-row in Python may be expensive; you can also implement
                # a DB-side INSERT SELECT from newly created normalized rows if you want it faster.
                # We'll do a lightweight loop but wrapped in the same transaction.
                try:
                    PriceHistory = __import__('cloud_pricing.models', fromlist=['PriceHistory']).PriceHistory
                    ph_objs = []
                    for npd in npd_objs_to_create:
                        try:
                            ph_objs.append(PriceHistory(
                                pricing_data=npd,
                                price_per_hour=npd.price_per_hour,
                                price_per_month=npd.price_per_month,
                                price_per_unit=npd.price_per_unit,
                                change_percentage=None
                            ))
                        except Exception:
                            logger.exception("Failed to create PriceHistory object for %s", getattr(npd, 'id', None))
                    if ph_objs:
                        PriceHistory.objects.bulk_create(ph_objs, batch_size=1000)
                except Exception:
                    # PriceHistory isn't critical; log and continue
                    logger.exception('Failed to bulk create PriceHistory for batch')

                # 5) Update any indexes/caches in models if necessary (skipped)

        except Exception as e:
            logger.exception("Batch DB write failed: %s", e)
            # Best attempt: continue with next batch
            offset += BATCH
            continue

        batch_created = len(npd_objs_to_create)
        total_saved += batch_created
        offset += BATCH
        logger.info("Batch processed: processed=%d created=%d skipped=%d, offset=%d",
                    processed_count, batch_created, skipped_count, offset)

    # 5. Clean up temp file
    try:
        os.remove(tmp_path)
    except OSError:
        logger.warning("Could not delete %s", tmp_path)

    # 6. Log API call
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

def _make_pricing_from_row(row, provider, currency):
    # Extract service/service code etc
    # CloudService.service_code max_length is 50 in the DB migrations — truncate to match
    service_code = _truncate(row.get("service") or row.get("vendorName"), 100, "service_code")
    service_name = row.get("service") or service_code
    product_family = _truncate(row.get("productFamily") or "", 100, "product_family")
    region_code = _truncate(row.get("region") or "", 50, "region_code")

    raw_attrs = row.get("attributes")
    parsed_attrs = {}
    if raw_attrs:
        try:
            parsed_attrs = json.loads(raw_attrs)
        except json.JSONDecodeError:
            parsed_attrs = {"raw": raw_attrs}

    raw_prices = row.get("prices")
    if raw_prices:
        try:
            parsed_prices = json.loads(raw_prices)
        except json.JSONDecodeError:
            parsed_prices = {"raw": raw_prices}
    else:
        parsed_prices = {}

    category, _ = ServiceCategory.objects.get_or_create(name=product_family or "General")

    # Robust get_or_create for CloudService to avoid race-related IntegrityError
    try:
        service, _ = CloudService.objects.get_or_create(
            provider=provider,
            service_code=service_code,
            defaults={"service_name": service_name, "category": category}
        )
    except IntegrityError:
        # Another process may have created it concurrently — fetch the existing record
        try:
            transaction.rollback()
        except Exception:
            pass
        service = CloudService.objects.filter(provider=provider, service_code=service_code).first()
        if service is None:
            # Re-raise so the caller can see the original problem
            raise

    # Region get_or_create can also face races; handle similarly
    try:
        region, _ = Region.objects.get_or_create(
            provider=provider,
            region_code=region_code,
            defaults={"region_name": region_code}
        )
    except IntegrityError:
        try:
            transaction.rollback()
        except Exception:
            pass
        region = Region.objects.filter(provider=provider, region_code=region_code).first()
        if region is None:
            raise

    # We'll treat pricing_model as on_demand for now; you could examine parsed_prices for purchaseOption
    purchase = parsed_prices.get(next(iter(parsed_prices), ''), [{}])[0].get("purchaseOption", "on_demand")
    try:
        pricing_model, _ = PricingModel.objects.get_or_create(
            name=purchase,
            defaults={"display_name": purchase.replace("_", " ").title()}
        )
    except IntegrityError:
        try:
            transaction.rollback()
        except Exception:
            pass
        pricing_model = PricingModel.objects.filter(name=purchase).first()
        if pricing_model is None:
            raise

    # For simplicity take first price in parsed_prices
    first_price = None
    if isinstance(parsed_prices, dict):
        # assume dict of lists
        for k, v in parsed_prices.items():
            if isinstance(v, list) and v:
                first_price = v[0]
                break
    price_val = None
    if first_price:
        usd_val = first_price.get("USD")
        try:
            price_val = Decimal(str(usd_val)) if usd_val is not None else None
        except Exception:
            logger.warning("Invalid USD value %r in row %r", usd_val, row)

    # Truncate fields to match DB column sizes
    instance_type_val = _truncate(parsed_attrs.get("instanceType", "") or "", 50, "instance_type")
    operating_system_val = _truncate(parsed_attrs.get("operatingSystem", "") or "", 50, "operating_system")
    tenancy_val = _truncate(parsed_attrs.get("tenancy", "") or "", 20, "tenancy")
    price_unit_val = _truncate(first_price.get("unit", "") if first_price else "", 50, "price_unit")

    npd = NormalizedPricingData(
        provider=provider,
        service=service,
        region=region,
        pricing_model=pricing_model,
        currency=currency,
        product_family=product_family or "",
        instance_type=instance_type_val,
        operating_system=operating_system_val,
        tenancy=tenancy_val,
        price_per_unit=price_val,
        price_unit=price_unit_val,
        effective_date=timezone.now(),
        attributes=parsed_attrs,
        # raw_data is no longer populated here to avoid duplicating the raw JSON;
        # the canonical raw JSON is stored in `RawPricingData` and linked via `raw_entry`.
        source_api="infracost_dump"
    )

    raw = RawPricingData(
        provider=provider,
        node_id=row.get("productHash"),
        raw_json=row,
        source_api="infracost_dump"
    )

    return npd, raw


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
