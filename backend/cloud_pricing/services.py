import os
import json
import logging
import requests
from datetime import datetime
from decimal import Decimal
from django.db import transaction

from .models import (
    CloudProvider,
    CloudService,
    Region,
    PricingModel,
    Currency,
    ServiceCategory,
    PricingData,
    PriceHistory,
    APICallLog,
)

logger = logging.getLogger(__name__)

# Default to the Infracost pricing GraphQL endpoint (see their example curl):
# curl https://pricing.api.infracost.io/graphql -X POST -H 'X-Api-Key: YOUR_API_KEY' ...
INFRACOST_GQL_URL = os.environ.get("INFRACOST_GQL_URL", "https://pricing.api.infracost.io/graphql")
INFRACOST_API_KEY = os.environ.get("INFRACOST_API_KEY")


class InfracostPricingService:
    """Fetch pricing from the Infracost Cloud Pricing GraphQL API and save into models."""

    def __init__(self, vendor_name="aws"):
        if not INFRACOST_API_KEY:
            raise RuntimeError("INFRACOST_API_KEY environment variable must be set")
        self.vendor_name = vendor_name
        # Ensure provider + currency exist
        self.provider, _ = CloudProvider.objects.get_or_create(
            name=vendor_name, defaults={"display_name": vendor_name.upper()}
        )
        self.currency, _ = Currency.objects.get_or_create(
            code="USD", defaults={"name": "US Dollar", "symbol": "$"}
        )

    def _run_query(self, query, variables=None):
        headers = {"X-Api-Key": INFRACOST_API_KEY, "Content-Type": "application/json"}
        payload = {"query": query, "variables": variables or {}}
        started = datetime.utcnow()
        status = 0
        error_message = ""
        resp = None
        try:
            resp = requests.post(INFRACOST_GQL_URL, headers=headers, json=payload, timeout=30)
            status = getattr(resp, 'status_code', 0)
            # Try to parse JSON if present
            try:
                data = resp.json()
            except ValueError:
                data = None

            # If non-200, capture body and return as error
            if status != 200:
                error_message = (resp.text or '')[:2000]
                logger.error('Infracost returned non-200 status %s: %s', status, error_message[:2000])
                return None, status, error_message

            # 200 OK, but GraphQL errors may be present
            if data is None:
                error_message = (resp.text or '')[:2000]
                return None, status, error_message

            if "errors" in data:
                error_message = json.dumps(data["errors"])[:2000]

            return data.get("data"), status, error_message
        except requests.RequestException as e:
            # Network/HTTP-level error
            logger.exception("Infracost API request failed: %s", e)
            if resp is not None:
                status = getattr(resp, 'status_code', status)
                error_message = (getattr(resp, 'text', '') or '')[:2000]
            else:
                error_message = str(e)[:2000]
            return None, status, error_message
        except Exception as e:
            logger.exception("Unexpected error calling Infracost API: %s", e)
            error_message = str(e)[:2000]
            return None, status, error_message
        finally:
            # Log call with response snippet for easier debugging
            try:
                APICallLog.objects.create(
                    provider=self.provider,
                    api_endpoint=INFRACOST_GQL_URL,
                    status_code=status,
                    response_time=(datetime.utcnow() - started).total_seconds(),
                    records_updated=0,
                    error_message=error_message,
                )
            except Exception:
                logger.exception("Failed to write APICallLog")

    def products_query(self, filters, first=100, after=None):
        """Return a GraphQL query string that inlines the filter (the pricing API doesn't use Relay pagination/variables)."""
        # Build a GraphQL filter literal from the provided filters dict.
        def serialize_value(v):
            # Strings need quotes, booleans/numbers not
            if isinstance(v, str):
                return json.dumps(v)
            if isinstance(v, bool):
                return 'true' if v else 'false'
            if v is None:
                return 'null'
            if isinstance(v, (list, tuple)):
                return '[' + ','.join(serialize_value(x) for x in v) + ']'
            if isinstance(v, dict):
                items = [f"{k}: {serialize_value(val)}" for k, val in v.items()]
                return '{' + ','.join(items) + '}'
            return str(v)

        # Special handling for attributeFilters (list of {key,value} pairs)
        filter_parts = []
        for k, v in (filters or {}).items():
            if k == 'attributeFilters' and isinstance(v, (list, tuple)):
                af_parts = []
                for af in v:
                    # each af is a dict with 'key' and 'value'
                    kv = ','.join(f"{kk}: {serialize_value(vv)}" for kk, vv in af.items())
                    af_parts.append('{' + kv + '}')
                filter_parts.append(f"attributeFilters: [{','.join(af_parts)}]")
            else:
                filter_parts.append(f"{k}: {serialize_value(v)}")

                filter_literal = '{' + ','.join(filter_parts) + '}' if filter_parts else '{}'

                q = f'''query {{
    products(filter: {filter_literal}) {{
        vendorName
        service
        productFamily
        region
        attributes {{ key value }}
        prices(filter: {{}}) {{ USD unit description purchaseOption startUsageAmount endUsageAmount termPurchaseOption termLength termOfferingClass }}
    }}
}}'''

        # We return the raw query string and no variables
        return q, None

    def fetch_and_save(self, filters=None, max_pages=10):
        """Fetch products from Infracost and save results to models. filters is a dict matching the ProductFilter input."""
        filters = filters or {"vendorName": self.vendor_name}
        after = None
        pages = 0
        total_saved = 0
        while pages < max_pages:
            query, variables = self.products_query(filters)
            data, status, err = self._run_query(query, variables)
            if data is None:
                logger.error("No data returned from Infracost query: %s", err)
                break

            # The pricing API returns a list of products under data['products']
            prod_list = data.get('products')
            if prod_list is None:
                # Some older shapes might return product directly or nested differently
                logger.error('Unexpected products shape in response: %s', data)
                break

            # If it's a dict (single product), wrap it
            if isinstance(prod_list, dict):
                products = [prod_list]
            else:
                products = list(prod_list)

            logger.info('Fetched %d products from Infracost (page %d)', len(products), pages+1)

            for node in products:
                if not node:
                    continue
                saved = self._process_product_node(node)
                total_saved += saved

            # The pricing API does not use Relay pagination; do a single pass unless caller provides a different filter
            break

        # Update last APICallLog record with total saved (best-effort)
        try:
            last = APICallLog.objects.filter(provider=self.provider).first()
            if last:
                last.records_updated = total_saved
                last.save()
        except Exception:
            pass

        return total_saved

    def _process_product_node(self, node):
        """Map a product node and its prices into our models. Returns number of PricingData records created/updated."""
        # Basic fields
        service_code = node.get("service") or node.get("vendorName")
        service_name = node.get("service") or service_code
        product_family = node.get("productFamily")
        region_code = node.get("region") or "global"

        # Build attributes dict
        attrs = {a.get("key"): a.get("value") for a in node.get("attributes", [])}

        # Ensure Service, Region, Category exist
        category, _ = ServiceCategory.objects.get_or_create(name=product_family or "General")
        service, _ = CloudService.objects.get_or_create(
            provider=self.provider,
            service_code=service_code,
            defaults={"service_name": service_name, "category": category},
        )
        region, _ = Region.objects.get_or_create(
            provider=self.provider, region_code=region_code, defaults={"region_name": region_code}
        )

        # prices can be returned as a flat list of price objects, or as a Relay-style
        # connection with edges->node. Support both shapes.
        prices = node.get("prices", [])
        if isinstance(prices, dict):
            # Relay-style
            if 'edges' in prices:
                prices = [e.get('node', {}) for e in prices.get('edges', [])]
            else:
                # single price object
                prices = [prices]

        saved = 0
        for p in prices:
            usd = p.get("USD")
            if usd is None:
                continue
            try:
                unit = p.get("unit") or p.get("unit")
                purchase = p.get("purchaseOption") or "on_demand"
                pricing_model, _ = PricingModel.objects.get_or_create(
                    name=purchase, defaults={"display_name": purchase.replace('_', ' ').title()}
                )

                instance_type = attrs.get("instanceType") or attrs.get("machineType") or attrs.get("instance_type", "")
                operating_system = attrs.get("operatingSystem") or attrs.get("operating_system", "")
                tenancy = attrs.get("tenancy", "")

                with transaction.atomic():
                    obj, created = PricingData.objects.update_or_create(
                        provider=self.provider,
                        service=service,
                        region=region,
                        pricing_model=pricing_model,
                        currency=self.currency,
                        instance_type=instance_type,
                        defaults={
                            "product_family": product_family,
                            "operating_system": operating_system,
                            "tenancy": tenancy,
                            "price_per_unit": Decimal(str(usd)),
                            "price_unit": unit or "",
                            "effective_date": datetime.utcnow(),
                            "attributes": attrs,
                            "raw_data": p,
                            "source_api": "infracost",
                        },
                    )

                    if not created:
                        # Log history when price changes
                        self._log_price_history(obj, Decimal(str(usd)))

                    saved += 1
            except Exception:
                logger.exception("Failed to save price record for node %s", node.get("id"))
                continue

        return saved

    def _log_price_history(self, pricing_obj, new_price):
        old_price = pricing_obj.price_per_unit
        if old_price != new_price:
            change_pct = ((new_price - old_price) / old_price * 100) if old_price else None
            PriceHistory.objects.create(
                pricing_data=pricing_obj,
                price_per_unit=old_price,
                change_percentage=change_pct,
            )


class CloudPricingOrchestrator:
    """Orchestrator that uses Infracost as source for providers."""

    def __init__(self):
        self.infracost = InfracostPricingService(vendor_name="aws")

    def fetch_provider_pricing(self, provider_name):
        if provider_name.lower() == "aws":
            return self.infracost.fetch_and_save(filters={"vendorName": "aws"})
        return 0

    def fetch_all_pricing_data(self):
        total = 0
        for provider_name in ["aws"]:
            total += self.fetch_provider_pricing(provider_name)
        return total
