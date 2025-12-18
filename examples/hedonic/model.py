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

# =================================================================
# STEP 0: Instructions and File Setup
# =================================================================

FILE_NAME = "pricing_export_20251218112136_5a97d0d9-bd2b-4870-b2c7-54a703886034.csv"
TARGET_COL = 'Effective Price Per Hour'

# Define columns by type
LOG_CONTINUOUS_COLS = ['Term Length Years', 'Vcpu Count', 'Memory Gb']
CATEGORICAL_COLS = [
    'Provider', 'Service', 'Region', 'Pricing Model', 'Product Family',
    'Instance Type', 'Operating System', 'Tenancy', 'Domain Label', 'Currency'
]
BOOLEAN_COLS = ['Is All Upfront', 'Is Partial Upfront', 'Is No Upfront']
IRRELEVANT_COLS = ['Storage Type', 'Price Unit', 'Effective Date']

try:
    df = pd.read_csv(FILE_NAME)
    print(f"Successfully loaded {len(df)} rows from {FILE_NAME}.\n")
except FileNotFoundError:
    print(f"Error: File '{FILE_NAME}' not found.")
    exit()

# =================================================================
# STEP 1: Data Cleaning (Updated with Vital Columns Check)
# =================================================================
print("--- Starting Data Cleaning ---")

# 1. Row-wise Missingness Check (50% threshold)
threshold = 0.5
missing_pct = df.isnull().mean(axis=1)
initial_count = len(df)
df = df[missing_pct < threshold].copy()
print(f"Removed {initial_count - len(df)} rows with >50% missing columns.")

# 2. ΑΥΣΤΗΡΟΣ ΕΛΕΓΧΟΣ: Αφαίρεση αν λείπουν τα βασικά χαρακτηριστικά
vital_cols = ['Product Family', 'Instance Type', 'Operating System', 'Vcpu Count', 'Memory Gb']
pre_vital_count = len(df)
# Αφαιρούμε τις γραμμές όπου οποιοδήποτε από τα vital_cols είναι NaN
df = df.dropna(subset=vital_cols).copy()
print(f"Removed {pre_vital_count - len(df)} rows due to missing vital features (CPU, RAM, OS, etc.).")

# 3. Filter non-positive prices
initial_rows = len(df)
df = df[df[TARGET_COL] > 0].copy()
print(f"Removed {initial_rows - len(df)} rows due to non-positive price.")

# 4. Fill remaining NaNs for other columns
df[CATEGORICAL_COLS] = df[CATEGORICAL_COLS].fillna('not_specified')
df[LOG_CONTINUOUS_COLS] = df[LOG_CONTINUOUS_COLS].fillna(0.0)
df[BOOLEAN_COLS] = df[BOOLEAN_COLS].fillna(0).astype(int)

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
# STEP 5: Econometric Diagnostics & Visualization
# =================================================================
print("\n--- Running Model Diagnostics ---")

# 1. VIF Check
vif_data = pd.DataFrame()
vif_data["feature"] = X_ols.columns
vif_data["VIF"] = [variance_inflation_factor(X_ols.values, i) for i in range(len(X_ols.columns))]
print("\nTop 10 VIF Scores (VIF > 10 indicates high multicollinearity):")
print(vif_data.sort_values(by="VIF", ascending=False).head(10))

# 2. Breusch-Pagan Test
bp_test = het_breuschpagan(model.resid, model.model.exog)
print(f"\nBreusch-Pagan p-value: {bp_test[1]:.4f}")

# 3. Accuracy Metric (MAPE)
mape = np.mean(np.abs((np.exp(Y_final) - np.exp(model.fittedvalues)) / np.exp(Y_final))) * 100
print(f"Mean Absolute Percentage Error (MAPE): {mape:.2f}%")

# 4. Plots
plt.figure(figsize=(18, 5))

plt.subplot(1, 3, 1)
sns.residplot(x=model.fittedvalues, y=model.resid, lowess=True, line_kws={'color': 'red'})
plt.title('Residuals vs Fitted')
plt.xlabel('Fitted Values (log_Price)')
plt.ylabel('Residuals')

plt.subplot(1, 3, 2)
sm.qqplot(model.resid, line='45', ax=plt.gca())
plt.title('Normal Q-Q Plot')

plt.subplot(1, 3, 3)
plt.scatter(Y_final, model.fittedvalues, alpha=0.3)
plt.plot([Y_final.min(), Y_final.max()], [Y_final.min(), Y_final.max()], 'r--')
plt.title('Predicted vs Actual (Log Scale)')
plt.xlabel('Actual log_Price')
plt.ylabel('Predicted log_Price')

plt.tight_layout()
plt.savefig('model_diagnostics.png')
plt.show()

import os
import joblib
import json
import requests

# =================================================================
# STEP 6: Save Model and Encoder Binaries
# =================================================================
API_URL = "http://10.100.106.82/engines/" 

# Ensure these lists are converted to JSON STRINGS 
# because multipart/form-data only accepts strings and files
payload = {
    "name": "AWS_Compute_Pricing",
    "model_type": "Hedonic_Regression",
    "version": "2025.12.18.04",
    "feature_names": json.dumps(list(X_ols.columns)),
    "log_transformed_features": json.dumps(LOG_CONTINUOUS_COLS),
    "categorical_features": json.dumps(CATEGORICAL_COLS),
    "r_squared": float(model.rsquared),
    "mape": float(mape),
    "training_sample_size": int(model.nobs),
    "is_active": "true"
}

files = {
    "model_binary": open("hedonic_model.pkl", "rb"),
    "encoder_binary": open("encoder.pkl", "rb")
}

# Run the request
response = requests.post(API_URL, data=payload, files=files)

if response.status_code == 201:
    print("✅ Model registered successfully!")
else:
    print(f"❌ Error {response.status_code}: {response.text}")