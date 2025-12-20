import joblib
import pandas as pd
import numpy as np
import logging
from celery import shared_task
from .models import MLEngine

logger = logging.getLogger(__name__)

@shared_task(name="compute_price_prediction")
def compute_price_prediction(engine_id, user_data):
    """
    Worker task to perform ML inference.
    1. Loads the engine and binaries.
    2. Fills missing user data with defaults to avoid IndexErrors.
    3. Transforms continuous features to log scale.
    4. Encodes categorical features.
    5. Returns the exponentiated price.
    """
    try:
        # 1. Fetch Engine record
        engine = MLEngine.objects.get(id=engine_id)
        
        # 2. Load binaries from shared media volume
        # Note: The worker needs statsmodels/scikit-learn installed to unpickle these
        model = joblib.load(engine.model_binary.path)
        encoder = joblib.load(engine.encoder_binary.path) if engine.encoder_binary else None
        scaler = joblib.load(engine.scaler_binary.path) if engine.scaler_binary else None

        # 3. Initialize DataFrame with user input
        input_df = pd.DataFrame([user_data])

        # 4. Handle Categorical Columns (Alignment)
        # If user didn't provide a category, use 'not_specified' (matches training)
        for col in engine.categorical_features:
            if col not in input_df.columns:
                input_df[col] = 'not_specified'

        # 5. Handle Numerical / Log Columns
        # Ensure the columns exist, then apply log transform
        for col in engine.log_transformed_features:
            if col not in input_df.columns:
                input_df[col] = 0.0
            
            # Apply log(x) handling 0 with epsilon to avoid -inf
            input_df[f'log_{col}'] = np.log(input_df[col].astype(float).replace(0, 1e-6))

        # 6. Handle Boolean Columns
        # These were likely used in Step 3 of your training script
        boolean_cols = ['is_all_upfront', 'is_partial_upfront', 'is_no_upfront']
        for col in boolean_cols:
            if col not in input_df.columns:
                input_df[col] = 0
            else:
                # Convert True/'true'/1 to 1, else 0
                val = input_df[col].iloc[0]
                input_df[col] = 1 if str(val).lower() in ['true', '1', 'yes'] else 0

        # 7. Apply One-Hot Encoding
        if encoder and engine.categorical_features:
            encoded_feat = encoder.transform(input_df[engine.categorical_features])
            encoded_df = pd.DataFrame(
                encoded_feat, 
                columns=encoder.get_feature_names_out(engine.categorical_features)
            )
            # Merge original DF (with logs/booleans) with the new one-hot columns
            input_df = pd.concat([input_df, encoded_df], axis=1)

        # 8. Add Constant if the model expects it
        if 'const' in engine.feature_names:
            input_df['const'] = 1.0

        # 9. Final Feature Alignment
        # This reorders columns and selects ONLY what the model was trained on
        try:
            X_input = input_df[engine.feature_names]
        except KeyError as e:
            missing = list(set(engine.feature_names) - set(input_df.columns))
            logger.error(f"Missing features after alignment: {missing}")
            raise ValueError(f"Feature alignment failed. Missing: {missing}")

        # 10. Apply scaling if model requires it (Ridge, etc.)
        if scaler:
            X_input = pd.DataFrame(
                scaler.transform(X_input),
                columns=X_input.columns,
                index=X_input.index
            )

        # 11. Predict and Convert from Log-Price to Real-Price
        prediction_log = model.predict(X_input)[0]
        final_price = np.exp(prediction_log)

        return float(final_price)

    except MLEngine.DoesNotExist:
        logger.error(f"Engine ID {engine_id} not found.")
        raise
    except Exception as e:
        logger.error(f"Prediction Error: {str(e)}")
        raise