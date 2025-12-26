import { Link } from 'react-router-dom'

export default function Documentation() {
  return (
    <div style={{ maxWidth: 1000, margin: '0 auto', paddingBottom: '3rem' }}>
      {/* Header */}
      <div className="page-header">
        <div className="page-header-breadcrumb">
          <svg width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
            <path d="M1 2.828c.885-.37 2.154-.769 3.388-.893 1.33-.134 2.458.063 3.112.752v9.746c-.935-.53-2.12-.603-3.213-.493-1.18.12-2.37.461-3.287.811V2.828zm7.5-.141c.654-.689 1.782-.886 3.112-.752 1.234.124 2.503.523 3.388.893v9.923c-.918-.35-2.107-.692-3.287-.81-1.094-.111-2.278-.039-3.213.492V2.687zM8 1.783C7.015.936 5.587.81 4.287.94c-1.514.153-3.042.672-3.994 1.105A.5.5 0 0 0 0 2.5v11a.5.5 0 0 0 .707.455c.882-.4 2.303-.881 3.68-1.02 1.409-.142 2.59.087 3.223.877a.5.5 0 0 0 .78 0c.633-.79 1.814-1.019 3.222-.877 1.378.139 2.8.62 3.681 1.02A.5.5 0 0 0 16 13.5v-11a.5.5 0 0 0-.293-.455c-.952-.433-2.48-.952-3.994-1.105C10.413.809 8.985.936 8 1.783z"/>
          </svg>
          Resources / Docs
        </div>
        <h1 className="page-header-title">Documentation</h1>
        <p className="page-header-subtitle">Complete guide for predictions, API usage, model training, and troubleshooting.</p>
      </div>

      {/* Table of Contents */}
      <div style={{ background: '#1e293b', padding: '1.5rem', borderRadius: 8, marginBottom: '2rem', border: '1px solid #334155' }} className="animate-slide-up animate-delay-1">
        <h3 style={{ color: '#f1f5f9', marginTop: 0, marginBottom: '1rem' }}>Table of Contents</h3>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
          <a href="#getting-predictions" style={{ color: '#60a5fa', textDecoration: 'none' }}>→ Getting Price Predictions</a>
          <a href="#api-usage" style={{ color: '#60a5fa', textDecoration: 'none' }}>→ API Usage</a>
          <a href="#exporting-data" style={{ color: '#60a5fa', textDecoration: 'none' }}>→ Exporting Training Data</a>
          <a href="#training-model" style={{ color: '#60a5fa', textDecoration: 'none' }}>→ Training Your Model</a>
          <a href="#registering-model" style={{ color: '#60a5fa', textDecoration: 'none' }}>→ Registering via UI</a>
          <a href="#example-code" style={{ color: '#60a5fa', textDecoration: 'none' }}>→ Complete Example</a>
          <a href="#troubleshooting" style={{ color: '#60a5fa', textDecoration: 'none' }}>→ Troubleshooting</a>
        </div>
      </div>

      {/* Section 1: Getting Predictions */}
      <section id="getting-predictions" style={{ marginBottom: '3rem' }}>
        <h3 style={{ color: '#f1f5f9', fontSize: '1.5rem', borderBottom: '2px solid #334155', paddingBottom: '0.5rem', marginBottom: '1rem' }}>
          Getting Price Predictions
        </h3>
        
        <div style={{ background: '#1e293b', padding: '1.5rem', borderRadius: 8, marginBottom: '1.5rem', border: '1px solid #334155' }}>
          <h4 style={{ color: '#60a5fa', marginTop: 0 }}>Via Web Interface</h4>
          <ol style={{ color: '#cbd5e1', lineHeight: 1.8 }}>
            <li>Navigate to the <Link to="/predict" style={{ color: '#60a5fa' }}>Predict page</Link></li>
            <li>Enter required fields:
              <ul style={{ marginTop: '0.5rem', color: '#94a3b8' }}>
                <li><strong style={{ color: '#cbd5e1' }}>vCPU:</strong> Number of virtual CPUs (e.g., 4)</li>
                <li><strong style={{ color: '#cbd5e1' }}>Memory:</strong> RAM in GB (e.g., 16)</li>
              </ul>
            </li>
            <li>Optionally add:
              <ul style={{ marginTop: '0.5rem', color: '#94a3b8' }}>
                <li>Region (e.g., us-east-1)</li>
                <li>Operating System (Linux, Windows, RHEL, SUSE)</li>
                <li>Tenancy (shared, dedicated, host)</li>
                <li>Term Length in months (12, 36 for reserved instances)</li>
                <li>Payment options (all upfront, partial, no upfront)</li>
              </ul>
            </li>
            <li>Click "Get Price Prediction"</li>
            <li>View hourly, monthly, and yearly cost estimates</li>
          </ol>
        </div>

        <div style={{ background: '#1e293b', padding: '1.5rem', borderRadius: 8, border: '1px solid #334155' }}>
          <h4 style={{ color: '#60a5fa', marginTop: 0 }}>Example Values</h4>
          <div style={{ background: '#0f172a', padding: '1rem', borderRadius: 6, fontFamily: 'monospace', fontSize: '0.875rem' }}>
            <div style={{ color: '#cbd5e1', marginBottom: '0.5rem' }}>vCPU: <span style={{ color: '#60a5fa' }}>4</span></div>
            <div style={{ color: '#cbd5e1', marginBottom: '0.5rem' }}>Memory: <span style={{ color: '#60a5fa' }}>16</span> GB</div>
            <div style={{ color: '#cbd5e1', marginBottom: '0.5rem' }}>Region: <span style={{ color: '#60a5fa' }}>us-east-1</span></div>
            <div style={{ color: '#cbd5e1', marginBottom: '0.5rem' }}>OS: <span style={{ color: '#60a5fa' }}>Linux</span></div>
            <div style={{ color: '#cbd5e1' }}>Tenancy: <span style={{ color: '#60a5fa' }}>shared</span></div>
          </div>
        </div>
      </section>

      {/* Section 2: API Usage */}
      <section id="api-usage" style={{ marginBottom: '3rem' }}>
        <h3 style={{ color: '#f1f5f9', fontSize: '1.5rem', borderBottom: '2px solid #334155', paddingBottom: '0.5rem', marginBottom: '1rem' }}>
          API Usage
        </h3>
        
        <div style={{ background: '#1e293b', padding: '1.5rem', borderRadius: 8, marginBottom: '1.5rem', border: '1px solid #334155' }}>
          <h4 style={{ color: '#60a5fa', marginTop: 0 }}>Predict by Model Type</h4>
          <p style={{ color: '#cbd5e1', marginBottom: '1rem' }}>
            POST to <code style={{ background: '#0f172a', padding: '0.25rem 0.5rem', borderRadius: 4, color: '#60a5fa' }}>/engines/predict-by-type/Regression/</code>
          </p>
          <div style={{ background: '#0f172a', padding: '1rem', borderRadius: 6, overflow: 'auto' }}>
            <pre style={{ margin: 0, color: '#cbd5e1', fontSize: '0.875rem', lineHeight: 1.6 }}>
{`curl -X POST http://localhost:8000/engines/predict-by-type/Regression/ \\
  -H "Content-Type: application/json" \\
  -d '{
    "vcpu_count": 4,
    "memory_gb": 16,
    "region": "us-east-1",
    "operating_system": "Linux",
    "tenancy": "shared"
  }'`}
            </pre>
          </div>
        </div>

        <div style={{ background: '#1e293b', padding: '1.5rem', borderRadius: 8, border: '1px solid #334155' }}>
          <h4 style={{ color: '#60a5fa', marginTop: 0 }}>Response Example</h4>
          <div style={{ background: '#0f172a', padding: '1rem', borderRadius: 6, overflow: 'auto' }}>
            <pre style={{ margin: 0, color: '#cbd5e1', fontSize: '0.875rem', lineHeight: 1.6 }}>
{`{
  "engine_version": "AWS_Compute_Pricing-v2025.12.18.06",
  "predicted_price": 0.083200,
  "currency": "USD",
  "model_type": "Regression",
  "model_name": "AWS_Compute_Pricing",
  "r_squared": 0.9175,
  "mape": 41.72
}`}
            </pre>
          </div>
        </div>
      </section>

      {/* Section 2.5: Exporting Training Data */}
      <section id="exporting-data" style={{ marginBottom: '3rem' }}>
        <h3 style={{ color: '#f1f5f9', fontSize: '1.5rem', borderBottom: '2px solid #334155', paddingBottom: '0.5rem', marginBottom: '1rem' }}>
          Exporting Training Data
        </h3>
        
        <div style={{ background: '#1e293b', padding: '1.5rem', borderRadius: 8, marginBottom: '1.5rem', border: '1px solid #334155' }}>
          <h4 style={{ color: '#60a5fa', marginTop: 0 }}>Complete Model Creation Workflow</h4>
          <p style={{ color: '#cbd5e1', marginBottom: '1rem' }}>
            To train and register your own pricing model, follow this end-to-end flow:
          </p>
          <div style={{ background: '#0f172a', padding: '1.5rem', borderRadius: 8, marginBottom: '1rem' }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '1rem', marginBottom: '1.5rem' }}>
              <div style={{ background: 'linear-gradient(135deg, #3b82f6, #2563eb)', color: 'white', width: '2rem', height: '2rem', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, flexShrink: 0 }}>1</div>
              <div>
                <strong style={{ color: '#f1f5f9', display: 'block', marginBottom: '0.5rem' }}>Export Pricing Data from API</strong>
                <p style={{ color: '#94a3b8', margin: 0, fontSize: '0.875rem' }}>Use the export endpoint to get cleaned, model-ready data</p>
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '1rem', marginBottom: '1.5rem' }}>
              <div style={{ background: 'linear-gradient(135deg, #3b82f6, #2563eb)', color: 'white', width: '2rem', height: '2rem', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, flexShrink: 0 }}>2</div>
              <div>
                <strong style={{ color: '#f1f5f9', display: 'block', marginBottom: '0.5rem' }}>Train Your Model Locally</strong>
                <p style={{ color: '#94a3b8', margin: 0, fontSize: '0.875rem' }}>Apply feature engineering and train using scikit-learn or statsmodels</p>
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '1rem', marginBottom: '1.5rem' }}>
              <div style={{ background: 'linear-gradient(135deg, #3b82f6, #2563eb)', color: 'white', width: '2rem', height: '2rem', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, flexShrink: 0 }}>3</div>
              <div>
                <strong style={{ color: '#f1f5f9', display: 'block', marginBottom: '0.5rem' }}>Save Model Artifacts</strong>
                <p style={{ color: '#94a3b8', margin: 0, fontSize: '0.875rem' }}>Export model binary, encoder, and scaler using joblib</p>
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '1rem' }}>
              <div style={{ background: 'linear-gradient(135deg, #3b82f6, #2563eb)', color: 'white', width: '2rem', height: '2rem', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, flexShrink: 0 }}>4</div>
              <div>
                <strong style={{ color: '#f1f5f9', display: 'block', marginBottom: '0.5rem' }}>Register via UI or API</strong>
                <p style={{ color: '#94a3b8', margin: 0, fontSize: '0.875rem' }}>Upload model files with metadata to make it available for predictions</p>
              </div>
            </div>
          </div>
        </div>

        <div style={{ background: '#1e293b', padding: '1.5rem', borderRadius: 8, marginBottom: '1.5rem', border: '1px solid #334155' }}>
          <h4 style={{ color: '#60a5fa', marginTop: 0 }}>Step 1: Start Export Task</h4>
          <p style={{ color: '#cbd5e1', marginBottom: '1rem' }}>
            POST to <code style={{ background: '#0f172a', padding: '0.25rem 0.5rem', borderRadius: 4, color: '#60a5fa' }}>/pricing-data/export/</code> to start a background export task:
          </p>
          <div style={{ background: '#0f172a', padding: '1rem', borderRadius: 6, overflow: 'auto' }}>
            <pre style={{ margin: 0, color: '#cbd5e1', fontSize: '0.875rem', lineHeight: 1.6 }}>
{`curl -X POST http://localhost:8000/pricing-data/export/ \\
  -H "Content-Type: application/json" \\
  -d '{
    "provider": "AWS",
    "region": "us-east-1"
  }'

# Response:
{
  "task_id": "abc123-def456-789",
  "status": "PENDING",
  "message": "Export task started. Use /pricing-data/export-status/?task_id=... to check progress."
}`}
            </pre>
          </div>
          <p style={{ color: '#94a3b8', fontSize: '0.875rem', marginTop: '1rem', marginBottom: 0 }}>
            <strong style={{ color: '#f1f5f9' }}>Important:</strong> The export automatically excludes rows with missing critical features (vcpu_count, memory_gb, effective_price_per_hour) to ensure data quality for model training.
          </p>
        </div>

        <div style={{ background: '#1e293b', padding: '1.5rem', borderRadius: 8, marginBottom: '1.5rem', border: '1px solid #334155' }}>
          <h4 style={{ color: '#60a5fa', marginTop: 0 }}>Step 2: Check Status & Download</h4>
          <p style={{ color: '#cbd5e1', marginBottom: '1rem' }}>
            GET from <code style={{ background: '#0f172a', padding: '0.25rem 0.5rem', borderRadius: 4, color: '#60a5fa' }}>/pricing-data/export-status/?task_id=&lt;TASK_ID&gt;</code>
          </p>
          <div style={{ background: '#0f172a', padding: '1rem', borderRadius: 6, overflow: 'auto', marginBottom: '1rem' }}>
            <pre style={{ margin: 0, color: '#cbd5e1', fontSize: '0.875rem', lineHeight: 1.6 }}>
{`curl http://localhost:8000/pricing-data/export-status/?task_id=abc123-def456-789

# While processing:
{
  "status": "PENDING"
}

# When complete (auto-downloads CSV):
# HTTP 200 with CSV file download
# Filename: pricing_export_20251227120000_abc123.csv`}
            </pre>
          </div>
          <p style={{ color: '#94a3b8', fontSize: '0.875rem', margin: 0 }}>
            When status is <span style={{ color: '#60a5fa', fontWeight: 600 }}>SUCCESS</span>, the endpoint automatically serves the CSV file for download. The file is cleaned and ready for model training.
          </p>
        </div>

        <div style={{ background: '#1e293b', padding: '1.5rem', borderRadius: 8, border: '1px solid #334155' }}>
          <h4 style={{ color: '#60a5fa', marginTop: 0 }}>Exported Data Structure</h4>
          <p style={{ color: '#cbd5e1', marginBottom: '1rem' }}>The exported CSV includes these columns:</p>
          <div style={{ background: '#0f172a', padding: '1rem', borderRadius: 6 }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '0.5rem', fontSize: '0.875rem' }}>
              <div style={{ color: '#60a5fa', fontWeight: 600 }}>Target Variable:</div>
              <div style={{ color: '#cbd5e1' }}>effective_price_per_hour</div>
              
              <div style={{ color: '#60a5fa', fontWeight: 600 }}>Continuous Features:</div>
              <div style={{ color: '#cbd5e1' }}>vcpu_count, memory_gb, term_length_years</div>
              
              <div style={{ color: '#60a5fa', fontWeight: 600 }}>Categorical Features:</div>
              <div style={{ color: '#cbd5e1' }}>provider, region, operating_system, tenancy, instance_type</div>
              
              <div style={{ color: '#60a5fa', fontWeight: 600 }}>Boolean Features:</div>
              <div style={{ color: '#cbd5e1' }}>is_all_upfront, is_partial_upfront, is_no_upfront</div>
            </div>
          </div>
        </div>
      </section>

      {/* Section 3: Training Your Model */}
      <section id="training-model" style={{ marginBottom: '3rem' }}>
        <h3 style={{ color: '#f1f5f9', fontSize: '1.5rem', borderBottom: '2px solid #334155', paddingBottom: '0.5rem', marginBottom: '1rem' }}>
          Training Your Model
        </h3>

        <div style={{ background: '#1e293b', padding: '1.5rem', borderRadius: 8, marginBottom: '1.5rem', border: '1px solid #334155' }}>
          <h4 style={{ color: '#60a5fa', marginTop: 0 }}>Step 1: Prepare Your Data</h4>
          <p style={{ color: '#cbd5e1', marginBottom: '1rem' }}>
            Use the exported CSV from the <a href="#exporting-data" style={{ color: '#60a5fa' }}>data export endpoint</a> or prepare your own dataset. Required columns:
          </p>
          <ul style={{ color: '#cbd5e1', lineHeight: 1.8 }}>
            <li><strong style={{ color: '#f1f5f9' }}>Target:</strong> effective_price_per_hour</li>
            <li><strong style={{ color: '#f1f5f9' }}>Continuous:</strong> vcpu_count, memory_gb, term_length_years</li>
            <li><strong style={{ color: '#f1f5f9' }}>Categorical:</strong> provider, region, operating_system, tenancy, etc.</li>
            <li><strong style={{ color: '#f1f5f9' }}>Boolean:</strong> is_all_upfront, is_partial_upfront, is_no_upfront</li>
          </ul>
          <div style={{ background: '#0f172a', padding: '1rem', borderRadius: 6, marginTop: '1rem' }}>
            <pre style={{ margin: 0, color: '#cbd5e1', fontSize: '0.875rem', lineHeight: 1.6 }}>
{`# Load exported data
import pandas as pd
df = pd.read_csv('pricing_export_20251227120000_abc123.csv')

# Verify data quality
print(f"Total rows: {len(df)}")
print(f"Missing values:\\n{df.isnull().sum()}")

# Check price distribution
min_price = df['effective_price_per_hour'].min()
max_price = df['effective_price_per_hour'].max()
print(f"Price range: {min_price:.4f} - {max_price:.4f} USD/hour")`}
            </pre>
          </div>
        </div>

        <div style={{ background: '#1e293b', padding: '1.5rem', borderRadius: 8, marginBottom: '1.5rem', border: '1px solid #334155' }}>
          <h4 style={{ color: '#60a5fa', marginTop: 0 }}>Step 2: Transform Features</h4>
          <div style={{ background: '#0f172a', padding: '1rem', borderRadius: 6, overflow: 'auto', marginBottom: '1rem' }}>
            <pre style={{ margin: 0, color: '#cbd5e1', fontSize: '0.875rem', lineHeight: 1.6 }}>
{`import numpy as np
from sklearn.preprocessing import OneHotEncoder

# Log transform continuous features
LOG_CONTINUOUS_COLS = ['vcpu_count', 'memory_gb', 'term_length_years']
for col in LOG_CONTINUOUS_COLS:
    df[f'log_{col}'] = np.log(df[col].replace(0.0, 1e-6))

# Log transform target
df['log_effective_price_per_hour'] = np.log(df['effective_price_per_hour'])

# One-hot encode categorical features
CATEGORICAL_COLS = ['provider', 'region', 'operating_system', 'tenancy']
encoder = OneHotEncoder(sparse_output=False, handle_unknown='ignore')
encoded_features = encoder.fit_transform(df[CATEGORICAL_COLS])`}
            </pre>
          </div>
          <p style={{ color: '#94a3b8', fontSize: '0.875rem', margin: 0 }}>
            Note: Log transformation is crucial for handling price ranges that span multiple orders of magnitude
          </p>
        </div>

        <div style={{ background: '#1e293b', padding: '1.5rem', borderRadius: 8, border: '1px solid #334155' }}>
          <h4 style={{ color: '#60a5fa', marginTop: 0 }}>Step 3: Train Model</h4>
          <div style={{ background: '#0f172a', padding: '1rem', borderRadius: 6, overflow: 'auto', marginBottom: '1rem' }}>
            <pre style={{ margin: 0, color: '#cbd5e1', fontSize: '0.875rem', lineHeight: 1.6 }}>
{`import statsmodels.api as sm
import joblib

# Combine features
X = pd.concat([log_features, boolean_features, encoded_features], axis=1)
Y = df['log_effective_price_per_hour']

# Add constant term
X_with_const = sm.add_constant(X)

# Train OLS model
model = sm.OLS(Y, X_with_const).fit()

# Calculate metrics
r_squared = model.rsquared
predictions = np.exp(model.predict(X_with_const))  # Exponentiate back
actual = np.exp(Y)
mape = np.mean(np.abs((actual - predictions) / actual)) * 100

# Save model and encoder
joblib.dump(model, "hedonic_model.pkl")
joblib.dump(encoder, "encoder.pkl")

print(f"R²: {r_squared:.4f}, MAPE: {mape:.2f}%")`}
            </pre>
          </div>
        </div>
      </section>

      {/* Section 4: Registering Model */}
      <section id="registering-model" style={{ marginBottom: '3rem' }}>
        <h3 style={{ color: '#f1f5f9', fontSize: '1.5rem', borderBottom: '2px solid #334155', paddingBottom: '0.5rem', marginBottom: '1rem' }}>
          Registering Your Model
        </h3>

        <div style={{ background: '#1e293b', padding: '1.5rem', borderRadius: 8, marginBottom: '1.5rem', border: '1px solid #334155' }}>
          <h4 style={{ color: '#60a5fa', marginTop: 0 }}>Option 1: Via Web Interface</h4>
          <ol style={{ color: '#cbd5e1', lineHeight: 1.8 }}>
            <li>Go to <Link to="/contribute" style={{ color: '#60a5fa' }}>Contribute page</Link></li>
            <li>Fill in <strong style={{ color: '#f1f5f9' }}>Basic Information</strong>:
              <ul style={{ marginTop: '0.5rem', color: '#94a3b8' }}>
                <li>Name: AWS_Compute_Pricing</li>
                <li>Model Type: Regression</li>
                <li>Version: 2025.12.26.01</li>
              </ul>
            </li>
            <li>Add <strong style={{ color: '#f1f5f9' }}>Performance Metrics</strong>:
              <ul style={{ marginTop: '0.5rem', color: '#94a3b8' }}>
                <li>R²: 0.9175</li>
                <li>MAPE: 41.72</li>
                <li>Training Samples: 50000</li>
              </ul>
            </li>
            <li>Configure <strong style={{ color: '#f1f5f9' }}>Features</strong> (JSON format):
              <ul style={{ marginTop: '0.5rem', color: '#94a3b8' }}>
                <li>feature_names: ["const", "log_vcpu_count", "log_memory_gb", ...]</li>
                <li>log_transformed_features: ["vcpu_count", "memory_gb"]</li>
                <li>categorical_features: ["provider", "region", "operating_system"]</li>
              </ul>
            </li>
            <li>Upload <strong style={{ color: '#f1f5f9' }}>Model Files</strong>:
              <ul style={{ marginTop: '0.5rem', color: '#94a3b8' }}>
                <li>model_binary.pkl (required)</li>
                <li>encoder_binary.pkl (optional)</li>
                <li>scaler_binary.pkl (optional, for Ridge/scaled models)</li>
              </ul>
            </li>
            <li>Click "Register Model"</li>
          </ol>
        </div>

        <div style={{ background: '#1e293b', padding: '1.5rem', borderRadius: 8, border: '1px solid #334155' }}>
          <h4 style={{ color: '#60a5fa', marginTop: 0 }}>Option 2: Via API (Python)</h4>
          <div style={{ background: '#0f172a', padding: '1rem', borderRadius: 6, overflow: 'auto' }}>
            <pre style={{ margin: 0, color: '#cbd5e1', fontSize: '0.875rem', lineHeight: 1.6 }}>
{`import requests
import json
import joblib

# Prepare payload
payload = {
    "name": "AWS_Compute_Pricing",
    "model_type": "Regression",
    "version": "2025.12.26.01",
    "feature_names": json.dumps(["const", "log_vcpu_count", "log_memory_gb"]),
    "log_transformed_features": json.dumps(["vcpu_count", "memory_gb"]),
    "categorical_features": json.dumps(["provider", "region", "operating_system"]),
    "r_squared": 0.9175,
    "mape": 41.72,
    "training_sample_size": 50000,
    "is_active": "true"
}

# Upload files
with open("hedonic_model.pkl", "rb") as m, open("encoder.pkl", "rb") as e:
    files = {
        "model_binary": ("model.pkl", m, "application/octet-stream"),
        "encoder_binary": ("encoder.pkl", e, "application/octet-stream")
    }
    response = requests.post("http://localhost:8000/engines/", 
                           data=payload, files=files)

if response.status_code == 201:
    print("✅ Model registered successfully!")
else:
    print(f"❌ Error: {response.text}")`}
            </pre>
          </div>
        </div>
      </section>

      {/* Section 5: Example Code */}
      <section id="example-code" style={{ marginBottom: '3rem' }}>
        <h3 style={{ color: '#f1f5f9', fontSize: '1.5rem', borderBottom: '2px solid #334155', paddingBottom: '0.5rem', marginBottom: '1rem' }}>
          Complete Example
        </h3>

        <div style={{ background: '#1e293b', padding: '1.5rem', borderRadius: 8, border: '1px solid #334155' }}>
          <h4 style={{ color: '#60a5fa', marginTop: 0 }}>Hedonic Regression Example</h4>
          <p style={{ color: '#cbd5e1', marginBottom: '1rem' }}>
            Full working example from <code style={{ background: '#0f172a', padding: '0.25rem 0.5rem', borderRadius: 4, color: '#60a5fa' }}>examples/hedonic/model.py</code>
          </p>
          <div style={{ background: '#0f172a', padding: '1rem', borderRadius: 6, overflow: 'auto' }}>
            <pre style={{ margin: 0, color: '#cbd5e1', fontSize: '0.75rem', lineHeight: 1.6 }}>
{`# Load and clean data
df = pd.read_csv("pricing_export.csv")
df = df[df['effective_price_per_hour'] > 0].copy()

# Define feature categories
LOG_CONTINUOUS_COLS = ['term_length_years', 'vcpu_count', 'memory_gb']
CATEGORICAL_COLS = ['provider', 'region', 'operating_system', 'tenancy']
BOOLEAN_COLS = ['is_all_upfront', 'is_partial_upfront', 'is_no_upfront']

# Transform features
for col in LOG_CONTINUOUS_COLS:
    df[f'log_{col}'] = np.log(df[col].replace(0.0, 1e-6))

df['log_effective_price_per_hour'] = np.log(df['effective_price_per_hour'])

encoder = OneHotEncoder(sparse_output=False, handle_unknown='ignore')
encoded = encoder.fit_transform(df[CATEGORICAL_COLS])

# Build feature matrix
X = pd.concat([
    df[[f'log_{c}' for c in LOG_CONTINUOUS_COLS]],
    df[BOOLEAN_COLS],
    pd.DataFrame(encoded, columns=encoder.get_feature_names_out())
], axis=1)

Y = df['log_effective_price_per_hour']
X_with_const = sm.add_constant(X)

# Train and evaluate
model = sm.OLS(Y, X_with_const).fit()
print(f"R²: {model.rsquared:.4f}")

# Save
joblib.dump(model, "hedonic_model.pkl")
joblib.dump(encoder, "encoder.pkl")`}
            </pre>
          </div>
          <div style={{ marginTop: '1rem', padding: '1rem', background: '#0f4c81', borderRadius: 6, borderLeft: '4px solid #60a5fa' }}>
            <p style={{ margin: 0, color: '#cbd5e1', fontSize: '0.875rem' }}>
              Find the complete example with comments in the <code style={{ color: '#93c5fd' }}>examples/hedonic/</code> directory
            </p>
          </div>
        </div>
      </section>

      {/* Section 6: Troubleshooting */}
      <section id="troubleshooting" style={{ marginBottom: '3rem' }}>
        <h3 style={{ color: '#f1f5f9', fontSize: '1.5rem', borderBottom: '2px solid #334155', paddingBottom: '0.5rem', marginBottom: '1rem' }}>
          Troubleshooting
        </h3>

        <div style={{ background: '#1e293b', padding: '1.5rem', borderRadius: 8, marginBottom: '1rem', border: '1px solid #334155' }}>
          <h4 style={{ color: '#fca5a5', marginTop: 0 }}>JSON Validation Errors</h4>
          <p style={{ color: '#cbd5e1', marginBottom: '0.5rem' }}>
            Ensure JSON fields are valid arrays/objects:
          </p>
          <div style={{ background: '#0f172a', padding: '1rem', borderRadius: 6 }}>
            <div style={{ color: '#cbd5e1', fontSize: '0.875rem', marginBottom: '0.5rem' }}>
              <span style={{ color: '#60a5fa', fontWeight: 600 }}>Correct:</span> <code style={{ color: '#60a5fa' }}>["vcpu_count", "memory_gb"]</code>
            </div>
            <div style={{ color: '#cbd5e1', fontSize: '0.875rem' }}>
              <span style={{ color: '#fca5a5', fontWeight: 600 }}>Wrong:</span> <code style={{ color: '#fca5a5' }}>vcpu_count, memory_gb</code>
            </div>
          </div>
        </div>

        <div style={{ background: '#1e293b', padding: '1.5rem', borderRadius: 8, marginBottom: '1rem', border: '1px solid #334155' }}>
          <h4 style={{ color: '#fca5a5', marginTop: 0 }}>Feature Mismatch Errors</h4>
          <p style={{ color: '#cbd5e1' }}>
            Feature names must match exactly between training and prediction. Include "const" if you used <code style={{ background: '#0f172a', padding: '0.25rem 0.5rem', borderRadius: 4, color: '#60a5fa' }}>sm.add_constant()</code>
          </p>
        </div>

        <div style={{ background: '#1e293b', padding: '1.5rem', borderRadius: 8, border: '1px solid #334155' }}>
          <h4 style={{ color: '#fca5a5', marginTop: 0 }}>Model Not Predicting</h4>
          <p style={{ color: '#cbd5e1', marginBottom: '0.5rem' }}>
            Check that:
          </p>
          <ul style={{ color: '#cbd5e1', lineHeight: 1.8 }}>
            <li>Model is marked as "Active"</li>
            <li>Input features match model's expected format</li>
            <li>Categorical values were seen during training (encoder handles unknown)</li>
            <li>Continuous values are positive (log transform requires &gt; 0)</li>
          </ul>
        </div>
      </section>

      {/* Quick Links */}
      <div style={{ background: '#1e293b', padding: '2rem', borderRadius: 8, border: '1px solid #334155', textAlign: 'center' }}>
        <h3 style={{ color: '#f1f5f9', marginTop: 0 }}>Ready to Get Started?</h3>
        <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', marginTop: '1.5rem' }}>
          <Link to="/predict" className="btn-primary" style={{ padding: '0.75rem 1.5rem' }}>
            Start Predicting
          </Link>
          <Link to="/contribute" className="btn-secondary" style={{ padding: '0.75rem 1.5rem' }}>
            Contribute Model
          </Link>
          <Link to="/models" className="btn-secondary" style={{ padding: '0.75rem 1.5rem' }}>
            View Dashboard
          </Link>
        </div>
      </div>
    </div>
  )
}
