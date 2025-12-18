from django.urls import path
from .views import MLEngineViewSet

urlpatterns = [
    path('engines/', MLEngineViewSet.as_view({'get': 'list', 'post': 'create'}), name='mlengine-list'),
    path('engines/<uuid:pk>/', MLEngineViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='mlengine-detail'),
    path('engines/predict/<str:engine_name>/', MLEngineViewSet.as_view({'post': 'predict'}), name='mlengine-predict'),
]