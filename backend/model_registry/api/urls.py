from django.urls import path
from .views import MLModelListCreateView, MLModelDetailView, ModelVersionListCreateView

urlpatterns = [
    path('models/', MLModelListCreateView.as_view(), name='model-list-create'),
    path('models/<int:pk>/', MLModelDetailView.as_view(), name='model-detail'),
    path('models/<int:model_id>/versions/', ModelVersionListCreateView.as_view(), name='model-version-list-create'),
]
