import { useEffect, useState } from 'react'
import './PredictForm.css'

type ModelType = {
  type: string
  count: number
  best_model: {
    name: string
    version: string
    r_squared?: number
    mape?: number
    is_active: boolean
  }
  feature_names?: string[]
  log_transformed_features?: string[]
  categorical_features?: string[]
}

type PredictionResult = {
  engine_version: string
  predicted_price: number
  currency: string
}

type AdditionalParam = {
  key: string
  value: string
}

const BACKEND_URL = (import.meta.env.VITE_APP_BACKEND_URL as string) || 'http://localhost:8000'

export default function PredictForm() {
  const [modelTypes, setModelTypes] = useState<ModelType[]>([])
  const [selectedType, setSelectedType] = useState<string>('')
  const [typeDetails, setTypeDetails] = useState<ModelType | null>(null)

  // Common fields
  const [vcpu, setVcpu] = useState<string>('')
  const [memory, setMemory] = useState<string>('')
  const [region, setRegion] = useState<string>('')
  const [os, setOs] = useState<string>('')
  const [tenancy, setTenancy] = useState<string>('')
  
  // Term/Payment options
  const [termLength, setTermLength] = useState<string>('')
  const [isAllUpfront, setIsAllUpfront] = useState<boolean>(false)
  const [isPartialUpfront, setIsPartialUpfront] = useState<boolean>(false)
  const [isNoUpfront, setIsNoUpfront] = useState<boolean>(false)

  // Additional dynamic parameters
  const [additionalParams, setAdditionalParams] = useState<AdditionalParam[]>([])

  const [loading, setLoading] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<PredictionResult | null>(null)

  // Fetch available model types
  useEffect(() => {
    const fetchModelTypes = async () => {
      try {
        const url = `${BACKEND_URL}/engines/types/`
        const res = await fetch(url)
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const data = await res.json()
        const typeList: ModelType[] = Array.isArray(data) ? data : data?.results ?? []
        setModelTypes(typeList)
        
        // Auto-select first type
        if (typeList.length > 0) {
          setSelectedType(typeList[0].type)
          setTypeDetails(typeList[0])
        }
      } catch (err: any) {
        console.error('Failed to fetch model types:', err)
      }
    }
    fetchModelTypes()
  }, [])

  // Update type details when selection changes
  useEffect(() => {
    const type = modelTypes.find((t: ModelType) => t.type === selectedType)
    setTypeDetails(type || null)
  }, [selectedType, modelTypes])

  const addParam = () => {
    setAdditionalParams([...additionalParams, { key: '', value: '' }])
  }

  const updateParam = (idx: number, field: 'key' | 'value', val: string) => {
    const next = [...additionalParams]
    next[idx][field] = val
    setAdditionalParams(next)
  }

  const removeParam = (idx: number) => {
    setAdditionalParams(additionalParams.filter((_: AdditionalParam, i: number) => i !== idx))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setResult(null)

    // Build payload
    const payload: Record<string, any> = {}

    // Add required fields
    payload.vcpu_count = parseFloat(vcpu)
    payload.memory_gb = parseFloat(memory)

    // Add optional common fields if provided
    if (region) payload.region = region
    if (os) payload.operating_system = os
    if (tenancy) payload.tenancy = tenancy
    if (termLength) payload.term_length_years = parseFloat(termLength) / 12

    // Add payment options only if at least one is selected
    if (isAllUpfront || isPartialUpfront || isNoUpfront) {
      if (isAllUpfront) payload.is_all_upfront = 1
      if (isPartialUpfront) payload.is_partial_upfront = 1
      if (isNoUpfront) payload.is_no_upfront = 1
    }

    // Add additional parameters
    additionalParams.forEach(({ key, value }: AdditionalParam) => {
      if (key && value) {
        const numVal = parseFloat(value)
        payload[key] = isNaN(numVal) ? value : numVal
      }
    })

    try {
      const url = `${BACKEND_URL}/engines/predict-by-type/${encodeURIComponent(selectedType)}/`
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })

      if (!res.ok) {
        const text = await res.text()
        throw new Error(`HTTP ${res.status}: ${text}`)
      }

      const data = await res.json()
      setResult(data)
    } catch (err: any) {
      setError(err.message ?? 'Request failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="predict-form-container">
      <div className="form-section">
        <h2>Cloud Price Prediction</h2>
        <p className="subtitle">
          Enter resource specifications to get ML-powered price predictions
        </p>

        <form onSubmit={handleSubmit}>
          {/* Model Type Selection */}
          <div className="form-group">
            <label htmlFor="modelType">Model Type</label>
            <select
              id="modelType"
              value={selectedType}
              onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setSelectedType(e.target.value)}
              disabled={modelTypes.length === 0}
            >
              {modelTypes.length === 0 && <option>Loading model types...</option>}
              {modelTypes.map((t: ModelType) => (
                <option key={t.type} value={t.type}>
                  {t.type} ({t.count} model{t.count !== 1 ? 's' : ''})
                </option>
              ))}
            </select>
            {typeDetails && typeDetails.best_model && (
              <small className="engine-info">
                Best Model: {typeDetails.best_model.name} v{typeDetails.best_model.version} | 
                R²: {typeDetails.best_model.r_squared?.toFixed(4) ?? 'N/A'} | 
                MAPE: {typeDetails.best_model.mape?.toFixed(2)}%
              </small>
            )}
          </div>

          {/* Common Resource Fields */}
          <div className="form-row">
            <div className="form-group">
              <label htmlFor="vcpu">vCPU <span className="required">*</span></label>
              <input
                id="vcpu"
                type="number"
                step="0.1"
                min="0"
                value={vcpu}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setVcpu(e.target.value)}
                placeholder="e.g. 4"
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="memory">Memory (GB) <span className="required">*</span></label>
              <input
                id="memory"
                type="number"
                step="0.1"
                min="0"
                value={memory}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setMemory(e.target.value)}
                placeholder="e.g. 16"
                required
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="region">Region <span className="optional">(optional)</span></label>
              <input
                id="region"
                type="text"
                value={region}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setRegion(e.target.value)}
                placeholder="e.g. us-east-1"
              />
            </div>

            <div className="form-group">
              <label htmlFor="os">Operating System <span className="optional">(optional)</span></label>
              <select id="os" value={os} onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setOs(e.target.value)}>
                <option value="">-- Select or leave empty --</option>
                <option value="Linux">Linux</option>
                <option value="Windows">Windows</option>
                <option value="RHEL">RHEL</option>
                <option value="SUSE">SUSE</option>
              </select>
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="tenancy">Tenancy <span className="optional">(optional)</span></label>
              <select id="tenancy" value={tenancy} onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setTenancy(e.target.value)}>
                <option value="">-- Select or leave empty --</option>
                <option value="shared">Shared</option>
                <option value="dedicated">Dedicated</option>
                <option value="host">Dedicated Host</option>
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="termLength">Term Length (months) <span className="optional">(optional)</span></label>
              <input
                id="termLength"
                type="number"
                step="1"
                min="0"
                value={termLength}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setTermLength(e.target.value)}
                placeholder="e.g. 12, 36 (leave empty for on-demand)"
              />
            </div>
          </div>

          {/* Payment Options */}
          <div className="form-group">
            <label>Payment Options</label>
            <div className="checkbox-group">
              <label>
                <input
                  type="checkbox"
                  checked={isAllUpfront}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setIsAllUpfront(e.target.checked)}
                />
                All Upfront
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={isPartialUpfront}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setIsPartialUpfront(e.target.checked)}
                />
                Partial Upfront
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={isNoUpfront}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setIsNoUpfront(e.target.checked)}
                />
                No Upfront
              </label>
            </div>
          </div>

          {/* Additional Parameters */}
          <div className="form-group">
            <label>Additional Parameters</label>
            {additionalParams.map((param, idx) => (
              <div key={idx} className="param-row">
                <input
                  type="text"
                  placeholder="Parameter name (e.g. gpu)"
                  value={param.key}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateParam(idx, 'key', e.target.value)}
                />
                <input
                  type="text"
                  placeholder="Value (e.g. 1)"
                  value={param.value}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateParam(idx, 'value', e.target.value)}
                />
                <button
                  type="button"
                  className="btn-remove"
                  onClick={() => removeParam(idx)}
                >
                  Remove
                </button>
              </div>
            ))}
            <button type="button" className="btn-secondary" onClick={addParam}>
              + Add Parameter
            </button>
          </div>

          <button
            type="submit"
            className="btn-primary"
            disabled={loading || !selectedType}
          >
            {loading ? 'Predicting...' : 'Get Price Prediction'}
          </button>
        </form>
      </div>

      {/* Results Section */}
      <div className="results-section">
        {error && (
          <div className="error-box">
            <h3>Error</h3>
            <p>{error}</p>
          </div>
        )}

        {result && (
          <div className="result-box">
            <h3>Prediction Result</h3>
            <div className="result-details">
              <div className="result-item highlight">
                <span className="label">Predicted Price:</span>
                <span className="value price">
                  ${result.predicted_price.toFixed(6)} {result.currency} / hour
                </span>
              </div>
              <div className="result-item">
                <span className="label">Monthly Cost:</span>
                <span className="value">
                  ${(result.predicted_price * 730).toFixed(2)} {result.currency}
                </span>
              </div>
              <div className="result-item">
                <span className="label">Yearly Cost:</span>
                <span className="value">
                  ${(result.predicted_price * 8760).toFixed(2)} {result.currency}
                </span>
              </div>
              <div className="result-item">
                <span className="label">Engine Version:</span>
                <span className="value">{result.engine_version}</span>
              </div>
            </div>
          </div>
        )}

        {typeDetails && !result && !error && (
          <div className="info-box">
            <h3>Model Information</h3>
            <div className="info-details">
              <p><strong>Type:</strong> {typeDetails.type}</p>
              <p><strong>Available Models:</strong> {typeDetails.count}</p>
              {typeDetails.best_model && (
                <>
                  <p><strong>Best Model:</strong> {typeDetails.best_model.name} v{typeDetails.best_model.version}</p>
                  <p><strong>R² Score:</strong> {typeDetails.best_model.r_squared?.toFixed(4) ?? 'N/A'}</p>
                  <p><strong>MAPE:</strong> {typeDetails.best_model.mape?.toFixed(2)}%</p>
                </>
              )}
              {typeDetails.log_transformed_features && typeDetails.log_transformed_features.length > 0 && (
                <p><strong>Log Features:</strong> {typeDetails.log_transformed_features.join(', ')}</p>
              )}
              {typeDetails.categorical_features && typeDetails.categorical_features.length > 0 && (
                <p><strong>Categorical Features:</strong> {typeDetails.categorical_features.join(', ')}</p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
