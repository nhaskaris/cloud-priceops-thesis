from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Q, Avg, Min, Max, Count
from django.utils import timezone
from datetime import timedelta

from ..models import (
    CloudProvider,
    CloudService,
    Region,
    PricingData,
    PriceHistory,
    PriceAlert,
    ServiceCategory,
    PricingModel
)
from .serializers import (
    CloudProviderSerializer,
    CloudServiceSerializer,
    RegionSerializer,
    PricingDataSerializer,
    PricingDataDetailSerializer,
    PriceHistorySerializer,
    PriceAlertSerializer,
    PriceComparisonSerializer,
    PricingAnalyticsSerializer
)
from ..tasks import update_provider_pricing_data, update_all_pricing_data
from ..services import CloudPricingOrchestrator


class CloudProviderViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for cloud providers"""
    queryset = CloudProvider.objects.filter(is_active=True)
    serializer_class = CloudProviderSerializer
    
    @action(detail=True, methods=['post'])
    def update_pricing(self, request, pk=None):
        """Trigger pricing update for specific provider"""
        provider = self.get_object()
        
        try:
            # Trigger async task
            task = update_provider_pricing_data.delay(provider.name)
            
            return Response({
                'message': f'Pricing update initiated for {provider.display_name}',
                'task_id': task.id
            }, status=status.HTTP_202_ACCEPTED)
            
        except Exception as e:
            return Response({
                'error': f'Failed to initiate pricing update: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CloudServiceViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for cloud services"""
    queryset = CloudService.objects.filter(is_active=True)
    serializer_class = CloudServiceSerializer
    filterset_fields = ['provider', 'category']
    search_fields = ['service_name', 'service_code']


class RegionViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for cloud regions"""
    queryset = Region.objects.filter(is_active=True)
    serializer_class = RegionSerializer
    filterset_fields = ['provider']
    search_fields = ['region_name', 'region_code']


class PricingDataViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for pricing data"""
    queryset = PricingData.objects.filter(is_active=True).select_related(
        'provider', 'service', 'region', 'pricing_model', 'currency'
    )
    serializer_class = PricingDataSerializer
    filterset_fields = ['provider', 'service', 'region', 'pricing_model', 'instance_type']
    search_fields = ['instance_type', 'operating_system']
    ordering_fields = ['price_per_hour', 'price_per_month', 'effective_date']
    ordering = ['provider', 'service', 'instance_type']
    
    def get_serializer_class(self):
        """Use detailed serializer for individual records"""
        if self.action == 'retrieve':
            return PricingDataDetailSerializer
        return PricingDataSerializer
    
    @action(detail=False, methods=['get'])
    def compare_prices(self, request):
        """Compare prices across providers"""
        serializer = PriceComparisonSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        
        filters = Q(is_active=True)
        
        service_type = serializer.validated_data.get('service_type')
        if service_type:
            filters &= Q(service__service_code__icontains=service_type)
        
        instance_type = serializer.validated_data.get('instance_type')
        if instance_type:
            filters &= Q(instance_type__icontains=instance_type)
        
        region = serializer.validated_data.get('region')
        if region:
            filters &= Q(region__region_code__icontains=region)
        
        providers = serializer.validated_data.get('providers')
        if providers:
            filters &= Q(provider__name__in=providers)
        
        pricing_data = PricingData.objects.filter(filters).select_related(
            'provider', 'service', 'region'
        )
        
        # Group by provider
        comparison_data = {}
        for item in pricing_data:
            provider_name = item.provider.name
            if provider_name not in comparison_data:
                comparison_data[provider_name] = []
            
            comparison_data[provider_name].append({
                'service': item.service.service_name,
                'instance_type': item.instance_type,
                'region': item.region.region_name,
                'price_per_hour': float(item.price_per_hour) if item.price_per_hour else None,
                'price_per_month': float(item.price_per_month) if item.price_per_month else None,
                'currency': item.currency.code,
            })
        
        return Response(comparison_data)
    
    @action(detail=False, methods=['get'])
    def analytics(self, request):
        """Get pricing analytics"""
        serializer = PricingAnalyticsSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        
        filters = Q(is_active=True)
        
        provider = serializer.validated_data.get('provider')
        if provider:
            filters &= Q(provider__name=provider)
        
        service = serializer.validated_data.get('service')
        if service:
            filters &= Q(service__service_code__icontains=service)
        
        region = serializer.validated_data.get('region')
        if region:
            filters &= Q(region__region_code__icontains=region)
        
        date_range = serializer.validated_data.get('date_range', '30d')
        days = int(date_range.replace('d', ''))
        cutoff_date = timezone.now() - timedelta(days=days)
        filters &= Q(created_at__gte=cutoff_date)
        
        pricing_data = PricingData.objects.filter(filters)
        
        # Calculate analytics
        analytics = {
            'total_records': pricing_data.count(),
            'providers_count': pricing_data.values('provider').distinct().count(),
            'services_count': pricing_data.values('service').distinct().count(),
            'regions_count': pricing_data.values('region').distinct().count(),
        }
        
        # Price statistics
        price_stats = pricing_data.exclude(price_per_hour__isnull=True).aggregate(
            avg_price=Avg('price_per_hour'),
            min_price=Min('price_per_hour'),
            max_price=Max('price_per_hour')
        )
        analytics['price_statistics'] = price_stats
        
        # Provider breakdown
        provider_stats = pricing_data.values(
            'provider__name', 'provider__display_name'
        ).annotate(
            count=Count('id'),
            avg_price=Avg('price_per_hour')
        ).order_by('-count')
        
        analytics['provider_breakdown'] = list(provider_stats)
        
        return Response(analytics)


class PriceHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for price history"""
    queryset = PriceHistory.objects.all().select_related('pricing_data')
    serializer_class = PriceHistorySerializer
    filterset_fields = ['pricing_data']
    ordering = ['-recorded_at']


class PriceAlertViewSet(viewsets.ModelViewSet):
    """ViewSet for price alerts"""
    serializer_class = PriceAlertSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Return alerts for current user only"""
        return PriceAlert.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        """Set current user when creating alert"""
        serializer.save(user=self.request.user)


class PricingManagementViewSet(viewsets.ViewSet):
    """ViewSet for pricing management operations"""
    
    @action(detail=False, methods=['post'])
    def update_all_pricing(self, request):
        """Trigger pricing update for all providers"""
        try:
            task = update_all_pricing_data.delay()
            
            return Response({
                'message': 'Pricing update initiated for all providers',
                'task_id': task.id
            }, status=status.HTTP_202_ACCEPTED)
            
        except Exception as e:
            return Response({
                'error': f'Failed to initiate pricing update: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def pricing_summary(self, request):
        """Get overall pricing summary"""
        try:
            summary = {
                'total_pricing_records': PricingData.objects.filter(is_active=True).count(),
                'providers': CloudProvider.objects.filter(is_active=True).count(),
                'services': CloudService.objects.filter(is_active=True).count(),
                'regions': Region.objects.filter(is_active=True).count(),
                'last_updated': PricingData.objects.filter(is_active=True).order_by('-updated_at').first().updated_at if PricingData.objects.filter(is_active=True).exists() else None,
            }
            
            # Provider breakdown
            provider_breakdown = CloudProvider.objects.filter(is_active=True).annotate(
                pricing_records=Count('pricingdata', filter=Q(pricingdata__is_active=True))
            ).values('name', 'display_name', 'pricing_records')
            
            summary['provider_breakdown'] = list(provider_breakdown)
            
            return Response(summary)
            
        except Exception as e:
            return Response({
                'error': f'Failed to get pricing summary: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def test_api_connections(self, request):
        """Test connections to all cloud pricing APIs"""
        try:
            orchestrator = CloudPricingOrchestrator()
            
            results = {
                'aws': {'status': 'unknown', 'message': ''},
                'azure': {'status': 'unknown', 'message': ''},
                'gcp': {'status': 'unknown', 'message': ''},
            }
            
            # Test AWS
            try:
                aws_data = orchestrator.aws_service.get_ec2_pricing(region='us-east-1')
                results['aws'] = {
                    'status': 'success' if aws_data else 'no_data',
                    'message': f'Retrieved {len(aws_data)} records' if aws_data else 'No data returned',
                    'sample_count': len(aws_data[:5])  # First 5 records
                }
            except Exception as e:
                results['aws'] = {'status': 'error', 'message': str(e)}
            
            # Test Azure
            try:
                azure_data = orchestrator.azure_service.get_vm_pricing(region='eastus')
                results['azure'] = {
                    'status': 'success' if azure_data else 'no_data',
                    'message': f'Retrieved {len(azure_data)} records' if azure_data else 'No data returned',
                    'sample_count': len(azure_data[:5])
                }
            except Exception as e:
                results['azure'] = {'status': 'error', 'message': str(e)}
            
            # Test GCP
            try:
                gcp_data = orchestrator.gcp_service.get_compute_pricing()
                results['gcp'] = {
                    'status': 'success' if gcp_data else 'no_data',
                    'message': f'Retrieved {len(gcp_data)} records' if gcp_data else 'No data returned',
                    'sample_count': len(gcp_data[:5])
                }
            except Exception as e:
                results['gcp'] = {'status': 'error', 'message': str(e)}
            
            return Response(results)
            
        except Exception as e:
            return Response({
                'error': f'Failed to test API connections: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
