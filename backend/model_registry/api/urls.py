from django.urls import path
from .views import MLEngineViewSet

urlpatterns = [
    path('engines/', MLEngineViewSet.as_view({'get': 'list', 'post': 'create'}), name='mlengine-list'),
    path('engines/summary/', MLEngineViewSet.as_view({'get': 'summary'}), name='mlengine-summary'),
    path('engines/types/', MLEngineViewSet.as_view({'get': 'get_types'}), name='mlengine-types'),
    path('engines/predict-by-type/<str:model_type>/', MLEngineViewSet.as_view({'post': 'predict_by_type'}), name='mlengine-predict-by-type'),
    path('engines/predict/<str:engine_name>/', MLEngineViewSet.as_view({'post': 'predict'}), name='mlengine-predict'),
    path('engines/<uuid:pk>/', MLEngineViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='mlengine-detail'),
]