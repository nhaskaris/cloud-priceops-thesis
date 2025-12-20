import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_squared_error, mean_absolute_percentage_error, r2_score
import joblib
import json
import requests
import os

# =================================================================
# Ridge Regression Model for Cloud Pricing
# Uses L2 regularization to prevent overfitting
# =================================================================

FILE_NAME = "../hedonic/pricing_export_20251218163200_f7eccb5e-c03c-4b2a-8a4a-9c5b799edb91.csv"
API_URL = "http://localhost/engines/" 
TARGET_COL = 'effective_price_per_hour'

# Feature Configuration
LOG_CONTINUOUS_COLS = ['term_length_years', 'vcpu_count', 'memory_gb']

CATEGORICAL_COLS = [
    'provider', 'service', 'region', 'pricing_model', 'product_family',
    'instance_type', 'operating_system', 'tenancy', 'domain_label', 'currency'
]

BOOLEAN_COLS = ['is_all_upfront', 'is_partial_upfront', 'is_no_upfront']

IRRELEVANT_COLS = ['storage_type', 'price_unit', 'effective_date']

try:
    df = pd.read_csv(FILE_NAME)
    print(f"✅ Successfully loaded {len(df)} rows from {FILE_NAME}.\n")
except FileNotFoundError:
    print(f"❌ Error: File '{FILE_NAME}' not found.")
    exit()

# =================================================================
# STEP 1: Data Cleaning
# =================================================================
print("--- Starting Data Cleaning (Ridge Regression) ---")

# 1. Row-wise Missingness Check
threshold = 0.45
missing_pct = df.isnull().mean(axis=1)
initial_count = len(df)
df = df[missing_pct < threshold].copy()
print(f"Removed {initial_count - len(df)} rows with >45% missing columns.")

# 2. Vital Columns Check
vital_cols = ['product_family', 'instance_type', 'operating_system', 'vcpu_count', 'memory_gb']
pre_vital_count = len(df)
df = df.dropna(subset=vital_cols).copy()
print(f"Removed {pre_vital_count - len(df)} rows due to missing vital features.")

# 3. Filter non-positive prices
initial_rows = len(df)
df = df[df[TARGET_COL] > 0].copy()
print(f"Removed {initial_rows - len(df)} rows due to non-positive price.")

# 4. Remove extreme outliers (0.5th to 99.5th percentile)
q_low = df[TARGET_COL].quantile(0.005)
q_high = df[TARGET_COL].quantile(0.995)
initial_outliers = len(df)
df = df[(df[TARGET_COL] >= q_low) & (df[TARGET_COL] <= q_high)].copy()
print(f"Removed {initial_outliers - len(df)} extreme outlier rows.")

# 5. Fill remaining NaNs
df[CATEGORICAL_COLS] = df[CATEGORICAL_COLS].fillna('not_specified')
df[LOG_CONTINUOUS_COLS] = df[LOG_CONTINUOUS_COLS].fillna(0.0)
df[BOOLEAN_COLS] = df[BOOLEAN_COLS].fillna(0).astype(int)

# Drop irrelevant columns
df.drop(columns=IRRELEVANT_COLS, errors='ignore', inplace=True)

# =================================================================
# STEP 2: Transformation
# =================================================================
print("\n--- Starting Data Transformation ---")

# 1. Log Transform Target
df[f'log_{TARGET_COL}'] = np.log(df[TARGET_COL])

# 2. Log Transform Continuous Features
for col in LOG_CONTINUOUS_COLS:
    df[f'log_{col}'] = np.log(df[col].replace(0.0, 1e-6))

# 3. One-Hot Encoding
encoder = OneHotEncoder(sparse_output=False, handle_unknown='ignore')
encoded_features = encoder.fit_transform(df[CATEGORICAL_COLS])
encoded_df = pd.DataFrame(
    encoded_features,
    columns=encoder.get_feature_names_out(CATEGORICAL_COLS)
)

# Combine features
df.reset_index(drop=True, inplace=True)
encoded_df.reset_index(drop=True, inplace=True)

log_cols = [f'log_{col}' for col in LOG_CONTINUOUS_COLS]
X = pd.concat([df[log_cols], df[BOOLEAN_COLS], encoded_df], axis=1).dropna()
Y = df[f'log_{TARGET_COL}'].loc[X.index]

print(f"\nFinal Dataset Shape: {X.shape}")
print(f"Target Variable: log({TARGET_COL})")

# =================================================================
# STEP 3: Train-Test Split
# =================================================================
print("\n--- Splitting Data ---")

X_train, X_test, Y_train, Y_test = train_test_split(
    X, Y, test_size=0.2, random_state=42
)

print(f"Training Set: {X_train.shape}")
print(f"Test Set: {X_test.shape}")

# =================================================================
# STEP 4: Feature Scaling (Important for Ridge)
# =================================================================
print("\n--- Scaling Features ---")

scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

# Convert back to DataFrame to preserve column names
X_train_scaled = pd.DataFrame(X_train_scaled, columns=X_train.columns, index=X_train.index)
X_test_scaled = pd.DataFrame(X_test_scaled, columns=X_test.columns, index=X_test.index)

# =================================================================
# STEP 5: Hyperparameter Tuning with Cross-Validation
# =================================================================
print("\n--- Tuning Ridge Regression Hyperparameters ---")

# Define parameter grid
param_grid = {
    'alpha': [0.001, 0.01, 0.1, 1.0, 10.0, 100.0, 1000.0]
}

# Grid search with cross-validation
ridge_cv = GridSearchCV(
    Ridge(random_state=42),
    param_grid,
    cv=5,
    scoring='r2',
    n_jobs=-1,
    verbose=1
)

ridge_cv.fit(X_train_scaled, Y_train)

print(f"\nBest Alpha: {ridge_cv.best_params_['alpha']}")
print(f"Best CV R² Score: {ridge_cv.best_score_:.4f}")

# Use best model
model = ridge_cv.best_estimator_

# =================================================================
# STEP 6: Model Performance Metrics
# =================================================================
print("\n--- Model Performance Metrics ---")

# Predictions on test set
y_pred_log_train = model.predict(X_train_scaled)
y_pred_log_test = model.predict(X_test_scaled)

# Convert back to original scale
y_pred_train = np.exp(y_pred_log_train)
y_pred_test = np.exp(y_pred_log_test)
y_actual_train = df[TARGET_COL].loc[X_train.index]
y_actual_test = df[TARGET_COL].loc[X_test.index]

# Calculate metrics on test set
r_squared = r2_score(Y_test, y_pred_log_test)
mape = mean_absolute_percentage_error(y_actual_test, y_pred_test) * 100
rmse_log = np.sqrt(mean_squared_error(Y_test, y_pred_log_test))

print(f"Test R² Score: {r_squared:.4f}")
print(f"Test MAPE: {mape:.2f}%")
print(f"Test RMSE (Log Scale): {rmse_log:.4f}")

# Training metrics
r_squared_train = r2_score(Y_train, y_pred_log_train)
print(f"\nTraining R² Score: {r_squared_train:.4f}")
print(f"Overfitting Check: {abs(r_squared_train - r_squared):.4f} difference")

# =================================================================
# STEP 7: Visualization
# =================================================================
print("\n--- Generating Visualizations ---")

# 1. Predicted vs Actual (Test Set)
plt.figure(figsize=(10, 6))
plt.scatter(y_actual_test, y_pred_test, alpha=0.3, s=10)
plt.plot([y_actual_test.min(), y_actual_test.max()], 
         [y_actual_test.min(), y_actual_test.max()], 'r--', lw=2)
plt.xlabel('Actual Price ($/hour)')
plt.ylabel('Predicted Price ($/hour)')
plt.title('Ridge Regression: Actual vs Predicted Prices (Test Set)')
plt.tight_layout()
plt.savefig('predicted_vs_actual_ridge.png', dpi=150)
print("✅ Saved: predicted_vs_actual_ridge.png")

# 2. Residuals Plot
residuals = Y_test - y_pred_log_test
plt.figure(figsize=(10, 6))
plt.scatter(y_pred_log_test, residuals, alpha=0.3, s=10)
plt.axhline(y=0, color='r', linestyle='--')
plt.xlabel('Predicted Log(Price)')
plt.ylabel('Residuals')
plt.title('Ridge Regression: Residual Plot (Test Set)')
plt.tight_layout()
plt.savefig('residuals_ridge.png', dpi=150)
print("✅ Saved: residuals_ridge.png")

# 3. Feature Importance (Top 20 by absolute coefficient)
feature_importance = pd.DataFrame({
    'feature': X.columns,
    'coefficient': model.coef_
})
feature_importance['abs_coef'] = abs(feature_importance['coefficient'])
top_features = feature_importance.nlargest(20, 'abs_coef')

plt.figure(figsize=(12, 8))
plt.barh(top_features['feature'], top_features['coefficient'])
plt.xlabel('Coefficient Value')
plt.title('Ridge Regression: Top 20 Feature Coefficients')
plt.tight_layout()
plt.savefig('feature_importance_ridge.png', dpi=150)
print("✅ Saved: feature_importance_ridge.png")

# 4. Alpha Selection Plot
plt.figure(figsize=(10, 6))
cv_results = ridge_cv.cv_results_
plt.semilogx(param_grid['alpha'], cv_results['mean_test_score'], 'o-')
plt.xlabel('Alpha (Regularization Strength)')
plt.ylabel('Cross-Validation R² Score')
plt.title('Ridge Regression: Alpha Selection')
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig('alpha_selection_ridge.png', dpi=150)
print("✅ Saved: alpha_selection_ridge.png")

# =================================================================
# STEP 8: Register Model to Django API
# =================================================================
print("\n--- Registering Model to API ---")

# Save model and scaler separately (avoid wrapper issues with Celery)
model_filename = "ridge_model.pkl"
encoder_filename = "encoder_ridge.pkl"
scaler_filename = "scaler_ridge.pkl"

joblib.dump(model, model_filename)
joblib.dump(encoder, encoder_filename)
joblib.dump(scaler, scaler_filename)

# Prepare API Data
payload = {
    "name": "AWS_Ridge_Pricing",
    "model_type": "Regression",
    "version": "2025.12.20.01",
    "feature_names": json.dumps(list(X.columns)),
    "log_transformed_features": json.dumps(LOG_CONTINUOUS_COLS),
    "categorical_features": json.dumps(CATEGORICAL_COLS),
    "r_squared": float(r_squared),
    "mape": float(mape),
    "training_sample_size": int(len(X_train)),
    "is_active": "true",
    "metadata": json.dumps({
        "algorithm": "Ridge Regression",
        "alpha": float(ridge_cv.best_params_['alpha']),
        "cv_folds": 5,
        "test_size": 0.2,
        "scaled": True,
        "scaler_file": "scaler_ridge.pkl"
    })
}

# Send Multi-part POST request
try:
    with open(model_filename, "rb") as m_file, open(encoder_filename, "rb") as e_file, open(scaler_filename, "rb") as s_file:
        files = {
            "model_binary": (model_filename, m_file, 'application/octet-stream'),
            "encoder_binary": (encoder_filename, e_file, 'application/octet-stream'),
            "scaler_binary": (scaler_filename, s_file, 'application/octet-stream')
        }
        
        response = requests.post(API_URL, data=payload, files=files)

    if response.status_code == 201:
        print(f"✅ Ridge Regression model registered successfully!")
        print(f"   Model Name: {payload['name']}")
        print(f"   Version: {payload['version']}")
        print(f"   Model Type: {payload['model_type']}")
        print(f"   Test R²: {payload['r_squared']:.4f}")
        print(f"   Test MAPE: {payload['mape']:.2f}%")
        print(f"   Alpha: {ridge_cv.best_params_['alpha']}")
    else:
        print(f"❌ Error {response.status_code}: {response.text}")
except Exception as e:
    print(f"❌ Connection Error: {e}")

print("\n✅ Ridge Regression Model Training Complete!")
