import joblib
import pandas as pd
import numpy as np
from rest_framework import viewsets, status, parsers
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Max, Q
from ..models import MLEngine
from .serializers import MLEngineSerializer, MLEngineSummarySerializer
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiTypes
from ..tasks import compute_price_prediction

class MLEngineViewSet(viewsets.ModelViewSet):
    queryset = MLEngine.objects.all()
    serializer_class = MLEngineSerializer
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    @extend_schema(
        summary="Register a New ML Model",
        description="""
        Register a new machine learning model for cloud pricing predictions.
        
        ## Request Format
        This endpoint accepts **multipart/form-data** to handle binary file uploads along with metadata.
        
        ## Required Fields
        
        ### Files (Binary Uploads)
        - **model_binary** (file, required): Pickled model file (.pkl) containing the trained ML model
          - Must be serialized with joblib or pickle
          - Model must implement a `predict()` method
          - For scaled models (Ridge, etc.), the scaler should be saved separately
        
        - **encoder_binary** (file, optional): Pickled encoder file (.pkl) for categorical features
          - Must be a scikit-learn OneHotEncoder or compatible encoder
          - Should match the encoder used during training
        
        - **scaler_binary** (file, optional): Pickled scaler file (.pkl) for feature scaling
          - Required for models like Ridge Regression that need standardized inputs
          - Must be a scikit-learn StandardScaler or compatible scaler
        
        ### Metadata Fields (Form Data)
        - **name** (string, required): Unique identifier for the model
          - Example: "AWS_Compute_Pricing", "AWS_Ridge_Pricing"
          - Used to identify the model's purpose
        
        - **model_type** (string, required): Algorithm category for automatic selection
          - Example: "Regression", "Classification", "TimeSeries"
          - Models of the same type compete; best R² is auto-selected
        
        - **version** (string, required): Version identifier
          - Format: "YYYY.MM.DD.NN" recommended
          - Example: "2025.12.20.01"
        
        - **feature_names** (JSON string, required): Ordered list of all feature column names
          - Must be a JSON-encoded array of strings
          - Example: '["const", "log_vcpu_count", "log_memory_gb", "region_us-east-1", ...]'
          - Order must match training data columns
          - Include "const" if your model uses an intercept term
        
        - **log_transformed_features** (JSON string, optional): Features that are log-transformed
          - JSON array of original feature names (before log transformation)
          - Example: '["vcpu_count", "memory_gb", "term_length_years"]'
          - System will apply np.log() during prediction
        
        - **categorical_features** (JSON string, optional): Categorical features to encode
          - JSON array of categorical column names
          - Example: '["provider", "region", "operating_system", "tenancy"]'
          - These will be one-hot encoded using the provided encoder
        
        - **r_squared** (float, optional): Model R² score (0.0 to 1.0)
          - Used for automatic model selection (higher is better)
          - Example: 0.9175
        
        - **mape** (float, required): Mean Absolute Percentage Error
          - Performance metric for model comparison
          - Example: 41.72 (represents 41.72%)
        
        - **rmse** (float, optional): Root Mean Squared Error
          - Additional performance metric
        
        - **training_sample_size** (integer, optional): Number of training samples
          - Example: 50000
        
        - **is_active** (boolean, required): Whether this is the active "Champion" model
          - Send as string: "true" or "false"
          - Only one model per name should be active
        
        - **metadata** (JSON string, optional): Additional model information
          - JSON object with any custom metadata
          - Example: '{"algorithm": "Ridge", "alpha": 1.0, "cv_folds": 5, "scaled": true}'
        
        ## Example Request (Python)
        ```python
        import requests
        import json
        import joblib
        
        # Save your trained model and encoder
        joblib.dump(trained_model, "model.pkl")
        joblib.dump(encoder, "encoder.pkl")
        joblib.dump(scaler, "scaler.pkl")  # Optional, for Ridge/scaled models
        
        # Prepare metadata
        payload = {
            "name": "AWS_Ridge_Pricing",
            "model_type": "Regression",
            "version": "2025.12.20.01",
            "feature_names": json.dumps(["const", "log_vcpu_count", "log_memory_gb", ...]),
            "log_transformed_features": json.dumps(["vcpu_count", "memory_gb"]),
            "categorical_features": json.dumps(["provider", "region", "operating_system"]),
            "r_squared": 0.9175,
            "mape": 41.72,
            "training_sample_size": 50000,
            "is_active": "true",
            "metadata": json.dumps({"algorithm": "Ridge", "alpha": 1.0})
        }
        
        # Upload files
        with open("model.pkl", "rb") as m, open("encoder.pkl", "rb") as e, open("scaler.pkl", "rb") as s:
            files = {
                "model_binary": ("model.pkl", m, "application/octet-stream"),
                "encoder_binary": ("encoder.pkl", e, "application/octet-stream"),
                "scaler_binary": ("scaler.pkl", s, "application/octet-stream")
            }
            response = requests.post("http://localhost/engines/", data=payload, files=files)
        ```
        
        ## Response (201 Created)
        Returns the full MLEngine object with all fields and auto-generated UUID.
        
        ## Important Notes
        - JSON fields must be sent as **JSON-encoded strings** in multipart form data
        - Model must predict log(price); system will exponentiate to get final price
        - Feature alignment is critical: prediction features must match `feature_names` exactly
        - For models requiring scaling (Ridge, etc.), include `scaler_binary` file
        - System auto-selects best model per type based on R² score
        """,
        responses={
            201: MLEngineSerializer,
            400: OpenApiTypes.OBJECT
        },
        examples=[
            OpenApiExample(
                'OLS Regression Example',
                value={
                    "name": "AWS_Compute_Pricing",
                    "model_type": "Regression",
                    "version": "2025.12.18.06",
                    "feature_names": '["const", "log_vcpu_count", "log_memory_gb"]',
                    "log_transformed_features": '["vcpu_count", "memory_gb"]',
                    "categorical_features": '["provider", "region", "operating_system"]',
                    "r_squared": 0.9175,
                    "mape": 41.72,
                    "is_active": "true"
                },
                request_only=True,
            ),
            OpenApiExample(
                'Ridge Regression Example (with Scaler)',
                value={
                    "name": "AWS_Ridge_Pricing",
                    "model_type": "Regression",
                    "version": "2025.12.20.01",
                    "feature_names": '["log_vcpu_count", "log_memory_gb", "region_us-east-1"]',
                    "log_transformed_features": '["vcpu_count", "memory_gb"]',
                    "categorical_features": '["region", "operating_system"]',
                    "r_squared": 0.9250,
                    "mape": 38.50,
                    "is_active": "true",
                    "metadata": '{"algorithm": "Ridge", "alpha": 1.0, "scaled": true}'
                },
                request_only=True,
            )
        ],
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        summary="List Models (Summary)",
        description=(
            "Returns all registered models without any binary file fields, "
            "exposing only identification and metrics for dashboards and comparisons."
        ),
        responses={200: MLEngineSummarySerializer(many=True)}
    )
    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request):
        engines = self.get_queryset()
        data = MLEngineSummarySerializer(engines, many=True).data
        return Response(data)

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