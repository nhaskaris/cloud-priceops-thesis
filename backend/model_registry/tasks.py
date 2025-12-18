# engines/tasks.py
import joblib
import pandas as pd
import numpy as np
from celery import shared_task
from .models import MLEngine

@shared_task(name="compute_price_prediction")
def compute_price_prediction(engine_id, user_data):
    # 1. Load Engine from DB
    engine = MLEngine.objects.get(id=engine_id)
    
    # 2. Load Binaries (Celery container sees these via the shared 'media_data' volume)
    model = joblib.load(engine.model_binary.path)
    encoder = joblib.load(engine.encoder_binary.path) if engine.encoder_binary else None

    # 3. Prepare DataFrame
    input_df = pd.DataFrame([user_data])

    # 4. Log Transforms
    for col in engine.log_transformed_features:
        if col in input_df.columns:
            input_df[f'log_{col}'] = np.log(input_df[col].astype(float).replace(0, 1e-6))

    # 5. Encoding
    if encoder and engine.categorical_features:
        encoded_feat = encoder.transform(input_df[engine.categorical_features])
        encoded_df = pd.DataFrame(
            encoded_feat, 
            columns=encoder.get_feature_names_out(engine.categorical_features)
        )
        input_df = pd.concat([input_df, encoded_df], axis=1)

    # 6. Feature Alignment
    if 'const' in engine.feature_names:
        input_df['const'] = 1.0
    
    X_input = input_df[engine.feature_names]

    # 7. Math
    prediction = model.predict(X_input)[0]
    return float(np.exp(prediction))