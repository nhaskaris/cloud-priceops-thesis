import joblib
import pandas as pd
import numpy as np
from rest_framework import viewsets, status, parsers
from rest_framework.decorators import action
from rest_framework.response import Response
from ..models import MLEngine
from .serializers import MLEngineSerializer
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiTypes

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
        """
        Translates raw user specs into a prediction using the 'Active' model.
        URL Example: /api/engines/predict/AWS_Compute_Pricing/
        """
        # 1. Get the current Champion
        engine = MLEngine.objects.filter(name=engine_name, is_active=True).first()
        if not engine:
            return Response({"error": "No active engine found with this name."}, status=404)

        try:
            # 2. Load binaries from storage
            model = joblib.load(engine.model_binary.path)
            encoder = joblib.load(engine.encoder_binary.path) if engine.encoder_binary else None

            # 3. Prepare Input Data
            user_data = request.data  # e.g., {"vcpu": 4, "memory": 16, "os": "Linux"}
            input_df = pd.DataFrame([user_data])

            # 4. Apply Log Transformations
            for col in engine.log_transformed_features:
                if col in input_df.columns:
                    input_df[f'log_{col}'] = np.log(input_df[col].astype(float).replace(0, 1e-6))

            # 5. Apply Encoding
            if encoder and engine.categorical_features:
                encoded_feat = encoder.transform(input_df[engine.categorical_features])
                encoded_df = pd.DataFrame(
                    encoded_feat, 
                    columns=encoder.get_feature_names_out(engine.categorical_features)
                )
                # Combine
                input_df = pd.concat([input_df, encoded_df], axis=1)

            # 6. Align with Training Features
            # Ensure 'const' exists if it's in feature_names
            if 'const' in engine.feature_names:
                input_df['const'] = 1.0

            # Filter and reorder columns to match exactly what the model expects
            X_input = input_df[engine.feature_names]

            # 7. Predict
            prediction = model.predict(X_input)[0]
            
            # If it was a Log-Log Hedonic model, convert back from log
            final_price = np.exp(prediction)

            return Response({
                "engine_version": engine.version,
                "predicted_price": round(float(final_price), 6),
                "currency": "USD"
            })

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)