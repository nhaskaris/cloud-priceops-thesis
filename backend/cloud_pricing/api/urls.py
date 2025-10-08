from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create router and register viewsets
router = DefaultRouter()
router.register(r'providers', views.CloudProviderViewSet)
router.register(r'services', views.CloudServiceViewSet)
router.register(r'regions', views.RegionViewSet)
router.register(r'pricing', views.PricingDataViewSet)
router.register(r'price-history', views.PriceHistoryViewSet)
router.register(r'price-alerts', views.PriceAlertViewSet, basename='pricealert')
router.register(r'management', views.PricingManagementViewSet, basename='pricing-management')

app_name = 'cloud_pricing'

urlpatterns = [
    path('api/', include(router.urls)),
]