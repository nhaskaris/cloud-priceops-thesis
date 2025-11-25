import os
import gzip
import json
import tempfile
import logging
import requests

from datetime import datetime
from decimal import Decimal

from celery import shared_task
from django.db import connection, transaction
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

@shared_task
def weekly_pricing_dump_update():
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
                for chunk in r2.iter_content(chunk_size=1024*1024):
                    if chunk:
                        f.write(chunk)
        logger.info("Downloaded dump to %s", tmp_path)
    except Exception as e:
        logger.exception("Download error: %s", e)
        return f"FAIL: download crashed {e}"

    # 3. Load into staging table
    staging_table = "infracost_staging_prices"
    with connection.cursor() as cur:
        # Drop and recreate to ensure correct schema
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

    # 4. Normalize into Django models in batches
    provider, _ = CloudProvider.objects.get_or_create(
        name="infracost", defaults={"display_name": "Infracost"})
    currency, _ = Currency.objects.get_or_create(
        code="USD", defaults={"name": "US Dollar", "symbol": "$"})

    BATCH = 5000
    total_saved = 0

    with connection.cursor() as cur:
        cur.execute(f"SELECT * FROM {staging_table}")
        col_names = [d[0] for d in cur.description]

    offset = 0
    while True:
        with connection.cursor() as cur:
            cur.execute(f"""
                SELECT * FROM {staging_table}
                ORDER BY productHash
                LIMIT {BATCH} OFFSET {offset}
            """)
            rows = cur.fetchall()
        if not rows:
            break

        npd_objs = []
        raw_objs = []
        for row in rows:
            rowdict = {col_names[i]: row[i] for i in range(len(col_names))}
            try:
                npd, raw = _make_pricing_from_row(rowdict, provider, currency)
            except Exception as e:
                logger.exception("Error processing row %r: %s", rowdict, e)
                continue
            npd_objs.append(npd)
            raw_objs.append(raw)

        NormalizedPricingData.objects.bulk_create(npd_objs, batch_size=BATCH)
        RawPricingData.objects.bulk_create(raw_objs, batch_size=BATCH)
        total_saved += len(npd_objs)

        offset += BATCH
        logger.info("Normalized %d rows, offset %d", len(npd_objs), offset)

    # 5. Clean up temp file
    try:
        os.remove(tmp_path)
    except OSError:
        logger.warning("Could not delete %s", tmp_path)

    # 6. Log API call
    APICallLog.objects.create(
        provider=provider,
        api_endpoint=DATA_DOWNLOAD_URL,
        status_code=200,
        response_time=0.0,
        records_updated=total_saved,
        error_message=""
    )

    logger.info("Import finished, saved %d normalized rows", total_saved)
    return f"OK: saved {total_saved}"

def _make_pricing_from_row(row, provider, currency):
    # Extract service/service code etc
    service_code = _truncate(row.get("service") or row.get("vendorName"), 50, "service_code")
    service_name = row.get("service") or service_code
    product_family = row.get("productFamily")
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
    service, _ = CloudService.objects.get_or_create(
        provider=provider,
        service_code=service_code,
        defaults={"service_name": service_name, "category": category})

    region, _ = Region.objects.get_or_create(
        provider=provider,
        region_code=region_code,
        defaults={"region_name": region_code})

    # We'll treat pricing_model as on_demand for now; you could examine parsed_prices for purchaseOption
    purchase = parsed_prices.get(next(iter(parsed_prices), ''), [{}])[0].get("purchaseOption", "on_demand")
    pricing_model, _ = PricingModel.objects.get_or_create(
        name=purchase,
        defaults={"display_name": purchase.replace("_", " ").title()})

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

    npd = NormalizedPricingData(
        provider=provider,
        service=service,
        region=region,
        pricing_model=pricing_model,
        currency=currency,
        product_family=product_family or "",
        instance_type=parsed_attrs.get("instanceType", "") or "",
        operating_system=parsed_attrs.get("operatingSystem", "") or "",
        tenancy=parsed_attrs.get("tenancy", "") or "",
        price_per_unit=price_val,
        price_unit=first_price.get("unit", "") if first_price else "",
        effective_date=datetime.utcnow(),
        attributes=parsed_attrs,
        raw_data=row,
        source_api="infracost_dump"
    )

    raw = RawPricingData(
        provider=provider,
        node_id=row.get("productHash"),
        raw_json=row,
        source_api="infracost_dump"
    )

    return npd, raw
