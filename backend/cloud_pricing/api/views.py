from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from django.conf import settings
from .models import (
    CloudProvider, CloudService, Region, ServiceCategory,
    PricingModel, Currency, PricingData, PriceHistory, PriceAlert
)
from .serializers import (
    CloudProviderSerializer, CloudServiceSerializer, RegionSerializer,
    ServiceCategorySerializer, PricingModelSerializer, CurrencySerializer,
    PricingDataSerializer, PriceHistorySerializer, PriceAlertSerializer
)
import requests
import logging

logger = logging.getLogger(__name__)


# ---------- BASIC CRUD VIEWSETS ----------

class CloudProviderViewSet(viewsets.ModelViewSet):
    queryset = CloudProvider.objects.all()
    serializer_class = CloudProviderSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]


class ServiceCategoryViewSet(viewsets.ModelViewSet):
    queryset = ServiceCategory.objects.all()
    serializer_class = ServiceCategorySerializer
    permission_classes = [IsAuthenticatedOrReadOnly]


class CloudServiceViewSet(viewsets.ModelViewSet):
    queryset = CloudService.objects.select_related("provider").all()
    serializer_class = CloudServiceSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]


class RegionViewSet(viewsets.ModelViewSet):
    queryset = Region.objects.select_related("provider").all()
    serializer_class = RegionSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]


class PricingModelViewSet(viewsets.ModelViewSet):
    queryset = PricingModel.objects.all()
    serializer_class = PricingModelSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]


class CurrencyViewSet(viewsets.ModelViewSet):
    queryset = Currency.objects.all()
    serializer_class = CurrencySerializer
    permission_classes = [IsAuthenticatedOrReadOnly]


class PricingDataViewSet(viewsets.ModelViewSet):
    queryset = PricingData.objects.select_related(
        "provider", "service", "region", "pricing_model", "currency"
    ).all()
    serializer_class = PricingDataSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    # ---------- CUSTOM ACTION TO FETCH LIVE INFRACOST PRICING ----------
    @action(detail=False, methods=["post"], url_path="fetch-infracost")
    def fetch_infracost_price(self, request):
        """
        Fetch live price from Infracost GraphQL API.
        Example payload:
        {
            "provider": "aws",
            "service": "AmazonEC2",
            "region": "us-east-1",
            "instance_type": "m3.large",
            "operating_system": "Linux"
        }
        """
        api_key = getattr(settings, "INFRACOST_API_KEY", None)
        if not api_key:
            return Response({"error": "Missing INFRACOST_API_KEY in settings."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        payload = request.data
        provider = payload.get("provider", "aws")
        service = payload.get("service", "AmazonEC2")
        region = payload.get("region", "us-east-1")
        instance_type = payload.get("instance_type", "m3.large")
        os = payload.get("operating_system", "Linux")

        query = {
            "query": f"""{{
                products(
                    filter: {{
                        vendorName: "{provider}",
                        service: "{service}",
                        productFamily: "Compute Instance",
                        region: "{region}",
                        attributeFilters: [
                            {{key: "instanceType", value: "{instance_type}"}},
                            {{key: "operatingSystem", value: "{os}"}},
                            {{key: "tenancy", value: "Shared"}},
                            {{key: "capacitystatus", value: "Used"}},
                            {{key: "preInstalledSw", value: "NA"}}
                        ]
                    }}
                ) {{
                    prices(filter: {{ purchaseOption: "on_demand" }}) {{
                        USD
                    }}
                }}
            }}"""
        }

        headers = {
            "X-Api-Key": api_key,
            "Content-Type": "application/json"
        }

        try:
            response = requests.post("https://pricing.api.infracost.io/graphql",
                                     headers=headers, json=query, timeout=15)
            response.raise_for_status()
            data = response.json()

            # Extract price
            usd_price = None
            try:
                usd_price = data["data"]["products"][0]["prices"][0]["USD"]
            except (KeyError, IndexError, TypeError):
                usd_price = None

            return Response({
                "provider": provider,
                "service": service,
                "region": region,
                "instance_type": instance_type,
                "price_usd": usd_price,
                "raw": data
            }, status=status.HTTP_200_OK)

        except requests.RequestException as e:
            logger.error(f"Infracost API error: {e}")
            return Response({"error": str(e)}, status=status.HTTP_502_BAD_GATEWAY)


class PriceHistoryViewSet(viewsets.ModelViewSet):
    queryset = PriceHistory.objects.select_related("pricing_data").all()
    serializer_class = PriceHistorySerializer
    permission_classes = [IsAuthenticatedOrReadOnly]


class PriceAlertViewSet(viewsets.ModelViewSet):
    queryset = PriceAlert.objects.select_related("pricing_data", "user").all()
    serializer_class = PriceAlertSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
