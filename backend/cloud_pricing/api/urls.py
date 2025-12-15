from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import NormalizedPricingDataViewSet

router = DefaultRouter()
router.register(r'normalized-pricing-data', NormalizedPricingDataViewSet, basename='normalized-pricing-data')

urlpatterns = [
    path('', include(router.urls)),
]
