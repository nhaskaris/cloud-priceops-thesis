"""
Unified cloud pricing service using Infracost API
"""

import requests
import time
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class InfracostPricingService:
    """Unified pricing service for AWS, Azure, and GCP via Infracost API"""

    API_URL = "https://pricing.api.infracost.io/graphql"

    def __init__(self):
        self.api_key = settings.INFRACOST_API_KEY
        if not self.api_key:
            raise ValueError("INFRACOST_API_KEY is not set in settings or environment")

    def _post_query(self, query: str, provider: str):
        from .tasks import log_api_call

        """Execute GraphQL query and log results"""
        headers = {"X-Api-Key": self.api_key, "Content-Type": "application/json"}
        start_time = time.time()
        resp = requests.post(self.API_URL, headers=headers, json={"query": query})
        duration = time.time() - start_time

        try:
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            data = {"error": str(e)}

        # Log API call asynchronously
        log_api_call.delay(
            provider_name=provider,
            endpoint=self.API_URL,
            status_code=resp.status_code,
            response_time=duration,
            records_updated=len(data.get("data", {}).get("products", []))
            if "data" in data
            else 0,
            error_message=data.get("error", ""),
        )

        return data

    def _build_query(self, vendor, service, product_family, region, attributes):
        """Build Infracost GraphQL query"""
        filters = ", ".join(
            [f'{{key: "{a["key"]}", value: "{a["value"]}"}}' for a in attributes]
        )
        return f"""
        {{
          products(
            filter: {{
              vendorName: "{vendor}",
              service: "{service}",
              productFamily: "{product_family}",
              region: "{region}",
              attributeFilters: [{filters}]
            }}
          ) {{
            prices(filter: {{purchaseOption: "on_demand"}}) {{
              USD
              unit
              description
            }}
          }}
        }}
        """

    def fetch_all_pricing(self):
        """Fetch AWS, Azure, and GCP pricing through Infracost"""
        queries = [
            {
                "vendor": "aws",
                "service": "AmazonEC2",
                "product_family": "Compute Instance",
                "region": "us-east-1",
                "attributes": [
                    {"key": "instanceType", "value": "m3.large"},
                    {"key": "operatingSystem", "value": "Linux"},
                    {"key": "tenancy", "value": "Shared"},
                    {"key": "capacitystatus", "value": "Used"},
                    {"key": "preInstalledSw", "value": "NA"},
                ],
            },
            {
                "vendor": "azure",
                "service": "Virtual Machines",
                "product_family": "Compute",
                "region": "eastus",
                "attributes": [
                    {"key": "productName", "value": "Standard_D2_v3"},
                    {"key": "operatingSystem", "value": "Linux"},
                ],
            },
            {
                "vendor": "gcp",
                "service": "Compute Engine",
                "product_family": "Compute Instance",
                "region": "us-east1",
                "attributes": [
                    {"key": "machineType", "value": "n2-standard-2"},
                    {"key": "preemptible", "value": "false"},
                ],
            },
        ]

        results = {}
        for q in queries:
            query = self._build_query(
                q["vendor"], q["service"], q["product_family"], q["region"], q["attributes"]
            )
            resp = self._post_query(query, q["vendor"])
            results[q["vendor"]] = resp.get("data", {}).get("products", [])

        return results


class CloudPricingOrchestrator:
    """Unified orchestrator using Infracost for all providers"""

    def __init__(self):
        self.infracost_service = InfracostPricingService()

    def fetch_all_pricing_data(self):
        return self.infracost_service.fetch_all_pricing()

    def fetch_provider_pricing(self, provider_name):
        all_data = self.infracost_service.fetch_all_pricing()
        return {provider_name: all_data.get(provider_name, [])}
