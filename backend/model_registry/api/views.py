import joblib
import pandas as pd
import numpy as np
from rest_framework import viewsets, status, parsers
from rest_framework.decorators import action
from rest_framework.response import Response
from ..models import MLEngine
from .serializers import MLEngineSerializer
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiTypes
from ..tasks import compute_price_prediction

class MLEngineViewSet(viewsets.ModelViewSet):
    queryset = MLEngine.objects.all()
    serializer_class = MLEngineSerializer
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

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