import { useEffect, useState } from 'react'

type Coefficient = {
  feature_name: string
  value: number
  p_value?: number | null
}

type ModelDetail = {
  id: string
  name: string
  model_type: string
  version: string
  r_squared?: number | null
  mape: number
  coefficients?: Coefficient[]
  feature_names?: string[]
}

const BACKEND_URL = (import.meta.env.VITE_APP_BACKEND_URL as string) || 'http://localhost:8000'

type Props = {
  modelId: string
  onClose: () => void
}

export default function ModelCoefficients({ modelId, onClose }: Props) {
  const [model, setModel] = useState<ModelDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [sortBy, setSortBy] = useState<'name' | 'value' | 'p_value'>('value')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')

  useEffect(() => {
    const fetchModel = async () => {
      try {
        setLoading(true)
        const res = await fetch(`${BACKEND_URL}/engines/${modelId}/`)
        const data = await res.json()
        setModel(data)
      } catch (e) {
        console.error('Failed to fetch model details', e)
      } finally {
        setLoading(false)
      }
    }
    fetchModel()
  }, [modelId])

  if (loading) {
    return (
      <div style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0, 0, 0, 0.8)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
      }}>
        <div style={{
          background: '#1e293b',
          border: '1px solid #334155',
          borderRadius: 8,
          padding: '2rem',
          color: '#94a3b8'
        }}>
          Loading model details...
        </div>
      </div>
    )
  }

  if (!model) {
    return (
      <div style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0, 0, 0, 0.8)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
      }} onClick={onClose}>
        <div style={{
          background: '#1e293b',
          border: '1px solid #334155',
          borderRadius: 8,
          padding: '2rem',
          color: '#f87171'
        }}>
          Failed to load model
        </div>
      </div>
    )
  }

  const coefficients = model.coefficients || []
  const hasCoefficients = coefficients.length > 0

  // Sort coefficients
  const sortedCoefficients = [...coefficients].sort((a, b) => {
    let av: number | string = 0
    let bv: number | string = 0

    if (sortBy === 'name') {
      av = a.feature_name
      bv = b.feature_name
    } else if (sortBy === 'value') {
      av = Math.abs(a.value)
      bv = Math.abs(b.value)
    } else if (sortBy === 'p_value') {
      av = a.p_value ?? Infinity
      bv = b.p_value ?? Infinity
    }

    if (av === bv) return 0
    if (sortDir === 'asc') return av > bv ? 1 : -1
    return av < bv ? 1 : -1
  })

  const maxAbsValue = Math.max(...coefficients.map(c => Math.abs(c.value)), 0.0001)

  const toggleSort = (key: 'name' | 'value' | 'p_value') => {
    if (sortBy === key) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc')
    } else {
      setSortBy(key)
      setSortDir(key === 'p_value' ? 'asc' : 'desc') // p-value: smaller is better
    }
  }

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0, 0, 0, 0.85)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
        padding: '2rem',
        overflow: 'auto'
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: '#0f172a',
          border: '1px solid #334155',
          borderRadius: 12,
          maxWidth: 1200,
          width: '100%',
          maxHeight: '90vh',
          overflow: 'auto',
          boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.5)'
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{
          padding: '1.5rem',
          borderBottom: '1px solid #334155',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          background: '#1e293b'
        }}>
          <div>
            <h2 style={{ margin: 0, color: '#f1f5f9', fontSize: '1.5rem', marginBottom: '0.5rem' }}>
              {model.name} <span style={{ color: '#94a3b8', fontSize: '1rem', fontWeight: 400 }}>v{model.version}</span>
            </h2>
            <div style={{ display: 'flex', gap: '1rem', fontSize: '0.875rem', color: '#94a3b8' }}>
              <span>Type: <strong style={{ color: '#60a5fa' }}>{model.model_type}</strong></span>
              {model.r_squared != null && <span>R²: <strong style={{ color: '#22c55e' }}>{model.r_squared.toFixed(4)}</strong></span>}
              <span>MAPE: <strong style={{ color: '#fbbf24' }}>{model.mape.toFixed(2)}%</strong></span>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: '1px solid #475569',
              borderRadius: 6,
              color: '#cbd5e1',
              cursor: 'pointer',
              padding: '0.5rem 1rem',
              fontSize: '0.875rem',
              transition: 'all 0.2s'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = '#334155'
              e.currentTarget.style.borderColor = '#64748b'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'transparent'
              e.currentTarget.style.borderColor = '#475569'
            }}
          >
            Close
          </button>
        </div>

        {/* Content */}
        <div style={{ padding: '1.5rem' }}>
          {!hasCoefficients ? (
            <div style={{
              padding: '3rem',
              textAlign: 'center',
              color: '#94a3b8',
              background: '#1e293b',
              borderRadius: 8,
              border: '1px solid #334155'
            }}>
              <div style={{ fontSize: '2.5rem', marginBottom: '1rem' }}>📊</div>
              <div style={{ fontSize: '1.125rem', marginBottom: '0.5rem', color: '#cbd5e1' }}>
                No Coefficients Available
              </div>
              <div style={{ fontSize: '0.875rem' }}>
                This model doesn't have coefficient data stored. Coefficients are typically available for linear regression and hedonic models.
              </div>
            </div>
          ) : (
            <>
              {/* Summary Stats */}
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                gap: '1rem',
                marginBottom: '1.5rem'
              }}>
                <div style={{ background: '#1e293b', padding: '1rem', borderRadius: 8, border: '1px solid #334155' }}>
                  <div style={{ color: '#94a3b8', fontSize: '0.75rem', marginBottom: '0.25rem' }}>Total Features</div>
                  <div style={{ color: '#f1f5f9', fontSize: '1.5rem', fontWeight: 700 }}>{coefficients.length}</div>
                </div>
                <div style={{ background: '#1e293b', padding: '1rem', borderRadius: 8, border: '1px solid #334155' }}>
                  <div style={{ color: '#94a3b8', fontSize: '0.75rem', marginBottom: '0.25rem' }}>Significant (p &lt; 0.05)</div>
                  <div style={{ color: '#22c55e', fontSize: '1.5rem', fontWeight: 700 }}>
                    {coefficients.filter(c => c.p_value != null && c.p_value < 0.05).length}
                  </div>
                </div>
                <div style={{ background: '#1e293b', padding: '1rem', borderRadius: 8, border: '1px solid #334155' }}>
                  <div style={{ color: '#94a3b8', fontSize: '0.75rem', marginBottom: '0.25rem' }}>Positive Impact</div>
                  <div style={{ color: '#60a5fa', fontSize: '1.5rem', fontWeight: 700 }}>
                    {coefficients.filter(c => c.value > 0).length}
                  </div>
                </div>
                <div style={{ background: '#1e293b', padding: '1rem', borderRadius: 8, border: '1px solid #334155' }}>
                  <div style={{ color: '#94a3b8', fontSize: '0.75rem', marginBottom: '0.25rem' }}>Negative Impact</div>
                  <div style={{ color: '#f87171', fontSize: '1.5rem', fontWeight: 700 }}>
                    {coefficients.filter(c => c.value < 0).length}
                  </div>
                </div>
              </div>

              {/* Coefficient Visualization */}
              <div style={{
                background: '#1e293b',
                padding: '1.5rem',
                borderRadius: 8,
                border: '1px solid #334155',
                marginBottom: '1.5rem'
              }}>
                <h3 style={{ margin: '0 0 1rem 0', color: '#f1f5f9', fontSize: '1.125rem' }}>
                  Feature Impact (Shadow Prices)
                </h3>
                <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '1rem' }}>
                  Bars show relative magnitude. Green = positive impact on price, Red = negative impact.
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', maxHeight: 400, overflow: 'auto' }}>
                  {sortedCoefficients.slice(0, 20).map((coeff, i) => {
                    const absValue = Math.abs(coeff.value)
                    const barWidth = (absValue / maxAbsValue) * 100
                    const isSignificant = coeff.p_value != null && coeff.p_value < 0.05

                    return (
                      <div key={i} style={{ position: 'relative' }}>
                        <div style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          marginBottom: '0.25rem',
                          fontSize: '0.8rem'
                        }}>
                          <span style={{
                            color: isSignificant ? '#f1f5f9' : '#94a3b8',
                            fontWeight: isSignificant ? 600 : 400,
                            maxWidth: '50%',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap'
                          }}>
                            {coeff.feature_name}
                            {isSignificant && <span style={{ color: '#22c55e', marginLeft: '0.25rem' }}>*</span>}
                          </span>
                          <span style={{
                            color: coeff.value >= 0 ? '#22c55e' : '#f87171',
                            fontWeight: 600,
                            fontFamily: 'monospace'
                          }}>
                            {coeff.value >= 0 ? '+' : ''}{coeff.value.toFixed(4)}
                          </span>
                        </div>
                        <div style={{
                          background: '#0f172a',
                          height: 24,
                          borderRadius: 4,
                          overflow: 'hidden',
                          border: '1px solid #334155',
                          position: 'relative'
                        }}>
                          <div style={{
                            height: '100%',
                            width: `${barWidth}%`,
                            background: coeff.value >= 0
                              ? 'linear-gradient(90deg, #22c55e, #16a34a)'
                              : 'linear-gradient(90deg, #f87171, #dc2626)',
                            transition: 'width 0.3s ease',
                            display: 'flex',
                            alignItems: 'center',
                            paddingLeft: '0.5rem',
                            fontSize: '0.7rem',
                            color: 'white',
                            fontWeight: 600
                          }}>
                            {coeff.p_value != null && (
                              <span style={{ opacity: 0.9 }}>
                                p={coeff.p_value.toFixed(4)}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
                {coefficients.length > 20 && (
                  <div style={{
                    marginTop: '1rem',
                    padding: '0.75rem',
                    background: '#0f172a',
                    borderRadius: 6,
                    fontSize: '0.875rem',
                    color: '#94a3b8',
                    textAlign: 'center'
                  }}>
                    Showing top 20 of {coefficients.length} coefficients
                  </div>
                )}
              </div>

              {/* Coefficient Table */}
              <div style={{
                background: '#1e293b',
                borderRadius: 8,
                border: '1px solid #334155',
                overflow: 'hidden'
              }}>
                <h3 style={{
                  margin: 0,
                  padding: '1rem 1.5rem',
                  color: '#f1f5f9',
                  fontSize: '1.125rem',
                  borderBottom: '1px solid #334155',
                  background: '#1e293b'
                }}>
                  All Coefficients
                </h3>
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead>
                      <tr style={{ background: '#0f172a' }}>
                        <th
                          onClick={() => toggleSort('name')}
                          style={{
                            padding: '0.75rem 1rem',
                            textAlign: 'left',
                            color: '#cbd5e1',
                            fontSize: '0.875rem',
                            fontWeight: 600,
                            cursor: 'pointer',
                            userSelect: 'none',
                            borderBottom: '1px solid #334155'
                          }}
                        >
                          Feature {sortBy === 'name' && (sortDir === 'asc' ? '↑' : '↓')}
                        </th>
                        <th
                          onClick={() => toggleSort('value')}
                          style={{
                            padding: '0.75rem 1rem',
                            textAlign: 'right',
                            color: '#cbd5e1',
                            fontSize: '0.875rem',
                            fontWeight: 600,
                            cursor: 'pointer',
                            userSelect: 'none',
                            borderBottom: '1px solid #334155'
                          }}
                        >
                          Coefficient {sortBy === 'value' && (sortDir === 'asc' ? '↑' : '↓')}
                        </th>
                        <th
                          onClick={() => toggleSort('p_value')}
                          style={{
                            padding: '0.75rem 1rem',
                            textAlign: 'right',
                            color: '#cbd5e1',
                            fontSize: '0.875rem',
                            fontWeight: 600,
                            cursor: 'pointer',
                            userSelect: 'none',
                            borderBottom: '1px solid #334155'
                          }}
                        >
                          p-value {sortBy === 'p_value' && (sortDir === 'asc' ? '↑' : '↓')}
                        </th>
                        <th
                          style={{
                            padding: '0.75rem 1rem',
                            textAlign: 'center',
                            color: '#cbd5e1',
                            fontSize: '0.875rem',
                            fontWeight: 600,
                            borderBottom: '1px solid #334155'
                          }}
                        >
                          Significance
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {sortedCoefficients.map((coeff, i) => {
                        const isSignificant = coeff.p_value != null && coeff.p_value < 0.05
                        return (
                          <tr
                            key={i}
                            style={{
                              borderBottom: '1px solid #334155',
                              background: i % 2 === 0 ? '#1e293b' : '#0f172a'
                            }}
                          >
                            <td style={{
                              padding: '0.75rem 1rem',
                              color: isSignificant ? '#f1f5f9' : '#94a3b8',
                              fontSize: '0.875rem',
                              fontWeight: isSignificant ? 600 : 400
                            }}>
                              {coeff.feature_name}
                            </td>
                            <td style={{
                              padding: '0.75rem 1rem',
                              textAlign: 'right',
                              fontFamily: 'monospace',
                              fontSize: '0.875rem',
                              color: coeff.value >= 0 ? '#22c55e' : '#f87171',
                              fontWeight: 600
                            }}>
                              {coeff.value >= 0 ? '+' : ''}{coeff.value.toFixed(6)}
                            </td>
                            <td style={{
                              padding: '0.75rem 1rem',
                              textAlign: 'right',
                              fontFamily: 'monospace',
                              fontSize: '0.875rem',
                              color: isSignificant ? '#22c55e' : '#94a3b8',
                              fontWeight: isSignificant ? 600 : 400
                            }}>
                              {coeff.p_value != null ? coeff.p_value.toFixed(6) : '—'}
                            </td>
                            <td style={{
                              padding: '0.75rem 1rem',
                              textAlign: 'center',
                              fontSize: '0.875rem'
                            }}>
                              {isSignificant ? (
                                <span style={{
                                  background: '#22c55e',
                                  color: '#0f172a',
                                  padding: '0.25rem 0.5rem',
                                  borderRadius: 4,
                                  fontSize: '0.75rem',
                                  fontWeight: 700
                                }}>
                                  ***
                                </span>
                              ) : coeff.p_value != null && coeff.p_value < 0.1 ? (
                                <span style={{
                                  background: '#fbbf24',
                                  color: '#0f172a',
                                  padding: '0.25rem 0.5rem',
                                  borderRadius: 4,
                                  fontSize: '0.75rem',
                                  fontWeight: 700
                                }}>
                                  *
                                </span>
                              ) : (
                                <span style={{ color: '#475569' }}>—</span>
                              )}
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Legend */}
              <div style={{
                marginTop: '1rem',
                padding: '1rem',
                background: '#1e293b',
                borderRadius: 8,
                border: '1px solid #334155',
                fontSize: '0.75rem',
                color: '#94a3b8'
              }}>
                <div style={{ fontWeight: 600, marginBottom: '0.5rem', color: '#cbd5e1' }}>Legend:</div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.5rem' }}>
                  <div>*** = p &lt; 0.05 (Highly Significant)</div>
                  <div>* = p &lt; 0.1 (Marginally Significant)</div>
                  <div><span style={{ color: '#22c55e' }}>Green</span> = Positive impact on price</div>
                  <div><span style={{ color: '#f87171' }}>Red</span> = Negative impact on price</div>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
