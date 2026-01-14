import { useEffect, useState } from 'react'
import './CostOptimizer.css'

type ModelType = {
  type: string
  count: number
  best_model: {
    name: string
    version: string
    r_squared?: number
    mape?: number
    is_active: boolean
    timestamp_created?: string
  }
  feature_names?: string[]
  log_transformed_features?: string[]
  categorical_features?: string[]
}

type PredictionResult = {
  engine_version: string
  predicted_price: number
  currency: string
  model_type?: string
  model_name?: string
  r_squared?: number | null
  mape?: number
  timestamp_created?: string
  created_at?: string
  input_specs?: {
    vcpu?: number
    memory?: number
    region?: string
    os?: string
    tenancy?: string
  }
  actual_pricing_options?: Array<{
    score: number
    price: number
    instance_type: string
    vcpu: number | null
    memory: number | null
    region: string | null
    provider: string | null
    service: string | null
    os: string
    tenancy: string
    product_family: string
    pricing_model: string | null
    description: string
    db_id: string
  }>
}

type AdditionalParam = {
  key: string
  value: string
}

const BACKEND_URL = (import.meta.env.VITE_APP_BACKEND_URL as string) || 'http://localhost:8000'

export default function PricingAnalyzer() {
  const [analysisMode, setAnalysisMode] = useState<'simple' | 'advanced'>('simple')
  const [modelTypes, setModelTypes] = useState<ModelType[]>([])
  const [selectedType, setSelectedType] = useState<string>('')
  const [typeDetails, setTypeDetails] = useState<ModelType | null>(null)

  // Common fields
  const [vcpu, setVcpu] = useState<string>('4')
  const [memory, setMemory] = useState<string>('16')
  const [region, setRegion] = useState<string>('us-east-1')
  const [os, setOs] = useState<string>('Linux')
  const [tenancy, setTenancy] = useState<string>('default')
  
  // Cost Optimizer specific
  const [currentCost, setCurrentCost] = useState<string>('0.5')

  // Advanced prediction fields
  const [termLength, setTermLength] = useState<string>('')
  const [isAllUpfront, setIsAllUpfront] = useState<boolean>(false)
  const [isPartialUpfront, setIsPartialUpfront] = useState<boolean>(false)
  const [isNoUpfront, setIsNoUpfront] = useState<boolean>(false)
  const [additionalParams, setAdditionalParams] = useState<AdditionalParam[]>([])

  const [loading, setLoading] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)
  const [predictions, setPredictions] = useState<PredictionResult[]>([])

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

  const handleAnalyze = async () => {
    setLoading(true)
    setError(null)
    setPredictions([])

    try {
      if (analysisMode === 'simple') {
        // Simple mode: find best model and predict
        const typesRes = await fetch(`${BACKEND_URL}/engines/types/`)
        if (!typesRes.ok) throw new Error('Failed to fetch model types')
        const typesData = await typesRes.json()
        
        if (!Array.isArray(typesData) || typesData.length === 0) {
          setError('No models available. Please register a model first.')
          setLoading(false)
          return
        }

        const bestModelType = typesData.reduce((best, current) => {
          const bestR2 = best.best_model?.r_squared ?? -1
          const currentR2 = current.best_model?.r_squared ?? -1
          return currentR2 > bestR2 ? current : best
        })

        const specs = {
          vcpu_count: parseFloat(vcpu),
          memory_gb: parseFloat(memory),
          region,
          operating_system: os,
          tenancy,
          domain_label: 'iaas',
        }

        const response = await fetch(`${BACKEND_URL}/engines/predict-by-type/${bestModelType.type}/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(specs),
        })

        if (!response.ok) {
          setError('Could not get prediction from the best model')
          setLoading(false)
          return
        }

        const prediction = await response.json()
        setPredictions([prediction])
      } else {
        // Advanced mode: use selected type with full parameters
        const payload: Record<string, any> = {
          vcpu_count: parseFloat(vcpu),
          memory_gb: parseFloat(memory),
        }

        if (region) payload.region = region
        if (os) payload.operating_system = os
        if (tenancy) payload.tenancy = tenancy
        if (termLength) payload.term_length_years = parseFloat(termLength) / 12

        if (isAllUpfront || isPartialUpfront || isNoUpfront) {
          if (isAllUpfront) payload.is_all_upfront = 1
          if (isPartialUpfront) payload.is_partial_upfront = 1
          if (isNoUpfront) payload.is_no_upfront = 1
        }

        additionalParams.forEach(({ key, value }: AdditionalParam) => {
          if (key && value) {
            const numVal = parseFloat(value)
            payload[key] = isNaN(numVal) ? value : numVal
          }
        })

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
        setPredictions([data])
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to analyze')
    } finally {
      setLoading(false)
    }
  }

  const getPredictionColor = (predicted: number, current: number) => {
    if (predicted < current) return '#22c55e'
    if (predicted > current) return '#ef4444'
    return '#94a3b8'
  }

  const formatPrice = (price: number) => {
    return price.toLocaleString('en-US', { 
      minimumFractionDigits: 0,
      maximumFractionDigits: 6 
    })
  }

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto' }}>
      <div className="page-header">
        <div className="page-header-breadcrumb">
          Pricing Analysis
        </div>
        <h1 className="page-header-title">Pricing Analysis & Optimization</h1>
        <p className="page-header-subtitle">Analyze cloud pricing with ML-powered predictions and cost optimization insights</p>
      </div>

      {/* Mode Toggle */}
      <div style={{ display: 'flex', gap: '1rem', marginBottom: '2rem' }}>
        <button
          onClick={() => setAnalysisMode('simple')}
          style={{
            flex: 1,
            padding: '0.75rem 1.5rem',
            background: analysisMode === 'simple' ? 'linear-gradient(180deg, #3b82f6, #2563eb)' : '#1e293b',
            color: 'white',
            border: `2px solid ${analysisMode === 'simple' ? '#3b82f6' : '#334155'}`,
            borderRadius: 10,
            cursor: 'pointer',
            fontWeight: 600,
            transition: 'all 0.2s',
          }}
        >
          Cost Optimizer
        </button>
        <button
          onClick={() => setAnalysisMode('advanced')}
          style={{
            flex: 1,
            padding: '0.75rem 1.5rem',
            background: analysisMode === 'advanced' ? 'linear-gradient(180deg, #8b5cf6, #7c3aed)' : '#1e293b',
            color: 'white',
            border: `2px solid ${analysisMode === 'advanced' ? '#8b5cf6' : '#334155'}`,
            borderRadius: 10,
            cursor: 'pointer',
            fontWeight: 600,
            transition: 'all 0.2s',
          }}
        >
          Advanced Prediction
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem', marginBottom: '2rem' }}>
        {/* Input Form */}
        <div style={{ background: '#1e293b', padding: '2rem', borderRadius: 12, border: '1px solid #334155' }}>
          <h3 style={{ color: '#f1f5f9', marginTop: 0 }}>
            {analysisMode === 'simple' ? 'Your Current Setup' : 'Resource Specifications'}
          </h3>

          <div style={{ marginBottom: '1.5rem' }}>
            <label style={{ display: 'block', color: '#cbd5e1', fontSize: '0.9rem', fontWeight: 600, marginBottom: '0.5rem' }}>
              vCPU Count <span style={{ color: '#f87171' }}>*</span>
            </label>
            <input
              type="number"
              value={vcpu}
              onChange={(e) => setVcpu(e.target.value)}
              step="0.5"
              min="0.5"
              style={{
                width: '100%',
                padding: '0.75rem',
                background: '#0f172a',
                border: '1px solid #475569',
                borderRadius: 8,
                color: '#e2e8f0',
              }}
              placeholder="e.g., 4"
            />
          </div>

          <div style={{ marginBottom: '1.5rem' }}>
            <label style={{ display: 'block', color: '#cbd5e1', fontSize: '0.9rem', fontWeight: 600, marginBottom: '0.5rem' }}>
              Memory (GB) <span style={{ color: '#f87171' }}>*</span>
            </label>
            <input
              type="number"
              value={memory}
              onChange={(e) => setMemory(e.target.value)}
              step="1"
              min="1"
              style={{
                width: '100%',
                padding: '0.75rem',
                background: '#0f172a',
                border: '1px solid #475569',
                borderRadius: 8,
                color: '#e2e8f0',
              }}
              placeholder="e.g., 16"
            />
          </div>

          <div style={{ marginBottom: '1.5rem' }}>
            <label style={{ display: 'block', color: '#cbd5e1', fontSize: '0.9rem', fontWeight: 600, marginBottom: '0.5rem' }}>
              Region
            </label>
            <input
              type="text"
              value={region}
              onChange={(e) => setRegion(e.target.value)}
              style={{
                width: '100%',
                padding: '0.75rem',
                background: '#0f172a',
                border: '1px solid #475569',
                borderRadius: 8,
                color: '#e2e8f0',
              }}
              placeholder="e.g., us-east-1"
            />
          </div>

          <div style={{ marginBottom: '1.5rem', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <div>
              <label style={{ display: 'block', color: '#cbd5e1', fontSize: '0.9rem', fontWeight: 600, marginBottom: '0.5rem' }}>
                Operating System
              </label>
              <select
                value={os}
                onChange={(e) => setOs(e.target.value)}
                style={{
                  width: '100%',
                  padding: '0.75rem',
                  background: '#0f172a',
                  border: '1px solid #475569',
                  borderRadius: 8,
                  color: '#e2e8f0',
                }}
              >
                <option value="Linux">Linux</option>
                <option value="Windows">Windows</option>
                <option value="RHEL">RHEL</option>
                <option value="SUSE">SUSE</option>
              </select>
            </div>
            <div>
              <label style={{ display: 'block', color: '#cbd5e1', fontSize: '0.9rem', fontWeight: 600, marginBottom: '0.5rem' }}>
                Tenancy
              </label>
              <select
                value={tenancy}
                onChange={(e) => setTenancy(e.target.value)}
                style={{
                  width: '100%',
                  padding: '0.75rem',
                  background: '#0f172a',
                  border: '1px solid #475569',
                  borderRadius: 8,
                  color: '#e2e8f0',
                }}
              >
                <option value="default">Default</option>
                <option value="shared">Shared</option>
                <option value="dedicated">Dedicated</option>
                <option value="host">Dedicated Host</option>
              </select>
            </div>
          </div>

          {analysisMode === 'simple' && (
            <div style={{ marginBottom: '1.5rem' }}>
              <label style={{ display: 'block', color: '#cbd5e1', fontSize: '0.9rem', fontWeight: 600, marginBottom: '0.5rem' }}>
                Current Hourly Cost ($)
              </label>
              <input
                type="number"
                value={currentCost}
                onChange={(e) => setCurrentCost(e.target.value)}
                step="0.001"
                min="0"
                style={{
                  width: '100%',
                  padding: '0.75rem',
                  background: '#0f172a',
                  border: '1px solid #475569',
                  borderRadius: 8,
                  color: '#e2e8f0',
                }}
                placeholder="0.5"
              />
            </div>
          )}

          {analysisMode === 'advanced' && (
            <>
              <div style={{ marginBottom: '1.5rem' }}>
                <label style={{ display: 'block', color: '#cbd5e1', fontSize: '0.9rem', fontWeight: 600, marginBottom: '0.5rem' }}>
                  Model Type
                </label>
                <select
                  value={selectedType}
                  onChange={(e) => setSelectedType(e.target.value)}
                  disabled={modelTypes.length === 0}
                  style={{
                    width: '100%',
                    padding: '0.75rem',
                    background: '#0f172a',
                    border: '1px solid #475569',
                    borderRadius: 8,
                    color: '#e2e8f0',
                  }}
                >
                  {modelTypes.length === 0 && <option>Loading model types...</option>}
                  {modelTypes.map((t: ModelType) => (
                    <option key={t.type} value={t.type}>
                      {t.type} ({t.count} model{t.count !== 1 ? 's' : ''})
                    </option>
                  ))}
                </select>
                {typeDetails && typeDetails.best_model && (
                  <small style={{ display: 'block', color: '#94a3b8', marginTop: '0.5rem', fontSize: '0.8rem' }}>
                    Best: {typeDetails.best_model.name} v{typeDetails.best_model.version} | R²: {typeDetails.best_model.r_squared?.toFixed(4) ?? 'N/A'} | MAPE: {typeDetails.best_model.mape?.toFixed(2)}%
                  </small>
                )}
              </div>

              <div style={{ marginBottom: '1.5rem' }}>
                <label style={{ display: 'block', color: '#cbd5e1', fontSize: '0.9rem', fontWeight: 600, marginBottom: '0.5rem' }}>
                  Term Length (months)
                </label>
                <input
                  type="number"
                  value={termLength}
                  onChange={(e) => setTermLength(e.target.value)}
                  step="1"
                  min="0"
                  style={{
                    width: '100%',
                    padding: '0.75rem',
                    background: '#0f172a',
                    border: '1px solid #475569',
                    borderRadius: 8,
                    color: '#e2e8f0',
                  }}
                  placeholder="e.g., 12, 36"
                />
              </div>

              <div style={{ marginBottom: '1.5rem' }}>
                <label style={{ display: 'block', color: '#cbd5e1', fontSize: '0.9rem', fontWeight: 600, marginBottom: '0.75rem' }}>
                  Payment Options
                </label>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  <label style={{ display: 'flex', alignItems: 'center', color: '#cbd5e1', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={isAllUpfront}
                      onChange={(e) => setIsAllUpfront(e.target.checked)}
                      style={{ marginRight: '0.5rem', cursor: 'pointer' }}
                    />
                    All Upfront
                  </label>
                  <label style={{ display: 'flex', alignItems: 'center', color: '#cbd5e1', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={isPartialUpfront}
                      onChange={(e) => setIsPartialUpfront(e.target.checked)}
                      style={{ marginRight: '0.5rem', cursor: 'pointer' }}
                    />
                    Partial Upfront
                  </label>
                  <label style={{ display: 'flex', alignItems: 'center', color: '#cbd5e1', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={isNoUpfront}
                      onChange={(e) => setIsNoUpfront(e.target.checked)}
                      style={{ marginRight: '0.5rem', cursor: 'pointer' }}
                    />
                    No Upfront
                  </label>
                </div>
              </div>

              <div style={{ marginBottom: '1.5rem' }}>
                <label style={{ display: 'block', color: '#cbd5e1', fontSize: '0.9rem', fontWeight: 600, marginBottom: '0.5rem' }}>
                  Additional Parameters
                </label>
                {additionalParams.map((param, idx) => (
                  <div key={idx} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr auto', gap: '0.5rem', marginBottom: '0.5rem' }}>
                    <input
                      type="text"
                      placeholder="Parameter name"
                      value={param.key}
                      onChange={(e) => updateParam(idx, 'key', e.target.value)}
                      style={{
                        padding: '0.5rem',
                        background: '#0f172a',
                        border: '1px solid #475569',
                        borderRadius: 6,
                        color: '#e2e8f0',
                      }}
                    />
                    <input
                      type="text"
                      placeholder="Value"
                      value={param.value}
                      onChange={(e) => updateParam(idx, 'value', e.target.value)}
                      style={{
                        padding: '0.5rem',
                        background: '#0f172a',
                        border: '1px solid #475569',
                        borderRadius: 6,
                        color: '#e2e8f0',
                      }}
                    />
                    <button
                      onClick={() => removeParam(idx)}
                      style={{
                        padding: '0.5rem 1rem',
                        background: '#7f1d1d',
                        color: '#fecaca',
                        border: 'none',
                        borderRadius: 6,
                        cursor: 'pointer',
                      }}
                    >
                      Remove
                    </button>
                  </div>
                ))}
                <button
                  onClick={addParam}
                  style={{
                    width: '100%',
                    padding: '0.5rem',
                    background: '#334155',
                    color: '#cbd5e1',
                    border: 'none',
                    borderRadius: 6,
                    cursor: 'pointer',
                    marginTop: '0.5rem',
                  }}
                >
                  + Add Parameter
                </button>
              </div>
            </>
          )}

          <button
            onClick={handleAnalyze}
            disabled={loading}
            style={{
              width: '100%',
              padding: '0.875rem',
              background: loading ? '#4b5563' : 'linear-gradient(180deg, #3b82f6, #2563eb)',
              color: 'white',
              border: 'none',
              borderRadius: 10,
              cursor: loading ? 'not-allowed' : 'pointer',
              fontWeight: 600,
              transition: 'all 0.2s',
            }}
          >
            {loading ? 'Analyzing...' : analysisMode === 'simple' ? 'Analyze Cost' : 'Get Prediction'}
          </button>

          {error && (
            <div style={{
              marginTop: '1rem',
              padding: '0.75rem 1rem',
              background: '#7f1d1d',
              color: '#fecaca',
              borderRadius: 8,
              fontSize: '0.9rem',
            }}>
              {error}
            </div>
          )}
        </div>

        {/* Results */}
        <div style={{ background: '#1e293b', padding: '2rem', borderRadius: 12, border: '1px solid #334155' }}>
          <h3 style={{ color: '#f1f5f9', marginTop: 0 }}>Analysis Results</h3>



          {predictions.length > 0 && (
            <div>
              {analysisMode === 'simple' && (
                <div style={{ color: '#94a3b8', fontSize: '0.9rem', marginBottom: '1rem' }}>
                  Current Cost: ${formatPrice(parseFloat(currentCost))}/hour
                </div>
              )}

              {predictions.map((pred, idx) => {
                const diff = analysisMode === 'simple' ? pred.predicted_price - parseFloat(currentCost) : 0
                const isCheaper = analysisMode === 'simple' && diff < 0

                return (
                  <div
                    key={idx}
                    style={{
                      padding: '1rem',
                      background: '#0f172a',
                      border: analysisMode === 'simple' ? `2px solid ${isCheaper ? '#10b981' : '#ef4444'}` : '2px solid #475569',
                      borderRadius: 8,
                      marginBottom: '0.75rem',
                    }}
                  >
                    {analysisMode === 'advanced' && (
                      <>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                          <div>
                            <div style={{ color: '#e2e8f0', fontWeight: 600 }}>
                              {pred.model_type ? pred.model_type.replace(/_/g, ' ') : pred.model_name || 'Prediction'}
                            </div>
                            <div style={{ color: '#64748b', fontSize: '0.85rem' }}>
                              {pred.engine_version}
                            </div>
                          </div>
                          <div style={{ textAlign: 'right' }}>
                            <div style={{ color: getPredictionColor(pred.predicted_price, parseFloat(currentCost)), fontSize: '1.35rem', fontWeight: 700 }}>
                              ${formatPrice(pred.predicted_price)}
                            </div>
                          </div>
                        </div>
                        
                        {pred.input_specs && (
                          <div style={{
                            paddingTop: '0.75rem',
                            borderTop: '1px solid #334155',
                            marginBottom: '0.75rem',
                            fontSize: '0.85rem',
                            color: '#cbd5e1',
                          }}>
                            <div style={{ marginBottom: '0.35rem' }}>
                              <span style={{ color: '#94a3b8' }}>Config:</span> {pred.input_specs.vcpu}x vCPU, {pred.input_specs.memory}GB RAM, {pred.input_specs.region}, {pred.input_specs.os}
                            </div>
                            {typeof pred.r_squared === 'number' && (
                              <div style={{ color: '#94a3b8', fontSize: '0.8rem', marginBottom: '0.35rem' }}>
                                Model R²: {pred.r_squared.toFixed(4)} | MAPE: {pred.mape?.toFixed(2)}%
                              </div>
                            )}
                            {pred.timestamp_created && (
                              <div style={{ color: '#94a3b8', fontSize: '0.8rem' }}>
                                Trained: {new Date(pred.timestamp_created).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                              </div>
                            )}
                            {pred.created_at && (
                              <div style={{ color: '#94a3b8', fontSize: '0.8rem' }}>
                                Registered: {new Date(pred.created_at).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                              </div>
                            )}
                          </div>
                        )}
                      </>
                    )}

                    {analysisMode === 'simple' && pred.actual_pricing_options && pred.actual_pricing_options.length > 0 && (
                      <div style={{
                        paddingTop: '0.75rem',
                        borderTop: '1px solid #334155',
                        marginBottom: '0.75rem',
                      }}>
                        <div style={{ color: '#a7f3d0', fontSize: '0.8rem', fontWeight: 600, marginBottom: '0.5rem' }}>
                          Available Options from Database:
                        </div>
                        {pred.actual_pricing_options.map((option, optIdx) => (
                          <div key={optIdx} style={{
                            background: '#1e293b',
                            padding: '0.75rem',
                            borderRadius: 6,
                            marginBottom: '0.75rem',
                            fontSize: '0.8rem',
                            border: '1px solid #475569',
                          }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem', alignItems: 'flex-start' }}>
                              <div style={{ flex: 1 }}>
                                <div style={{ color: '#cbd5e1', fontWeight: 700, marginBottom: '0.25rem' }}>
                                  {option.instance_type}
                                </div>
                                <div style={{ color: '#94a3b8', fontSize: '0.75rem', marginBottom: '0.25rem' }}>
                                  {option.service && `Service: ${option.service}`}
                                  {option.service && option.provider && ' • '}
                                  {option.provider && `${option.provider.toUpperCase()}`}
                                </div>
                                <div style={{ color: '#cbd5e1', fontSize: '0.8rem' }}>
                                  {option.vcpu}x vCPU • {option.memory}GB RAM
                                </div>
                              </div>
                              <div style={{ textAlign: 'right' }}>
                                <div style={{ color: '#22d3ee', fontWeight: 700, fontSize: '1rem', marginBottom: '0.25rem' }}>
                                  ${formatPrice(option.price)}
                                </div>
                                <div style={{ color: '#94a3b8', fontSize: '0.7rem' }}>per hour</div>
                              </div>
                            </div>
                            <div style={{ 
                              display: 'grid', 
                              gridTemplateColumns: '1fr 1fr', 
                              gap: '0.5rem',
                              borderTop: '1px solid #334155',
                              paddingTop: '0.5rem',
                              marginTop: '0.5rem',
                              color: '#94a3b8',
                              fontSize: '0.75rem'
                            }}>
                              <div><span style={{ color: '#cbd5e1', fontWeight: 600 }}>Region:</span> {option.region}</div>
                              <div><span style={{ color: '#cbd5e1', fontWeight: 600 }}>OS:</span> {option.os}</div>
                              <div><span style={{ color: '#cbd5e1', fontWeight: 600 }}>Tenancy:</span> {option.tenancy || 'default'}</div>
                              <div><span style={{ color: '#cbd5e1', fontWeight: 600 }}>Family:</span> {option.product_family}</div>
                            </div>
                            {option.description && (
                              <div style={{
                                color: '#64748b',
                                fontSize: '0.75rem',
                                marginTop: '0.5rem',
                                paddingTop: '0.5rem',
                                borderTop: '1px solid #334155',
                                fontStyle: 'italic'
                              }}>
                                {option.description}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                    
                    {analysisMode === 'simple' && isCheaper && (
                      <div style={{
                        paddingTop: '0.5rem',
                        borderTop: '1px solid #334155',
                        color: '#22c55e',
                        fontSize: '0.8rem',
                      }}>
                        Save ${formatPrice(Math.abs(diff))} per hour
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}

          {!loading && predictions.length === 0 && !error && (
            <div style={{ color: '#64748b', textAlign: 'center', paddingTop: '2rem' }}>
              {analysisMode === 'simple'
                ? 'Enter your setup and click "Analyze Cost" to find optimization opportunities'
                : 'Enter your specifications and click "Get Prediction" to see pricing estimates'}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
