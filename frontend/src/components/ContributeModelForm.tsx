import { useState } from 'react'
import SchemaVisualizer from './SchemaVisualizer'
import { Link } from 'react-router-dom'

const BACKEND_URL = (import.meta.env.VITE_APP_BACKEND_URL as string) || 'http://localhost:8000'

export default function ContributeModelForm() {
  const [activeTab, setActiveTab] = useState<'schema' | 'form'>('schema')
  const [name, setName] = useState('')
  const [modelType, setModelType] = useState('Regression')
  const [version, setVersion] = useState('')
  const [featureNames] = useState<string>('[]')
  const [logFeatures] = useState<string>('[]')
  const [catFeatures] = useState<string>('[]')
  const [r2, setR2] = useState<string>('')
  const [mape, setMape] = useState<string>('')
  const [rmse, setRmse] = useState<string>('')
  const [samples, setSamples] = useState<string>('')
  const [isActive, setIsActive] = useState<boolean>(false)
  const [metadata] = useState<string>('{"algorithm":"Ridge"}')
  const [modelFile] = useState<File | null>(null)
  const [encoderFile] = useState<File | null>(null)
  const [scalerFile] = useState<File | null>(null)

  const [error, setError] = useState<string | null>(null)
  const [ok, setOk] = useState<string | null>(null)

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setOk(null)

    if (!modelFile) {
      setError('Model binary is required')
      return
    }

    const fd = new FormData()
    fd.append('name', name)
    fd.append('model_type', modelType)
    fd.append('version', version)
    fd.append('feature_names', featureNames)
    fd.append('log_transformed_features', logFeatures)
    fd.append('categorical_features', catFeatures)
    if (r2) fd.append('r_squared', r2)
    if (mape) fd.append('mape', mape)
    if (rmse) fd.append('rmse', rmse)
    if (samples) fd.append('training_sample_size', samples)
    fd.append('is_active', String(isActive))
    if (metadata) fd.append('metadata', metadata)
    fd.append('model_binary', modelFile)
    if (encoderFile) fd.append('encoder_binary', encoderFile)
    if (scalerFile) fd.append('scaler_binary', scalerFile)

    try {
      const res = await fetch(`${BACKEND_URL}/engines/`, { method: 'POST', body: fd })
      if (!res.ok) {
        const text = await res.text()
        throw new Error(`HTTP ${res.status}: ${text}`)
      }
      const data = await res.json()
      setOk(`Model registered: ${data.name} v${data.version}`)
    } catch (err: any) {
      setError(err.message ?? 'Upload failed')
    } finally {
    }
  }

  return (
    <div style={{ maxWidth: 900, margin: '0 auto', display: 'flex', flexDirection: 'column' }}>
      {/* Tab Navigation - always horizontal, at top */}
      <div style={{ width: '100%', display: 'flex', flexDirection: 'row', gap: '1rem', marginBottom: '2rem', borderBottom: '1px solid #334155', alignItems: 'flex-end', background: 'transparent' }}>
        <button
          onClick={() => setActiveTab('schema')}
          style={{
            background: activeTab === 'schema' ? '#334155' : 'transparent',
            color: activeTab === 'schema' ? '#60a5fa' : '#cbd5e1',
            border: 'none',
            borderBottom: activeTab === 'schema' ? '2px solid #60a5fa' : 'none',
            padding: '0.75rem 1.5rem',
            fontWeight: 600,
            cursor: 'pointer',
            fontSize: '1rem',
            outline: 'none',
            borderRadius: '8px 8px 0 0',
          }}
        >
          Schema
        </button>
        <button
          onClick={() => setActiveTab('form')}
          style={{
            background: activeTab === 'form' ? '#334155' : 'transparent',
            color: activeTab === 'form' ? '#60a5fa' : '#cbd5e1',
            border: 'none',
            borderBottom: activeTab === 'form' ? '2px solid #60a5fa' : 'none',
            padding: '0.75rem 1.5rem',
            fontWeight: 600,
            cursor: 'pointer',
            fontSize: '1rem',
            outline: 'none',
            borderRadius: '8px 8px 0 0',
          }}
        >
          Contribute
        </button>
      </div>

      {/* Tab Content */}
      {activeTab === 'schema' ? (
        <div style={{ marginBottom: '2rem' }} className="animate-slide-up animate-delay-1">
          <h2 style={{ color: '#60a5fa', marginBottom: '1rem' }}>Database Schema Overview</h2>
          <p style={{ color: '#cbd5e1', marginBottom: '1.5rem', fontSize: '1rem' }}>
            This page provides a visual overview of the database schema used for cloud pricing models. Each table and its relationships are shown to help contributors understand how data is structured and connected. Use this reference to ensure your model and metadata align with the platform's requirements.<br />
            For details on contributing models, <button onClick={() => setActiveTab('form')} style={{ color: '#60a5fa', background: 'none', border: 'none', textDecoration: 'underline', cursor: 'pointer', fontWeight: 600, fontSize: '1rem', padding: 0 }}>click here to go to the Contribute tab</button>.
          </p>
          <SchemaVisualizer />
        </div>
      ) : (
        <>
          <div className="page-header">
            <div className="page-header-breadcrumb">
              <svg width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
                <path d="M8.5 5.5a.5.5 0 0 0-1 0v3.362l-1.429 2.38a.5.5 0 1 0 .858.515l1.5-2.5A.5.5 0 0 0 8.5 9V5.5z"/>
                <path d="M6.5 0a.5.5 0 0 0 0 1H7v1.07a7.001 7.001 0 0 0-3.273 12.474l-.602.602a.5.5 0 0 0 .707.708l.746-.746A6.97 6.97 0 0 0 8 16a6.97 6.97 0 0 0 3.422-.892l.746.746a.5.5 0 0 0 .707-.708l-.601-.602A7.001 7.001 0 0 0 9 2.07V1h.5a.5.5 0 0 0 0-1h-3zm1.038 3.018a6.093 6.093 0 0 1 .924 0 6 6 0 1 1-.924 0zM0 3.5c0 .753.333 1.429.86 1.887A8.035 8.035 0 0 1 4.387 1.86 2.5 2.5 0 0 0 0 3.5zM13.5 1c-.753 0-1.429.333-1.887.86a8.035 8.035 0 0 1 3.527 3.527A2.5 2.5 0 0 0 13.5 1z"/>
              </svg>
              Contribute / Register
            </div>
            <p className="page-header-subtitle">Upload your trained pricing model with metadata and performance metrics. All JSON fields require valid syntax.</p>
          </div>
          <div style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 10, padding: '1rem 1.25rem', marginBottom: '1.5rem', color: '#cbd5e1' }}>
            <strong style={{ color: '#f1f5f9' }}>Note:</strong> If your model depends on extra files (embeddings, tokenizers, auxiliary assets), please open a pull request in
            {' '}<a href="https://github.com/nhaskaris/cloud-priceops-thesis" style={{ color: '#60a5fa' }}>cloud-priceops-thesis</a> and follow the
            {' '}<Link to="/docs#extra-model-files" style={{ color: '#60a5fa' }}>extra model files guidance</Link> in the docs.
          </div>
          {/* Step-by-step guide */}
          <div style={{ background: '#1e293b', padding: '1.5rem', borderRadius: 8, marginBottom: '1.5rem', border: '1px solid #334155' }} className="animate-slide-up animate-delay-1">
            <div style={{ color: '#60a5fa', fontWeight: 600, marginBottom: '1rem', fontSize: '1rem' }}>📋 CONTRIBUTION STEPS:</div>
            <div style={{ display: 'grid', gap: '1rem', gridTemplateColumns: '1fr 1fr' }}>
              <div>
                <div style={{ color: '#94a3b8', fontWeight: 600, fontSize: '0.875rem', marginBottom: '0.5rem' }}>
                  STEP 1: MODEL FILES
                </div>
                <ul style={{ margin: 0, paddingLeft: '1.25rem', color: '#cbd5e1', fontSize: '0.825rem', lineHeight: 1.6 }}>
                  <li>model_binary.pkl (required)</li>
                  <li>encoder_binary.pkl (optional)</li>
                  <li>scaler_binary.pkl (optional)</li>
                </ul>
              </div>
              <div>
                <div style={{ color: '#94a3b8', fontWeight: 600, fontSize: '0.875rem', marginBottom: '0.5rem' }}>
                  STEP 2: METADATA
                </div>
                <ul style={{ margin: 0, paddingLeft: '1.25rem', color: '#cbd5e1', fontSize: '0.825rem', lineHeight: 1.6 }}>
                  <li>Name, Type, Version</li>
                  <li>Feature names (JSON)</li>
                  <li>Transform details (JSON)</li>
                </ul>
              </div>
              <div>
                <div style={{ color: '#94a3b8', fontWeight: 600, fontSize: '0.875rem', marginBottom: '0.5rem' }}>
                  STEP 3: METRICS
                </div>
                <ul style={{ margin: 0, paddingLeft: '1.25rem', color: '#cbd5e1', fontSize: '0.825rem', lineHeight: 1.6 }}>
                  <li>R² score (0-1)</li>
                  <li>MAPE (percentage)</li>
                  <li>RMSE, Sample size</li>
                </ul>
              </div>
              <div>
                <div style={{ color: '#94a3b8', fontWeight: 600, fontSize: '0.875rem', marginBottom: '0.5rem' }}>
                  STEP 4: SUBMIT
                </div>
                <ul style={{ margin: 0, paddingLeft: '1.25rem', color: '#cbd5e1', fontSize: '0.825rem', lineHeight: 1.6 }}>
                  <li>Validate JSON fields</li>
                  <li>Upload all files</li>
                  <li>Model goes live!</li>
                </ul>
              </div>
            </div>
          </div>

          {error && <div className="error" style={{ margin: '1rem 0' }}>{error}</div>}
          {ok && <div className="best" style={{ margin: '1rem 0' }}>{ok}</div>}

          <form onSubmit={onSubmit} className="form" style={{ gridTemplateColumns: '1fr 1fr' }}>
            {/* Section 1: Basic Info */}
            <div style={{ gridColumn: '1 / -1', background: '#0f172a', padding: '0.75rem 1rem', borderRadius: 6, marginBottom: '0.5rem', border: '1px solid #334155' }}>
              <span style={{ color: '#60a5fa', fontWeight: 600, fontSize: '0.875rem' }}>SECTION 1: BASIC INFORMATION</span>
            </div>
            
            <label style={{ color: '#cbd5e1' }}>
              Name
              <input value={name} onChange={e => setName(e.target.value)} placeholder="AWS_Compute_Pricing" required />
            </label>
            <label style={{ color: '#cbd5e1' }}>
              Model Type
              <input value={modelType} onChange={e => setModelType(e.target.value)} placeholder="Regression" required />
            </label>
            <label style={{ color: '#cbd5e1' }}>
              Version
              <input value={version} onChange={e => setVersion(e.target.value)} placeholder="2025.12.26.01" required />
            </label>

            {/* Section 2: Performance Metrics */}
            <div style={{ gridColumn: '1 / -1', background: '#0f172a', padding: '0.75rem 1rem', borderRadius: 6, marginTop: '1rem', marginBottom: '0.5rem', border: '1px solid #334155' }}>
              <span style={{ color: '#60a5fa', fontWeight: 600, fontSize: '0.875rem' }}>SECTION 2: PERFORMANCE METRICS</span>
            </div>
            
            <label style={{ color: '#cbd5e1' }}>
              R²
              <input type="number" step="0.0001" min="0" max="1" value={r2} onChange={e => setR2(e.target.value)} placeholder="0.92" />
            </label>
            <label style={{ color: '#cbd5e1' }}>
              MAPE (%)
              <input type="number" step="0.01" value={mape} onChange={e => setMape(e.target.value)} placeholder="41.72" />
            </label>
            <label style={{ color: '#cbd5e1' }}>
              RMSE
              <input type="number" step="0.0001" value={rmse} onChange={e => setRmse(e.target.value)} placeholder="0.1234" />
            </label>
            <label style={{ color: '#cbd5e1' }}>
              Training Samples
              <input type="number" value={samples} onChange={e => setSamples(e.target.value)} placeholder="50000" />
            </label>
            <label style={{ color: '#cbd5e1', alignSelf: 'end' }}>
              <input type="checkbox" checked={isActive} onChange={e => setIsActive(e.target.checked)} /> Active (Champion)
            </label>
          </form>
        </>
      )}
    </div>
  )
}
