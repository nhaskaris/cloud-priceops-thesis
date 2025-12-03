from django.urls import path
from . import views

app_name = "feast_offline_api"

urlpatterns = [
    # Online features endpoint - fetches latest features from Redis
    path(
        "feast/features/online/",
        views.GetOnlineFeaturesAPIView.as_view(),
        name="online-features"
    ),
    
    # Training data endpoint - fetches historical features from PostgreSQL
    path(
        "feast/features/training-data/",
        views.GetTrainingDataAPIView.as_view(),
        name="training-data"
    ),
]
