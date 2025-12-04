from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CloudProviderViewSet, CloudServiceViewSet,
    RegionViewSet, PricingModelViewSet, CurrencyViewSet,
    PricingDataViewSet, PriceHistoryViewSet
)
from .views import RawPricingDataViewSet
from .views import TCOView

router = DefaultRouter()
router.register(r'providers', CloudProviderViewSet)
router.register(r'services', CloudServiceViewSet)
router.register(r'regions', RegionViewSet)
router.register(r'pricing-models', PricingModelViewSet)
router.register(r'currencies', CurrencyViewSet)
router.register(r'pricing', PricingDataViewSet, basename='pricing')
router.register(r'price-history', PriceHistoryViewSet)
router.register(r'raw-pricing', RawPricingDataViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('api/v1/tco/', TCOView.as_view(), name='tco'),
]
