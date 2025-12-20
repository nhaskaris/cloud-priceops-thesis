import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.preprocessing import OneHotEncoder
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LassoCV
import statsmodels.api as sm
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.stats.diagnostic import het_breuschpagan
import joblib
import json
import requests
import os

# =================================================================
# STEP 0: Configuration and Column Setup (Snake Case)
# =================================================================

FILE_NAME = "pricing_export_20251218163200_f7eccb5e-c03c-4b2a-8a4a-9c5b799edb91.csv"
API_URL = "http://localhost/engines/" 
TARGET_COL = 'effective_price_per_hour'

# Define columns by type to match Django Serializer output
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
print("--- Starting Data Cleaning ---")

# 1. Row-wise Missingness Check (50% threshold)
threshold = 0.5
missing_pct = df.isnull().mean(axis=1)
initial_count = len(df)
df = df[missing_pct < threshold].copy()
print(f"Removed {initial_count - len(df)} rows with >50% missing columns.")

# 2. Vital Columns Check: Remove rows missing key prediction features
vital_cols = ['product_family', 'instance_type', 'operating_system', 'vcpu_count', 'memory_gb']
pre_vital_count = len(df)
df = df.dropna(subset=vital_cols).copy()
print(f"Removed {pre_vital_count - len(df)} rows due to missing vital features.")

# 3. Filter non-positive prices
initial_rows = len(df)
df = df[df[TARGET_COL] > 0].copy()
print(f"Removed {initial_rows - len(df)} rows due to non-positive price.")

# 4. Fill remaining NaNs and set types
df[CATEGORICAL_COLS] = df[CATEGORICAL_COLS].fillna('not_specified')
df[LOG_CONTINUOUS_COLS] = df[LOG_CONTINUOUS_COLS].fillna(0.0)
df[BOOLEAN_COLS] = df[BOOLEAN_COLS].fillna(0).astype(int)

# Drop irrelevant columns
df.drop(columns=IRRELEVANT_COLS, errors='ignore', inplace=True)

# =================================================================
# STEP 2: Transformation (Log and One-Hot Encoding)
# =================================================================
print("\n--- Starting Data Transformation ---")

# 1. Log Transform Target
df[f'log_{TARGET_COL}'] = np.log(df[TARGET_COL])

# 2. Log Transform Continuous Features (handling 0.0 with epsilon)
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

print(f"Final dataset size: {len(X)} rows with {len(X.columns)} features.")

# =================================================================
# STEP 3: Feature Selection (Lasso)
# =================================================================
print("\n--- Starting Feature Selection (Lasso) ---")

X_train, X_test, Y_train, Y_test = train_test_split(X, Y, test_size=0.2, random_state=42)
lasso = LassoCV(cv=5, random_state=42, max_iter=10000).fit(X_train, Y_train)
selected_features = X_train.columns[lasso.coef_ != 0].tolist()

print(f"Lasso selected {len(selected_features)} relevant features.")

# =================================================================
# STEP 4: Final Hedonic Model Training (OLS)
# =================================================================
print("\n--- Training Final Hedonic Model (OLS) ---")

X_final = X[selected_features].astype(np.float64)
Y_final = Y.astype(np.float64)
X_ols = sm.add_constant(X_final) 

# Use HC3 Robust Standard Errors for Heteroskedasticity
model = sm.OLS(Y_final, X_ols, hasconst=True).fit(cov_type='HC3')
print(model.summary())

# =================================================================
# STEP 5: Econometric Diagnostics
# =================================================================
print("\n--- Running Model Diagnostics ---")

# 1. Accuracy Metric (MAPE)
mape = np.mean(np.abs((np.exp(Y_final) - np.exp(model.fittedvalues)) / np.exp(Y_final))) * 100
print(f"Mean Absolute Percentage Error (MAPE): {mape:.2f}%")

# 2. VIF Check (Sample of top 10)
vif_data = pd.DataFrame()
vif_data["feature"] = X_ols.columns
vif_data["VIF"] = [variance_inflation_factor(X_ols.values, i) for i in range(len(X_ols.columns))]
print(vif_data.sort_values(by="VIF", ascending=False).head(10))

# 3. Save Visualizations
plt.figure(figsize=(12, 5))
plt.subplot(1, 2, 1)
plt.scatter(Y_final, model.fittedvalues, alpha=0.3)
plt.plot([Y_final.min(), Y_final.max()], [Y_final.min(), Y_final.max()], 'r--')
plt.title('Predicted vs Actual (Log Scale)')

plt.subplot(1, 2, 2)
sns.histplot(model.resid, kde=True)
plt.title('Residual Distribution')
plt.savefig('training_diagnostics.png')

# =================================================================
# STEP 6: Save Binaries and Register via API
# =================================================================
print("\n--- Registering Model with Django API ---")

# 1. Export local binaries
model_filename = "hedonic_model.pkl"
encoder_filename = "encoder.pkl"
joblib.dump(model, model_filename)
joblib.dump(encoder, encoder_filename)

# 2. Prepare API Data
payload = {
    "name": "AWS_Compute_Pricing",
    "model_type": "Hedonic_Regression",
    "version": "2025.12.18.06",
    "feature_names": json.dumps(list(X_ols.columns)),
    "log_transformed_features": json.dumps(LOG_CONTINUOUS_COLS),
    "categorical_features": json.dumps(CATEGORICAL_COLS),
    "r_squared": float(model.rsquared),
    "mape": float(mape),
    "training_sample_size": int(model.nobs),
    "is_active": "true"
}

# 3. Send Multi-part POST request
try:
    with open(model_filename, "rb") as m_file, open(encoder_filename, "rb") as e_file:
        files = {
            "model_binary": (model_filename, m_file, 'application/octet-stream'),
            "encoder_binary": (encoder_filename, e_file, 'application/octet-stream')
        }
        
        response = requests.post(API_URL, data=payload, files=files)

    if response.status_code == 201:
        print(f"✅ Model registered successfully! Version: {payload['version']}")
    else:
        print(f"❌ Error {response.status_code}: {response.text}")
except Exception as e:
    print(f"❌ Connection Error: {e}")