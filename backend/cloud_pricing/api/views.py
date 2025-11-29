from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly, AllowAny
from rest_framework.views import APIView
from django.conf import settings
from django.db.models import Q
from ..models import (
    CloudProvider, CloudService, Region, ServiceCategory,
    PricingModel, Currency, NormalizedPricingData, PriceHistory, PriceAlert
)
from ..models import RawPricingData
from .serializers import (
    CloudProviderSerializer, CloudServiceSerializer, RegionSerializer,
    ServiceCategorySerializer, PricingModelSerializer, CurrencySerializer,
    PricingDataSerializer, PriceHistorySerializer, PriceAlertSerializer
)
from .serializers import RawPricingDataSerializer
from .serializers import TCORequestSerializer
import requests
import logging
import re
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from feature_repo.duckdb_client import connect, path_for_store
from django.core.exceptions import ImproperlyConfigured

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
    queryset = NormalizedPricingData.objects.select_related(
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


class TCOView(APIView):
    """Simple TCO estimator endpoint for the frontend MVP."""
    # Explicitly allow anonymous access so the frontend can call this endpoint
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = TCORequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        # frontend sends resource_type (cpu/gpu/memory/storage)
        resource_type = (data.get('resource_type') or 'cpu').lower()
        cpu_hours = float(data.get('cpu_hours_per_month', 720))
        duration_months = int(data.get('duration_months', 12))
        regions = data.get('region_preferences') or []
        providers = data.get('providers') or ['aws', 'azure', 'gcp']

        results = []
        for prov in providers:
            # find the best matching pricing record in DB using resource intent heuristics
            # If regions list is empty, search across all regions and pick the cheapest one
            # select records that have some kind of price available (hourly, unit, or monthly)
            qs = NormalizedPricingData.objects.filter(
                provider__name__iexact=prov,
                is_active=True
            ).filter(
                Q(price_per_hour__isnull=False) | Q(price_per_unit__isnull=False) | Q(price_per_month__isnull=False)
            )

            # Simple heuristics over JSON attributes / instance_type to match resource intent
            if resource_type == 'gpu':
                qs = qs.filter(
                    Q(attributes__icontains='"gpu"') |
                    Q(attributes__icontains='accelerator') |
                    Q(instance_type__icontains='gpu')
                )
            elif resource_type == 'memory':
                qs = qs.filter(
                    Q(attributes__icontains='memory') |
                    Q(attributes__icontains='ram') |
                    Q(instance_type__icontains='mem')
                )
            elif resource_type == 'storage':
                qs = qs.filter(
                    Q(attributes__icontains='storage') |
                    Q(attributes__icontains='ssd') |
                    Q(attributes__icontains='hdd')
                )
            else:  # cpu / generic
                # Include records whose product_family mentions "Compute Instance",
                # or otherwise exclude obvious GPU/accelerator entries.
                qs = qs.filter(
                    Q(product_family__icontains='compute instance'))

            if regions:
                qs = qs.filter(region__region_code__in=regions)
            # Order by price ascending (cheapest first), then prefer the most recent effective_date
            qs = qs.filter(price_per_unit__isnull=False).filter(price_per_unit__gt=0).order_by('price_per_unit')
            rec = qs.first()

            if rec is None: continue

            print(rec.price_per_unit, rec.price_unit, rec.product_family)

            # Derive hourly/monthly/yearly from price_per_unit and price_unit heuristics
            ppu = rec.price_per_unit
            unit = (rec.price_unit or "").strip().lower()
            price_per_hour = None
            monthly = None
            yearly = None

            try:
                if ppu is not None:
                    ppu = float(ppu)
                    # Use cpu_hours as the number of billable hours per month (default from request)
                    hours_per_month = float(cpu_hours) if cpu_hours else 720.0

                    # Storage / per-GiB units are hard to convert to instance costs without a size;
                    # treat as non-applicable unless they are per-hour
                    if "gib" in unit or "gb" in unit or "byte" in unit:
                        if "hour" in unit:
                            price_per_hour = ppu
                            monthly = price_per_hour * hours_per_month
                        elif "second" in unit:
                            price_per_hour = ppu * 3600.0
                            monthly = price_per_hour * hours_per_month
                        elif "month" in unit:
                            # per-GiB-month -> cannot convert to instance cost without size, leave None
                            price_per_hour = None
                            monthly = None
                        else:
                            price_per_hour = None
                            monthly = None

                    # Per-month pricing (e.g. "month")
                    elif "month" in unit:
                        monthly = ppu
                        price_per_hour = monthly / hours_per_month if hours_per_month else None

                    # Per-minute pricing
                    elif "min" in unit or "minute" in unit:
                        price_per_hour = ppu * 60.0
                        monthly = price_per_hour * hours_per_month

                    # Per-second pricing
                    elif "sec" in unit or "second" in unit:
                        price_per_hour = ppu * 3600.0
                        monthly = price_per_hour * hours_per_month

                    # Per-hour / per-hr variants
                    elif "hour" in unit or "hr" in unit or "hrs" in unit or "/hour" in unit:
                        price_per_hour = ppu
                        monthly = price_per_hour * hours_per_month

                    # Ambiguous/single-unit/quantity -> assume per-hour (common for compute instances)
                    elif unit in ("", "1", "quantity") or re.match(r"^\d+$", unit):
                        price_per_hour = ppu
                        monthly = price_per_hour * hours_per_month

                    # Fallback to existing explicit fields if we couldn't derive from unit
                    else:
                        price_per_hour = rec.price_per_hour if rec.price_per_hour is not None else None
                        monthly = rec.price_per_month if rec.price_per_month is not None else (price_per_hour * hours_per_month if price_per_hour else None)

                    if monthly is not None:
                        yearly = monthly * 12.0
                    else:
                        yearly = rec.price_per_year if rec.price_per_year is not None else None

                else:
                    # no price_per_unit available: fall back to explicit fields
                    price_per_hour = rec.price_per_hour if rec.price_per_hour is not None else None
                    monthly = rec.price_per_month if rec.price_per_month is not None else None
                    yearly = rec.price_per_year if rec.price_per_year is not None else None

            except (TypeError, ValueError):
                price_per_hour = rec.price_per_hour if rec.price_per_hour is not None else None
                monthly = rec.price_per_month if rec.price_per_month is not None else None
                yearly = rec.price_per_year if rec.price_per_year is not None else None

            results.append({
                'provider': prov,
                'region': rec.region.region_code if rec else None,
                'instance_type': rec.instance_type if rec else None,
                'price_per_hour': price_per_hour,
                'monthly_cost': monthly,
                'yearly_cost': yearly,
            })

        # find best (lowest monthly) where available
        best = None
        available = [r for r in results if r['monthly_cost'] is not None]
        if available:
            best = min(available, key=lambda x: x['monthly_cost'])

        return Response({'results': results, 'best': best})


class PriceHistoryViewSet(viewsets.ModelViewSet):
    queryset = PriceHistory.objects.select_related("pricing_data").all()
    serializer_class = PriceHistorySerializer
    permission_classes = [IsAuthenticatedOrReadOnly]


class PriceAlertViewSet(viewsets.ModelViewSet):
    queryset = PriceAlert.objects.select_related("pricing_data", "user").all()
    serializer_class = PriceAlertSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]


class RawPricingDataViewSet(viewsets.ModelViewSet):
    queryset = RawPricingData.objects.select_related("provider", "normalized").all()
    serializer_class = RawPricingDataSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]


class FeatureLookup(APIView):
    """Lookup latest feature values for a pricing entity.

    Query params:
      - pricing_data_id (int)
      - node_id (str)

    Returns JSON mapping feature -> { value, raw_value, computed_at }
    """
    permission_classes = [AllowAny]

    def get(self, request):
        pricing_data_id = request.query_params.get('pricing_data_id')
        node_id = request.query_params.get('node_id')

        if not pricing_data_id and not node_id:
            return Response({'error': 'Provide pricing_data_id or node_id'}, status=status.HTTP_400_BAD_REQUEST)
        # Try Feast online store first (if Feast and a feature repo are available)
        try:
            from feast import FeatureStore
            from pathlib import Path

            repo_path = Path(__file__).resolve().parents[2] / 'feature_repo'
            fs = FeatureStore(repo_path=str(repo_path))

            # Build entity rows
            entity = {}
            if pricing_data_id:
                entity['pricing_data_id'] = int(pricing_data_id)
            elif node_id:
                entity['node_id'] = node_id

            # Feature refs expected (must match your feature repo definitions)
            feature_refs = [
                'current_price',
                'price_history_count',
                'latest_change_pct',
            ]

            try:
                of = fs.get_online_features(feature_refs, [entity])
                # of is a Feast OnlineResponse / dictionary-like; convert to dict safely
                out = of.to_dict() if hasattr(of, 'to_dict') else dict(of)
                # Format into feature -> value mapping
                features = {}
                # Depending on Feast version, of.to_dict() structure varies; handle common layouts
                if 'values' in out and 'fields' in out:
                    # new-format: {'values': [[...]], 'fields': [...]} 
                    fields = out['fields']
                    vals = out['values'][0] if out['values'] else []
                    for i, f in enumerate(fields):
                        features[f] = {'value': vals[i] if i < len(vals) else None}
                else:
                    # fallback: attempt to read as plain dict of lists
                    for k, v in out.items():
                        features[k] = {'value': v[0] if isinstance(v, list) and v else v}

                return Response({'features': features})
            except Exception:
                # If Feast repo or online lookup fails, fall through to offline methods
                logger.exception('Feast online lookup failed (falling back to offline)')
        except Exception:
            # Feast not available or repo missing — continue to offline lookup
            logger.debug('Feast not configured or unavailable; using offline store')

        # Try DuckDB offline store
        try:
            con = connect(path_for_store())
            if pricing_data_id:
                rows = con.execute(
                    'SELECT feature, value, raw_value, computed_at FROM feature_values WHERE pricing_data_id = ? ORDER BY computed_at DESC',
                    (int(pricing_data_id),)
                ).fetchall()
            else:
                rows = con.execute(
                    'SELECT feature, value, raw_value, computed_at FROM feature_values WHERE node_id = ? ORDER BY computed_at DESC',
                    (node_id,)
                ).fetchall()
            con.close()
            # Keep latest per feature
            feature_map = {}
            for feat, val, raw, ts in rows:
                if feat not in feature_map:
                    feature_map[feat] = {'value': val, 'raw_value': raw, 'computed_at': str(ts)}
            return Response({'features': feature_map})
        except Exception:
            # Fall back to Django model if present
            try:
                from ..models import FeatureValue
                qs = FeatureValue.objects.filter(pricing_data__id=pricing_data_id) if pricing_data_id else FeatureValue.objects.filter(node_id=node_id)
                qs = qs.order_by('-computed_at')
                feature_map = {}
                for fv in qs:
                    if fv.feature.name not in feature_map:
                        feature_map[fv.feature.name] = {
                            'value': float(fv.value) if fv.value is not None else None,
                            'raw_value': fv.raw_value,
                            'computed_at': fv.computed_at.isoformat() if fv.computed_at else None,
                        }
                return Response({'features': feature_map})
            except ImproperlyConfigured:
                return Response({'error': 'No offline feature store available'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            except Exception:
                logger.exception('Feature lookup failed')
                return Response({'error': 'Feature lookup failed'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LatestFeatures(APIView):
    """Return the latest feature values (online-first). Use this for serving/real-time queries.

    Query params:
        - pricing_data_id (int)
        - node_id (str)

    Returns a mapping feature -> { value, raw_value, computed_at }
    """
    permission_classes = [AllowAny]

    def get(self, request):
        pricing_data_id = request.query_params.get('pricing_data_id')
        node_id = request.query_params.get('node_id')

        if not pricing_data_id and not node_id:
            return Response({'error': 'Provide pricing_data_id or node_id'}, status=status.HTTP_400_BAD_REQUEST)

        # Try Feast online store first
        try:
            from feast import FeatureStore
            from pathlib import Path

            repo_path = Path(__file__).resolve().parents[2] / 'feature_repo'
            fs = FeatureStore(repo_path=str(repo_path))

            entity = {}
            if pricing_data_id:
                entity['pricing_data_id'] = int(pricing_data_id)
            else:
                entity['node_id'] = node_id

            # Define the feature refs you expect to serve; adjust if you have a canonical repo
            feature_refs = [
                'current_price',
                'previous_price',
                'price_diff_abs',
                'price_diff_pct',
                'days_since_price_change',
                'price_change_frequency_90d',
            ]

            of = fs.get_online_features(feature_refs, [entity])
            out = of.to_dict() if hasattr(of, 'to_dict') else dict(of)

            # Convert to feature->value mapping (best-effort across Feast versions)
            features = {}
            if 'values' in out and 'fields' in out:
                fields = out['fields']
                vals = out['values'][0] if out['values'] else []
                for i, f in enumerate(fields):
                    features[f] = {'value': vals[i] if i < len(vals) else None}
            else:
                for k, v in out.items():
                    features[k] = {'value': v[0] if isinstance(v, list) and v else v}

            return Response({'features': features})
        except Exception:
            logger.exception('Feast online lookup failed or unavailable; falling back to DuckDB')

        # Fallback to DuckDB latest per feature
        try:
            con = connect(path_for_store())
            if pricing_data_id:
                rows = con.execute(
                    'SELECT feature, value, raw_value, computed_at FROM feature_values WHERE pricing_data_id = ? ORDER BY computed_at DESC',
                    (int(pricing_data_id),)
                ).fetchall()
            else:
                rows = con.execute(
                    'SELECT feature, value, raw_value, computed_at FROM feature_values WHERE node_id = ? ORDER BY computed_at DESC',
                    (node_id,)
                ).fetchall()
            con.close()

            feature_map = {}
            for feat, val, raw, ts in rows:
                if feat not in feature_map:
                    feature_map[feat] = {'value': val, 'raw_value': raw, 'computed_at': str(ts)}
            return Response({'features': feature_map})
        except Exception:
            logger.exception('DuckDB lookup failed for latest features')
            return Response({'error': 'Latest feature lookup failed'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class FeatureHistory(APIView):
    """Return historical feature rows from the offline DuckDB store (for training/backfills).

    Query params:
        - pricing_data_id (int) OR node_id (str)
        - feature (optional) to filter a specific feature
        - start_date, end_date (ISO) optional time range filter on computed_at
    """
    permission_classes = [AllowAny]

    def get(self, request):
        pricing_data_id = request.query_params.get('pricing_data_id')
        node_id = request.query_params.get('node_id')
        feature = request.query_params.get('feature')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        if not pricing_data_id and not node_id:
            return Response({'error': 'Provide pricing_data_id or node_id'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            con = connect(path_for_store())
            params = []
            where = []
            if pricing_data_id:
                where.append('pricing_data_id = ?')
                params.append(int(pricing_data_id))
            else:
                where.append('node_id = ?')
                params.append(node_id)
            if feature:
                where.append('feature = ?')
                params.append(feature)
            if start_date:
                where.append('computed_at >= ?')
                params.append(start_date)
            if end_date:
                where.append('computed_at <= ?')
                params.append(end_date)

            where_sql = ' AND '.join(where)
            sql = f"SELECT feature, value, raw_value, computed_at FROM feature_values WHERE {where_sql} ORDER BY computed_at DESC"
            rows = con.execute(sql, tuple(params)).fetchall()
            con.close()

            # Return list of rows
            out = []
            for feat, val, raw, ts in rows:
                out.append({
                    'feature': feat,
                    'value': val,
                    'raw_value': raw,
                    'computed_at': str(ts),
                })
            return Response({'history': out})
        except Exception:
            logger.exception('DuckDB history lookup failed')
            return Response({'error': 'Feature history lookup failed'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
