import logging
from rest_framework import viewsets
from rest_framework.permissions import AllowAny

from ..models import NormalizedPricingData
from .serializers import PricingDataSerializer

from django_filters.rest_framework import DjangoFilterBackend

logger = logging.getLogger(__name__)

class NormalizedPricingDataViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = NormalizedPricingData.objects.all()
    serializer_class = PricingDataSerializer
    permission_classes = [AllowAny]
    filterset_fields = {'domain_label'}
    filter_backends = [DjangoFilterBackend]
    
    def get_queryset(self):
        queryset = NormalizedPricingData.objects.filter(is_active=True, effective_price_per_hour__gt=0)
        
        return queryset
