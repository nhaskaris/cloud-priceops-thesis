import joblib
import pandas as pd
import numpy as np
from rest_framework import viewsets, status, parsers
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Max, Q
from ..models import MLEngine
from .serializers import MLEngineSerializer
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiTypes
from ..tasks import compute_price_prediction

class MLEngineViewSet(viewsets.ModelViewSet):
    queryset = MLEngine.objects.all()
    serializer_class = MLEngineSerializer
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    @extend_schema(
        summary="Register a new ML Engine",
        description="""
            Uploads a model and its encoder. 
            **Note:** Since this is a multipart request, JSON fields like `feature_names` 
            should be sent as raw JSON strings.
        """,
        responses={201: MLEngineSerializer},
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        summary="Get Available Model Types",
        description="Returns all model types with their best performing model based on R² score.",
        responses={200: OpenApiTypes.OBJECT}
    )
    @action(detail=False, methods=['get'], url_path='types')
    def get_types(self, request):
        """
        Get all model types with their best model.
        Returns: [
            {
                "type": "Regression",
                "count": 3,
                "best_model": {
                    "name": "AWS_Compute_Pricing",
                    "version": "2025.12.18.06",
                    "r_squared": 0.9175,
                    "mape": 41.72,
                    "is_active": true
                },
                "log_transformed_features": [...],
                "categorical_features": [...]
            }
        ]
        """
        # Get all unique model types
        model_types = MLEngine.objects.values_list('model_type', flat=True).distinct()
        
        result = []
        for model_type in model_types:
            # Get all models of this type
            models = MLEngine.objects.filter(model_type=model_type)
            
            # Find best model by R² score (or use is_active as fallback)
            best_model = models.filter(r_squared__isnull=False).order_by('-r_squared', '-created_at').first()
            if not best_model:
                # If no R² scores, use active or most recent
                best_model = models.filter(is_active=True).first() or models.order_by('-created_at').first()
            
            if best_model:
                result.append({
                    "type": model_type,
                    "count": models.count(),
                    "best_model": {
                        "name": best_model.name,
                        "version": best_model.version,
                        "r_squared": best_model.r_squared,
                        "mape": best_model.mape,
                        "is_active": best_model.is_active
                    },
                    "log_transformed_features": best_model.log_transformed_features,
                    "categorical_features": best_model.categorical_features
                })
        
        return Response(result)

    @extend_schema(
        summary="Predict Price by Model Type",
        description="Automatically selects the best model of the given type and returns price prediction.",
        request=OpenApiTypes.OBJECT,
        examples=[
            OpenApiExample(
                'Regression Example',
                value={
                    "vcpu_count": 4,
                    "memory_gb": 16,
                    "region": "us-east-1",
                    "operating_system": "Linux",
                    "tenancy": "shared"
                },
                request_only=True,
            )
        ],
        responses={200: OpenApiTypes.OBJECT}
    )
    @action(detail=False, methods=['post'], url_path='predict-by-type/(?P<model_type>[^/.]+)')
    def predict_by_type(self, request, model_type=None):
        """
        Predict using the best model of the specified type.
        Automatically selects the model with highest R² score.
        """
        # Find best model of this type by R² score
        best_model = (MLEngine.objects
                     .filter(model_type=model_type, r_squared__isnull=False)
                     .order_by('-r_squared', '-created_at')
                     .first())
        
        if not best_model:
            # Fallback to active or most recent model of this type
            best_model = (MLEngine.objects
                         .filter(model_type=model_type)
                         .filter(Q(is_active=True) | Q(is_active=False))
                         .order_by('-is_active', '-created_at')
                         .first())
        
        if not best_model:
            return Response({
                "error": f"No models found for type '{model_type}'"
            }, status=404)

        # Trigger prediction with the best model
        task = compute_price_prediction.delay(best_model.id, request.data)

        try:
            predicted_price = task.get(timeout=10)

            return Response({
                "engine_version": f"{best_model.name}-v{best_model.version}",
                "predicted_price": round(predicted_price, 6),
                "currency": "USD",
                "model_type": model_type,
                "model_name": best_model.name,
                "r_squared": best_model.r_squared,
                "mape": best_model.mape
            })

        except TimeoutError:
            return Response({"error": "Prediction timed out in the worker."}, status=504)
        except Exception as e:
            return Response({"error": f"Worker Error: {str(e)}"}, status=400)

    @extend_schema(
        summary="Predict Price using an Active Engine",
        description="Provide raw specs to get a price prediction from the 'Champion' model.",
        request=OpenApiTypes.OBJECT,
        examples=[
            OpenApiExample(
                'AWS EC2 Example',
                value={"vcpu": 4, "memory": 16, "region": "us-east-1", "os": "Linux"},
                request_only=True,
            )
        ],
        responses={200: OpenApiTypes.OBJECT}
    )
    @action(detail=False, methods=['post'], url_path='predict/(?P<engine_name>[^/.]+)')
    def predict(self, request, engine_name=None):
        # 1. Find the active engine
        engine = MLEngine.objects.filter(name=engine_name, is_active=True).first()
        if not engine:
            return Response({"error": "No active engine found."}, status=404)

        # 2. Trigger the Celery Task (Offload to worker container)
        task = compute_price_prediction.delay(engine.id, request.data)

        try:
            # 3. Wait for the result (e.g., up to 10 seconds)
            # This blocks the Django thread but keeps the 'statsmodels' requirement in the worker
            predicted_price = task.get(timeout=10)

            return Response({
                "engine_version": engine.version,
                "predicted_price": round(predicted_price, 6),
                "currency": "USD",
                "compute_node": "celery_worker" 
            })

        except TimeoutError:
            return Response({"error": "Prediction timed out in the worker."}, status=504)
        except Exception as e:
            return Response({"error": f"Worker Error: {str(e)}"}, status=400)