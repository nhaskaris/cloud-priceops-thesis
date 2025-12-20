import { useEffect, useState } from 'react'
import './PredictForm.css'

type Engine = {
  id: string
  name: string
  version: string
  model_type: string
  is_active: boolean
  r_squared?: number
  mape?: number
  feature_names?: string[]
  log_transformed_features?: string[]
  categorical_features?: string[]
}

type PredictionResult = {
  engine_version: string
  predicted_price: number
  currency: string
  compute_node: string
}

type AdditionalParam = {
  key: string
  value: string
}

const BACKEND_URL = (import.meta.env.VITE_APP_BACKEND_URL as string) || 'http://localhost:8000'

export default function PredictForm() {
  const [engines, setEngines] = useState<Engine[]>([])
  const [selectedEngine, setSelectedEngine] = useState<string>('')
  const [engineDetails, setEngineDetails] = useState<Engine | null>(null)

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

  // Fetch available engines
  useEffect(() => {
    const fetchEngines = async () => {
      try {
        const url = `${BACKEND_URL}/engines/`
        const res = await fetch(url)
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const data = await res.json()
        const engineList: Engine[] = Array.isArray(data) ? data : data?.results ?? []
        setEngines(engineList)
        
        // Auto-select first active engine
        const active = engineList.find(e => e.is_active)
        if (active) {
          setSelectedEngine(active.name)
          setEngineDetails(active)
        } else if (engineList.length > 0) {
          setSelectedEngine(engineList[0].name)
          setEngineDetails(engineList[0])
        }
      } catch (err: any) {
        console.error('Failed to fetch engines:', err)
      }
    }
    fetchEngines()
  }, [])

  // Update engine details when selection changes
  useEffect(() => {
    const engine = engines.find((e: Engine) => e.name === selectedEngine)
    setEngineDetails(engine || null)
  }, [selectedEngine, engines])

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
      const url = `${BACKEND_URL}/engines/predict/${encodeURIComponent(selectedEngine)}/`
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
          {/* Engine Selection */}
          <div className="form-group">
            <label htmlFor="engine">ML Engine</label>
            <select
              id="engine"
              value={selectedEngine}
              onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setSelectedEngine(e.target.value)}
              disabled={engines.length === 0}
            >
              {engines.length === 0 && <option>Loading engines...</option>}
              {engines.map((e: Engine) => (
                <option key={e.id} value={e.name}>
                  {e.name} v{e.version} {e.is_active ? '(Active)' : ''}
                </option>
              ))}
            </select>
            {engineDetails && (
              <small className="engine-info">
                Type: {engineDetails.model_type} | 
                R²: {engineDetails.r_squared?.toFixed(4) ?? 'N/A'} | 
                MAPE: {engineDetails.mape?.toFixed(2)}%
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
            disabled={loading || !selectedEngine}
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

        {engineDetails && !result && !error && (
          <div className="info-box">
            <h3>Engine Information</h3>
            <div className="info-details">
              <p><strong>Name:</strong> {engineDetails.name}</p>
              <p><strong>Type:</strong> {engineDetails.model_type}</p>
              <p><strong>Version:</strong> {engineDetails.version}</p>
              <p><strong>R² Score:</strong> {engineDetails.r_squared?.toFixed(4) ?? 'N/A'}</p>
              <p><strong>MAPE:</strong> {engineDetails.mape?.toFixed(2)}%</p>
              {engineDetails.log_transformed_features && engineDetails.log_transformed_features.length > 0 && (
                <p><strong>Log Features:</strong> {engineDetails.log_transformed_features.join(', ')}</p>
              )}
              {engineDetails.categorical_features && engineDetails.categorical_features.length > 0 && (
                <p><strong>Categorical Features:</strong> {engineDetails.categorical_features.join(', ')}</p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
