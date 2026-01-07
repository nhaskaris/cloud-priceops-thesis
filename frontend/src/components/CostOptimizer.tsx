import { useState } from 'react'
import './CostOptimizer.css'

type PredictionResult = {
  engine_version: string
  predicted_price: number
  currency: string
  model_type?: string
  model_name?: string
  r_squared?: number | null
  mape?: number
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

const BACKEND_URL = (import.meta.env.VITE_APP_BACKEND_URL as string) || 'http://localhost:8000'

export default function CostOptimizer() {
  const [vcpu, setVcpu] = useState<string>('4')
  const [memory, setMemory] = useState<string>('16')
  const [region, setRegion] = useState<string>('us-east-1')
  const [os, setOs] = useState<string>('Linux')
  const [tenancy, setTenancy] = useState<string>('default')
  const [currentCost, setCurrentCost] = useState<string>('0.5')
  
  const [predictions, setPredictions] = useState<PredictionResult[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [savings, setSavings] = useState<{ type: string; percentage: number; amount: number } | null>(null)

  const handleOptimize = async () => {
    if (!vcpu || !memory || !region || !currentCost) {
      setError('Please fill in all fields')
      return
    }

    setLoading(true)
    setError(null)
    setPredictions([])
    setSavings(null)

    try {
      // Fetch available model types to find the best one
      const typesRes = await fetch(`${BACKEND_URL}/engines/types/`)
      if (!typesRes.ok) throw new Error('Failed to fetch model types')
      const typesData = await typesRes.json()
      
      if (!Array.isArray(typesData) || typesData.length === 0) {
        setError('No models available. Please register a model first.')
        return
      }

      // Find the best model type based on R² score
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
        domain_label: 'iaas',  // Filter to IaaS only
      }

      // Get prediction from the best model only
      const response = await fetch(`${BACKEND_URL}/engines/predict-by-type/${bestModelType.type}/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(specs),
      })

      if (!response.ok) {
        setError('Could not get prediction from the best model')
        return
      }

      const prediction = await response.json()
      setPredictions([prediction])

      // Calculate savings
      const currentCostNum = parseFloat(currentCost)
      if (prediction.predicted_price < currentCostNum) {
        const savingsAmount = currentCostNum - prediction.predicted_price
        const savingsPercent = (savingsAmount / currentCostNum) * 100
        setSavings({
          type: prediction.model_type || 'Best Match',
          percentage: savingsPercent,
          amount: savingsAmount,
        })
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to analyze costs')
    } finally {
      setLoading(false)
    }
  }

  const getPredictionColor = (predicted: number, current: number) => {
    if (predicted < current) return '#22c55e' // green
    if (predicted > current) return '#ef4444' // red
    return '#94a3b8' // gray
  }

  // Format price based on cost type - hourly rates can have many decimals
  const formatPrice = (price: number) => {
    // For hourly rates, show up to 6 decimals, removing trailing zeros
    return price.toLocaleString('en-US', { 
      minimumFractionDigits: 0,
      maximumFractionDigits: 6 
    })
  }

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto' }}>
      <div className="page-header">
        <div className="page-header-breadcrumb">
          <svg width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
            <path d="M8 4.754a3.246 3.246 0 1 0 0 6.492 3.246 3.246 0 0 0 0-6.492zM5.754 8a2.246 2.246 0 1 1 4.492 0 2.246 2.246 0 0 1-4.492 0z"/>
            <path d="M9.796 1.343c-.527-1.79-3.065-1.79-3.592 0l-.094.319a.873.873 0 0 1-1.255.52l-.292-.16c-1.64-.892-3.433.902-2.54 2.541l.159.292a.873.873 0 0 1-.52 1.255l-.319.094c-1.79.527-1.79 3.065 0 3.592l.319.094a.873.873 0 0 1 .52 1.255l-.16.292c-.892 1.64.901 3.434 2.541 2.54l.292-.159a.873.873 0 0 1 1.255.52l.094.319c.527 1.79 3.065 1.79 3.592 0l.094-.319a.873.873 0 0 1 1.255-.52l.292.16c1.64.893 3.434-.902 2.54-2.541l-.159-.292a.873.873 0 0 1 .52-1.255l.319-.094c1.79-.527 1.79-3.065 0-3.592l-.319-.094a.873.873 0 0 1-.52-1.255l.16-.292c.893-1.64-.902-3.433-2.541-2.54l-.292.159a.873.873 0 0 1-1.255-.52l-.094-.319zm1.44-2.779a.873.873 0 0 0-1.54 0l-.094.319a1.873 1.873 0 0 1-2.693.11l-.291-.16a.873.873 0 0 0-1.55.26l-.159.292a1.873 1.873 0 0 1-2.693.91l-.291-.16a.873.873 0 0 0-1.55.26l-.094.319a.873.873 0 0 0 1.54.53l.094-.319a1.873 1.873 0 0 1 2.693-.11l.291.16a.873.873 0 0 0 1.55-.26l.159-.292a1.873 1.873 0 0 1 2.693-.91l.291.16a.873.873 0 0 0 1.55-.26l.094-.319a.873.873 0 0 0-.456-.802z"/>
          </svg>
          Optimization Tools
        </div>
        <h1 className="page-header-title">Cost Optimizer</h1>
        <p className="page-header-subtitle">Enter your current resource specs and hourly cost to find cheaper alternatives</p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem', marginBottom: '2rem' }}>
        {/* Input Form */}
        <div style={{ background: '#1e293b', padding: '2rem', borderRadius: 12, border: '1px solid #334155' }}>
          <h3 style={{ color: '#f1f5f9', marginTop: 0 }}>Your Current Setup</h3>

          <div style={{ marginBottom: '1.5rem' }}>
            <label style={{ display: 'block', color: '#cbd5e1', fontSize: '0.9rem', fontWeight: 600, marginBottom: '0.5rem' }}>
              vCPU Count
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
              Memory (GB)
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
                OS
              </label>
              <input
                type="text"
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
                placeholder="Linux"
              />
            </div>
            <div>
              <label style={{ display: 'block', color: '#cbd5e1', fontSize: '0.9rem', fontWeight: 600, marginBottom: '0.5rem' }}>
                Tenancy
              </label>
              <input
                type="text"
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
                placeholder="default"
              />
            </div>
          </div>

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

          <button
            onClick={handleOptimize}
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
            {loading ? 'Analyzing...' : 'Analyze Cost'}
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

          {savings && (
            <div style={{
              background: 'linear-gradient(135deg, #064e3b, #047857)',
              padding: '1.5rem',
              borderRadius: 10,
              marginBottom: '1.5rem',
              border: '1px solid #10b981',
            }}>
              <div style={{ color: '#a7f3d0', fontSize: '0.9rem', marginBottom: '0.5rem' }}>Potential Savings</div>
              <div style={{ color: '#f1f5f9', fontSize: '1.75rem', fontWeight: 700, marginBottom: '0.5rem' }}>
                {savings.percentage.toFixed(1)}% - ${formatPrice(savings.amount)}/hour
              </div>
              <div style={{ color: '#cbd5e1', fontSize: '0.85rem' }}>
                Using {savings.type} model
              </div>
            </div>
          )}

          {predictions.length > 0 && (
            <div>
              <div style={{ color: '#94a3b8', fontSize: '0.9rem', marginBottom: '1rem' }}>
                Current Cost: ${formatPrice(parseFloat(currentCost))}/hour
              </div>

              {predictions.map((pred, idx) => {
                const diff = pred.predicted_price - parseFloat(currentCost)
                const diffPercent = (diff / parseFloat(currentCost)) * 100
                const isCheaper = diff < 0

                return (
                  <div
                    key={idx}
                    style={{
                      padding: '1rem',
                      background: '#0f172a',
                      border: `2px solid ${isCheaper ? '#10b981' : '#ef4444'}`,
                      borderRadius: 8,
                      marginBottom: '0.75rem',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                      <div>
                        <div style={{ color: '#e2e8f0', fontWeight: 600 }}>
                          {pred.model_type ? pred.model_type.replace(/_/g, ' ') : 'Model ' + (idx + 1)}
                        </div>
                        <div style={{ color: '#64748b', fontSize: '0.85rem' }}>
                          {pred.engine_version}
                        </div>
                      </div>
                      <div style={{ textAlign: 'right' }}>
                        <div style={{ color: getPredictionColor(pred.predicted_price, parseFloat(currentCost)), fontSize: '1.35rem', fontWeight: 700 }}>
                          ${formatPrice(pred.predicted_price)}
                        </div>
                        <div style={{
                          color: isCheaper ? '#22c55e' : '#ef4444',
                          fontSize: '0.85rem',
                          fontWeight: 600,
                        }}>
                          {isCheaper ? '↓' : '↑'} {Math.abs(diffPercent).toFixed(1)}%
                        </div>
                      </div>
                    </div>
                    
                    {/* Specs Summary */}
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
                        {pred.r_squared !== null && pred.r_squared !== undefined && (
                          <div style={{ color: '#94a3b8', fontSize: '0.8rem' }}>
                            Model R²: {pred.r_squared.toFixed(4)} | MAPE: {pred.mape?.toFixed(2)}%
                          </div>
                        )}
                      </div>
                    )}

                    {/* Actual Pricing Options from DB */}
                    {pred.actual_pricing_options && pred.actual_pricing_options.length > 0 && (
                      <div style={{
                        paddingTop: '0.75rem',
                        borderTop: '1px solid #334155',
                        marginBottom: '0.75rem',
                      }}>
                        <div style={{ color: '#a7f3d0', fontSize: '0.8rem', fontWeight: 600, marginBottom: '0.5rem' }}>
                          Available Options from DB:
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
                    
                    {isCheaper && (
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
              Run analysis to see cost predictions
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
