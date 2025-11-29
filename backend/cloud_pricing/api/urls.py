from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CloudProviderViewSet, ServiceCategoryViewSet, CloudServiceViewSet,
    RegionViewSet, PricingModelViewSet, CurrencyViewSet,
    PricingDataViewSet, PriceHistoryViewSet, PriceAlertViewSet
)
from .views import RawPricingDataViewSet
from .views import TCOView
from .views import FeatureLookup, LatestFeatures, FeatureHistory

router = DefaultRouter()
router.register(r'providers', CloudProviderViewSet)
router.register(r'categories', ServiceCategoryViewSet)
router.register(r'services', CloudServiceViewSet)
router.register(r'regions', RegionViewSet)
router.register(r'pricing-models', PricingModelViewSet)
router.register(r'currencies', CurrencyViewSet)
router.register(r'pricing', PricingDataViewSet, basename='pricing')
router.register(r'price-history', PriceHistoryViewSet)
router.register(r'price-alerts', PriceAlertViewSet)
router.register(r'raw-pricing', RawPricingDataViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('api/v1/features/lookup/', FeatureLookup.as_view(), name='feature-lookup'),
    path('api/v1/features/latest/', LatestFeatures.as_view(), name='features-latest'),
    path('api/v1/features/history/', FeatureHistory.as_view(), name='features-history'),
    path('api/v1/tco/', TCOView.as_view(), name='tco'),
]
