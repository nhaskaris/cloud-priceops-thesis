import { Link } from 'react-router-dom'
import { useState } from 'react'

export default function Documentation() {
  const [activeTab, setActiveTab] = useState<'users' | 'contributors'>('users')

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
        <p className="page-header-subtitle">Complete guide for predictions, API usage, model contributions, and troubleshooting.</p>
      </div>

      {/* Tab Navigation */}
      <div style={{ 
        display: 'flex', 
        gap: '1rem', 
        marginBottom: '2rem',
        borderBottom: '2px solid #334155'
      }} className="animate-slide-up animate-delay-1">
        <button
          onClick={() => setActiveTab('users')}
          style={{
            background: activeTab === 'users' ? 'linear-gradient(180deg, #3b82f6, #2563eb)' : 'transparent',
            color: activeTab === 'users' ? '#f1f5f9' : '#94a3b8',
            border: 'none',
            padding: '0.875rem 1.5rem',
            fontSize: '1rem',
            fontWeight: 600,
            cursor: 'pointer',
            borderRadius: '8px 8px 0 0',
            transition: 'all 0.2s ease',
            borderBottom: activeTab === 'users' ? '3px solid #3b82f6' : '3px solid transparent',
            marginBottom: '-2px'
          }}
        >
          For Users
        </button>
        <button
          onClick={() => setActiveTab('contributors')}
          style={{
            background: activeTab === 'contributors' ? 'linear-gradient(180deg, #3b82f6, #2563eb)' : 'transparent',
            color: activeTab === 'contributors' ? '#f1f5f9' : '#94a3b8',
            border: 'none',
            padding: '0.875rem 1.5rem',
            fontSize: '1rem',
            fontWeight: 600,
            cursor: 'pointer',
            borderRadius: '8px 8px 0 0',
            transition: 'all 0.2s ease',
            borderBottom: activeTab === 'contributors' ? '3px solid #3b82f6' : '3px solid transparent',
            marginBottom: '-2px'
          }}
        >
          For Contributors
        </button>
      </div>

      {/* User Documentation */}
      {activeTab === 'users' && (
        <div className="animate-fade-in">
          {/* Table of Contents */}
          <div style={{ background: '#1e293b', padding: '1.5rem', borderRadius: 8, marginBottom: '2rem', border: '1px solid #334155' }}>
            <h3 style={{ color: '#f1f5f9', marginTop: 0, marginBottom: '1rem' }}>User Guide Contents</h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
              <a href="#getting-predictions" style={{ color: '#60a5fa', textDecoration: 'none' }}>→ Getting Price Predictions</a>
              <a href="#api-usage" style={{ color: '#60a5fa', textDecoration: 'none' }}>→ API Usage</a>
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
                <li>Navigate to the <Link to="/analyze" style={{ color: '#60a5fa' }}>Analyze page</Link></li>
                <li>Choose a mode:
                  <ul style={{ marginTop: '0.5rem', color: '#94a3b8' }}>
                    <li><strong style={{ color: '#cbd5e1' }}>Cost Overview:</strong> Find cheaper alternatives to your current setup</li>
                    <li><strong style={{ color: '#cbd5e1' }}>Advanced Prediction:</strong> Get detailed predictions with full control over parameters</li>
                  </ul>
                </li>
                <li>Enter required fields:
                  <ul style={{ marginTop: '0.5rem', color: '#94a3b8' }}>
                    <li><strong style={{ color: '#cbd5e1' }}>vCPU:</strong> Number of virtual CPUs (e.g., 4)</li>
                    <li><strong style={{ color: '#cbd5e1' }}>Memory:</strong> RAM in GB (e.g., 16)</li>
                  </ul>
                </li>
                <li>Optionally add:
                  <ul style={{ marginTop: '0.5rem', color: '#94a3b8' }}>
                    <li><strong style={{ color: '#cbd5e1' }}>Region:</strong> us-east-1, eu-west-1, etc.</li>
                    <li><strong style={{ color: '#cbd5e1' }}>Operating System:</strong> Linux, Windows</li>
                    <li><strong style={{ color: '#cbd5e1' }}>Tenancy:</strong> Shared, Dedicated, Host</li>
                  </ul>
                </li>
                <li>Click <strong style={{ color: '#cbd5e1' }}>Get Predictions</strong></li>
                <li>View results sorted by predicted price (lowest first)</li>
              </ol>
            </div>
          </section>

          {/* Section 2: API Usage */}
          <section id="api-usage" style={{ marginBottom: '3rem' }}>
            <h3 style={{ color: '#f1f5f9', fontSize: '1.5rem', borderBottom: '2px solid #334155', paddingBottom: '0.5rem', marginBottom: '1rem' }}>
              API Usage
            </h3>
            
            <div style={{ background: '#1e293b', padding: '1.5rem', borderRadius: 8, marginBottom: '1.5rem', border: '1px solid #334155' }}>
              <h4 style={{ color: '#60a5fa', marginTop: 0 }}>Prediction Endpoint</h4>
              <p style={{ color: '#cbd5e1', margin: '0.5rem 0 1rem' }}>
                Make POST requests to get predictions programmatically. Full API documentation available at{' '}
                <a href="/api/schema/swagger-ui/" target="_blank" rel="noopener noreferrer" style={{ color: '#60a5fa' }}>
                  Swagger UI
                </a>
              </p>
              
              <div style={{ background: '#0f172a', padding: '1rem', borderRadius: 6, overflow: 'auto', fontSize: '0.875rem' }}>
                <pre style={{ margin: 0, color: '#e2e8f0', fontFamily: 'monospace' }}>
{`POST /api/engines/predict-by-type/
Content-Type: application/json

{
  "vcpu": 4,
  "memory_gb": 16,
  "provider_name": "AWS",
  "region": "us-east-1",
  "os": "Linux",
  "pricing_model": "on_demand"
}`}
                </pre>
              </div>

              <p style={{ color: '#94a3b8', marginTop: '1rem', fontSize: '0.875rem' }}>
                Only <code style={{ background: '#334155', padding: '0.2rem 0.5rem', borderRadius: 4, color: '#cbd5e1' }}>vcpu</code> and{' '}
                <code style={{ background: '#334155', padding: '0.2rem 0.5rem', borderRadius: 4, color: '#cbd5e1' }}>memory_gb</code> are required.
              </p>
            </div>
          </section>

        </div>
      )}

      {/* Contributor Documentation */}
      {activeTab === 'contributors' && (
        <div className="animate-fade-in">
          {/* Table of Contents */}
          <div style={{ background: '#1e293b', padding: '1.5rem', borderRadius: 8, marginBottom: '2rem', border: '1px solid #334155' }}>
            <h3 style={{ color: '#f1f5f9', marginTop: 0, marginBottom: '1rem' }}>Contributor Guide Contents</h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
              <a href="#exporting-data" style={{ color: '#60a5fa', textDecoration: 'none' }}>→ Exporting Training Data</a>
              <a href="#registering-model" style={{ color: '#60a5fa', textDecoration: 'none' }}>→ Registering via UI</a>
              <a href="#extra-model-files" style={{ color: '#60a5fa', textDecoration: 'none' }}>→ Supporting Extra Model Files</a>
              <a href="#example-code" style={{ color: '#60a5fa', textDecoration: 'none' }}>→ Complete Example</a>
            </div>
          </div>

          {/* Section 1: Exporting Training Data */}
          <section id="exporting-data" style={{ marginBottom: '3rem' }}>
            <h3 style={{ color: '#f1f5f9', fontSize: '1.5rem', borderBottom: '2px solid #334155', paddingBottom: '0.5rem', marginBottom: '1rem' }}>
              Exporting Training Data
            </h3>
            
            <div style={{ background: '#1e293b', padding: '1.5rem', borderRadius: 8, marginBottom: '1.5rem', border: '1px solid #334155' }}>
              <p style={{ color: '#cbd5e1', margin: '0 0 1.5rem' }}>
                Export historical pricing data for training your own models. The system provides a two-step workflow for generating and downloading CSV exports.
              </p>

              {/* Workflow Steps */}
              <div style={{ display: 'grid', gap: '1.25rem', marginBottom: '1.5rem' }}>
                {[
                  { num: 1, title: 'Request Export', desc: 'POST to /pricing-data/export/ with filters' },
                  { num: 2, title: 'Poll Status', desc: 'GET /pricing-data/export-status/{export_id}/' },
                  { num: 3, title: 'Check Completion', desc: 'Wait for status: "completed"' },
                  { num: 4, title: 'Download CSV', desc: 'Use file_url from status response' }
                ].map((step) => (
                  <div key={step.num} style={{ display: 'flex', gap: '1rem', alignItems: 'flex-start' }}>
                    <div style={{
                      background: 'linear-gradient(135deg, #3b82f6, #2563eb)',
                      color: '#fff',
                      width: '40px',
                      height: '40px',
                      borderRadius: '50%',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontWeight: 700,
                      flexShrink: 0,
                      boxShadow: '0 4px 12px rgba(59, 130, 246, 0.4)'
                    }}>
                      {step.num}
                    </div>
                    <div>
                      <div style={{ color: '#f1f5f9', fontWeight: 600, marginBottom: '0.25rem' }}>{step.title}</div>
                      <div style={{ color: '#94a3b8', fontSize: '0.875rem' }}>{step.desc}</div>
                    </div>
                  </div>
                ))}
              </div>

              <h4 style={{ color: '#60a5fa', marginTop: '1.5rem', marginBottom: '0.75rem' }}>Example: Request Export</h4>
              <div style={{ background: '#0f172a', padding: '1rem', borderRadius: 6, overflow: 'auto', fontSize: '0.875rem', marginBottom: '1rem' }}>
                <pre style={{ margin: 0, color: '#e2e8f0', fontFamily: 'monospace' }}>
{`POST /api/pricing-data/export/
Content-Type: application/json

{
  "provider": "AWS",
  "start_date": "2024-01-01",
  "end_date": "2024-12-31"
}`}
                </pre>
              </div>

              <h4 style={{ color: '#60a5fa', marginTop: '1.5rem', marginBottom: '0.75rem' }}>Example: Check Status</h4>
              <div style={{ background: '#0f172a', padding: '1rem', borderRadius: 6, overflow: 'auto', fontSize: '0.875rem' }}>
                <pre style={{ margin: 0, color: '#e2e8f0', fontFamily: 'monospace' }}>
{`GET /api/pricing-data/export-status/abc123/

Response:
{
  "export_id": "abc123",
  "status": "completed",
  "file_url": "/media/exports/pricing_export_20241218.csv",
  "created_at": "2024-12-18T10:30:00Z"
}`}
                </pre>
              </div>
            </div>
          </section>

          {/* Section 2: Registering Model */}
          <section id="registering-model" style={{ marginBottom: '3rem' }}>
            <h3 style={{ color: '#f1f5f9', fontSize: '1.5rem', borderBottom: '2px solid #334155', paddingBottom: '0.5rem', marginBottom: '1rem' }}>
              Registering Your Model
            </h3>
            
            <div style={{ background: '#1e293b', padding: '1.5rem', borderRadius: 8, marginBottom: '1.5rem', border: '1px solid #334155' }}>
              <h4 style={{ color: '#60a5fa', marginTop: 0 }}>Via Web Interface</h4>
              <ol style={{ color: '#cbd5e1', lineHeight: 1.8 }}>
                <li>Navigate to the <Link to="/contribute" style={{ color: '#60a5fa' }}>Contribute page</Link></li>
                <li>Fill in model details:
                  <ul style={{ marginTop: '0.5rem', color: '#94a3b8' }}>
                    <li><strong style={{ color: '#cbd5e1' }}>Model Name:</strong> Unique identifier (e.g., "ridge_regression_v2")</li>
                    <li><strong style={{ color: '#cbd5e1' }}>Type:</strong> scikit-learn, PyTorch, TensorFlow, etc.</li>
                    <li><strong style={{ color: '#cbd5e1' }}>Version:</strong> Semantic version (e.g., "1.0.0")</li>
                    <li><strong style={{ color: '#cbd5e1' }}>Description:</strong> Brief explanation of your approach</li>
                  </ul>
                </li>
                <li>Upload your trained model file (.pkl, .pt, .h5, etc.)</li>
                <li>No requirements.txt upload needed; standard libs installed (pandas, numpy, scikit-learn, statsmodels, joblib)</li>
                <li>Click <strong style={{ color: '#cbd5e1' }}>Register Model</strong></li>
                <li>System validates and registers your model for predictions</li>
              </ol>
            </div>

            <div style={{ background: '#1e293b', padding: '1.5rem', borderRadius: 8, border: '1px solid #334155' }}>
              <h4 style={{ color: '#60a5fa', marginTop: 0 }}>Via API</h4>
              <div style={{ background: '#0f172a', padding: '1rem', borderRadius: 6, overflow: 'auto', fontSize: '0.875rem' }}>
                <pre style={{ margin: 0, color: '#e2e8f0', fontFamily: 'monospace' }}>
{`POST /api/engines/
Content-Type: multipart/form-data

name: "my_model"
model_type: "scikit-learn"
version: "1.0.0"
description: "Ridge regression with feature engineering"
model_file: <binary>`}
                </pre>
              </div>
            </div>
          </section>

          {/* Section 3: Supporting Extra Model Files */}
          <section id="extra-model-files" style={{ marginBottom: '3rem' }}>
            <h3 style={{ color: '#f1f5f9', fontSize: '1.5rem', borderBottom: '2px solid #334155', paddingBottom: '0.5rem', marginBottom: '1rem' }}>
              Supporting Extra Model Files
            </h3>
            
            <div style={{ background: '#1e293b', padding: '1.5rem', borderRadius: 8, marginBottom: '1.5rem', border: '1px solid #334155' }}>
              <p style={{ color: '#cbd5e1', margin: '0 0 1.5rem' }}>
                If your model requires additional files (preprocessing pipelines, tokenizers, config files), you'll need to contribute code changes. Follow these steps:
              </p>

              <h4 style={{ color: '#60a5fa', marginTop: 0, marginBottom: '0.75rem' }}>1. Add FileField to Model</h4>
              <p style={{ color: '#94a3b8', fontSize: '0.875rem', margin: '0 0 0.75rem' }}>
                Edit <code style={{ background: '#334155', padding: '0.2rem 0.5rem', borderRadius: 4, color: '#cbd5e1' }}>model_registry/models.py</code>:
              </p>
              <div style={{ background: '#0f172a', padding: '1rem', borderRadius: 6, overflow: 'auto', fontSize: '0.875rem', marginBottom: '1rem' }}>
                <pre style={{ margin: 0, color: '#e2e8f0', fontFamily: 'monospace' }}>
{`class PredictionEngine(models.Model):
    # existing fields...
    preprocessor_file = models.FileField(
        upload_to='engines/preprocessors/',
        null=True,
        blank=True
    )`}
                </pre>
              </div>

              <h4 style={{ color: '#60a5fa', marginTop: '1.5rem', marginBottom: '0.75rem' }}>2. Update Serializer</h4>
              <p style={{ color: '#94a3b8', fontSize: '0.875rem', margin: '0 0 0.75rem' }}>
                Edit <code style={{ background: '#334155', padding: '0.2rem 0.5rem', borderRadius: 4, color: '#cbd5e1' }}>model_registry/api/serializers.py</code>:
              </p>
              <div style={{ background: '#0f172a', padding: '1rem', borderRadius: 6, overflow: 'auto', fontSize: '0.875rem', marginBottom: '1rem' }}>
                <pre style={{ margin: 0, color: '#e2e8f0', fontFamily: 'monospace' }}>
{`class PredictionEngineSerializer(serializers.ModelSerializer):
    class Meta:
        model = PredictionEngine
        fields = [
            'name', 'model_type', 'version',
            'model_file', 'preprocessor_file'  # add your new field
        ]`}
                </pre>
              </div>

              <h4 style={{ color: '#60a5fa', marginTop: '1.5rem', marginBottom: '0.75rem' }}>3. Update Prediction Task</h4>
              <p style={{ color: '#94a3b8', fontSize: '0.875rem', margin: '0 0 0.75rem' }}>
                Edit <code style={{ background: '#334155', padding: '0.2rem 0.5rem', borderRadius: 4, color: '#cbd5e1' }}>model_registry/tasks.py</code> to load your extra file:
              </p>
              <div style={{ background: '#0f172a', padding: '1rem', borderRadius: 6, overflow: 'auto', fontSize: '0.875rem', marginBottom: '1rem' }}>
                <pre style={{ margin: 0, color: '#e2e8f0', fontFamily: 'monospace' }}>
{`def load_model(engine_id):
    engine = PredictionEngine.objects.get(id=engine_id)
    model = pickle.load(engine.model_file)
    
    if engine.preprocessor_file:
        preprocessor = pickle.load(engine.preprocessor_file)
        return model, preprocessor
    
    return model, None`}
                </pre>
              </div>

              <h4 style={{ color: '#60a5fa', marginTop: '1.5rem', marginBottom: '0.75rem' }}>4. Open Pull Request</h4>
              <p style={{ color: '#cbd5e1', margin: 0 }}>
                Submit your changes to the{' '}
                <a 
                  href="https://github.com/yourusername/Cloud-PriceOps-thesis" 
                  target="_blank" 
                  rel="noopener noreferrer"
                  style={{ color: '#60a5fa' }}
                >
                  GitHub repository
                </a>
                {' '}with a description of your model's requirements.
              </p>
            </div>
          </section>

          {/* Section 4: Complete Example */}
          <section id="example-code" style={{ marginBottom: '3rem' }}>
            <h3 style={{ color: '#f1f5f9', fontSize: '1.5rem', borderBottom: '2px solid #334155', paddingBottom: '0.5rem', marginBottom: '1rem' }}>
              Complete Example
            </h3>
            
            <div style={{ background: '#1e293b', padding: '1.5rem', borderRadius: 8, border: '1px solid #334155' }}>
              <h4 style={{ color: '#60a5fa', marginTop: 0 }}>Simple Ridge Regression Model</h4>
              <div style={{ background: '#0f172a', padding: '1rem', borderRadius: 6, overflow: 'auto', fontSize: '0.875rem' }}>
                <pre style={{ margin: 0, color: '#e2e8f0', fontFamily: 'monospace' }}>
{`import pickle
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

# 1. Load training data
df = pd.read_csv('pricing_export.csv')

# 2. Prepare features
X = df[['vcpu', 'memory_gb', 'provider_encoded', 'region_encoded']]
y = df['price_per_hour']

# 3. Train model
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

model = Ridge(alpha=1.0)
model.fit(X_scaled, y)

# 4. Save model
with open('ridge_model.pkl', 'wb') as f:
    pickle.dump(model, f)

# 5. Register via UI or API
# Upload ridge_model.pkl at /contribute`}
                </pre>
              </div>
            </div>
          </section>
        </div>
      )}
    </div>
  )
}
