import { useState } from 'react'

const BACKEND_URL = (import.meta.env.VITE_APP_BACKEND_URL as string) || 'http://localhost:8000'

export default function ContributeModelForm() {
  const [name, setName] = useState('')
  const [modelType, setModelType] = useState('Regression')
  const [version, setVersion] = useState('')
  const [featureNames, setFeatureNames] = useState<string>('[]')
  const [logFeatures, setLogFeatures] = useState<string>('[]')
  const [catFeatures, setCatFeatures] = useState<string>('[]')
  const [r2, setR2] = useState<string>('')
  const [mape, setMape] = useState<string>('')
  const [rmse, setRmse] = useState<string>('')
  const [samples, setSamples] = useState<string>('')
  const [isActive, setIsActive] = useState<boolean>(false)
  const [metadata, setMetadata] = useState<string>('{"algorithm":"Ridge"}')
  const [modelFile, setModelFile] = useState<File | null>(null)
  const [encoderFile, setEncoderFile] = useState<File | null>(null)
  const [scalerFile, setScalerFile] = useState<File | null>(null)

  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [ok, setOk] = useState<string | null>(null)

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    setOk(null)

    if (!modelFile) {
      setError('Model binary is required')
      setSubmitting(false)
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
      setSubmitting(false)
    }
  }

  return (
    <div style={{ maxWidth: 900, margin: '0 auto' }}>
      <div className="page-header">
        <div className="page-header-breadcrumb">
          <svg width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
            <path d="M8.5 5.5a.5.5 0 0 0-1 0v3.362l-1.429 2.38a.5.5 0 1 0 .858.515l1.5-2.5A.5.5 0 0 0 8.5 9V5.5z"/>
            <path d="M6.5 0a.5.5 0 0 0 0 1H7v1.07a7.001 7.001 0 0 0-3.273 12.474l-.602.602a.5.5 0 0 0 .707.708l.746-.746A6.97 6.97 0 0 0 8 16a6.97 6.97 0 0 0 3.422-.892l.746.746a.5.5 0 0 0 .707-.708l-.601-.602A7.001 7.001 0 0 0 9 2.07V1h.5a.5.5 0 0 0 0-1h-3zm1.038 3.018a6.093 6.093 0 0 1 .924 0 6 6 0 1 1-.924 0zM0 3.5c0 .753.333 1.429.86 1.887A8.035 8.035 0 0 1 4.387 1.86 2.5 2.5 0 0 0 0 3.5zM13.5 1c-.753 0-1.429.333-1.887.86a8.035 8.035 0 0 1 3.527 3.527A2.5 2.5 0 0 0 13.5 1z"/>
          </svg>
          Contribute / Register
        </div>
        <h1 className="page-header-title">Register Model Engine</h1>
        <p className="page-header-subtitle">Upload your trained pricing model with metadata and performance metrics. All JSON fields require valid syntax.</p>
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

        {/* Section 3: Feature Configuration */}
        <div style={{ gridColumn: '1 / -1', background: '#0f172a', padding: '0.75rem 1rem', borderRadius: 6, marginTop: '1rem', marginBottom: '0.5rem', border: '1px solid #334155' }}>
          <span style={{ color: '#60a5fa', fontWeight: 600, fontSize: '0.875rem' }}>SECTION 3: FEATURE CONFIGURATION (JSON)</span>
        </div>

        <label style={{ gridColumn: '1 / -1', color: '#cbd5e1' }}>
          feature_names (JSON array)
          <textarea value={featureNames} onChange={e => setFeatureNames(e.target.value)} rows={3} placeholder='["const","log_vcpu_count","log_memory_gb"]' style={{ background: '#0f172a', color: '#e2e8f0', border: '1px solid #475569', borderRadius: 6, padding: '0.5rem' }} />
        </label>
        <label style={{ color: '#cbd5e1' }}>
          log_transformed_features (JSON array)
          <textarea value={logFeatures} onChange={e => setLogFeatures(e.target.value)} rows={3} placeholder='["vcpu_count","memory_gb"]' style={{ background: '#0f172a', color: '#e2e8f0', border: '1px solid #475569', borderRadius: 6, padding: '0.5rem' }} />
        </label>
        <label style={{ color: '#cbd5e1' }}>
          categorical_features (JSON array)
          <textarea value={catFeatures} onChange={e => setCatFeatures(e.target.value)} rows={3} placeholder='["region","operating_system"]' style={{ background: '#0f172a', color: '#e2e8f0', border: '1px solid #475569', borderRadius: 6, padding: '0.5rem' }} />
        </label>
        <label style={{ gridColumn: '1 / -1', color: '#cbd5e1' }}>
          metadata (JSON object)
          <textarea value={metadata} onChange={e => setMetadata(e.target.value)} rows={3} placeholder='{"algorithm":"Ridge","alpha":1.0}' style={{ background: '#0f172a', color: '#e2e8f0', border: '1px solid #475569', borderRadius: 6, padding: '0.5rem' }} />
        </label>

        {/* Section 4: Model Files */}
        <div style={{ gridColumn: '1 / -1', background: '#0f172a', padding: '0.75rem 1rem', borderRadius: 6, marginTop: '1rem', marginBottom: '0.5rem', border: '1px solid #334155' }}>
          <span style={{ color: '#60a5fa', fontWeight: 600, fontSize: '0.875rem' }}>SECTION 4: MODEL FILES (.pkl)</span>
        </div>

        <label style={{ color: '#cbd5e1' }}>
          model_binary (.pkl)
          <input type="file" accept=".pkl,.joblib,application/octet-stream" onChange={e => setModelFile(e.target.files?.[0] ?? null)} required />
        </label>
        <label style={{ color: '#cbd5e1' }}>
          encoder_binary (.pkl)
          <input type="file" accept=".pkl,.joblib,application/octet-stream" onChange={e => setEncoderFile(e.target.files?.[0] ?? null)} />
        </label>
        <label style={{ color: '#cbd5e1' }}>
          scaler_binary (.pkl)
          <input type="file" accept=".pkl,.joblib,application/octet-stream" onChange={e => setScalerFile(e.target.files?.[0] ?? null)} />
        </label>

        <button type="submit" disabled={submitting}>
          {submitting ? 'Uploading…' : 'Register Model'}
        </button>
      </form>
    </div>
  )
}
