import { useEffect, useMemo, useState } from 'react'

type EngineSummary = {
  id: string
  name: string
  model_type: string
  version: string
  r_squared?: number | null
  mape: number
  rmse?: number | null
  training_sample_size?: number | null
  is_active: boolean
  created_at: string
  updated_at: string
}

const BACKEND_URL = (import.meta.env.VITE_APP_BACKEND_URL as string) || 'http://localhost:8000'

export default function ModelsDashboard() {
  const [rows, setRows] = useState<EngineSummary[]>([])
  const [q, setQ] = useState('')
  const [sortKey, setSortKey] = useState<keyof EngineSummary>('created_at')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await fetch(`${BACKEND_URL}/engines/summary/`)
        const data = await res.json()
        setRows(Array.isArray(data) ? data : (data?.results ?? []))
      } catch (e) {
        console.error('Failed to fetch model summaries', e)
      }
    }
    fetchData()
  }, [])

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase()
    const base = needle
      ? rows.filter(r =>
          r.name.toLowerCase().includes(needle) ||
          r.model_type.toLowerCase().includes(needle) ||
          r.version.toLowerCase().includes(needle)
        )
      : rows
    const sorted = [...base].sort((a, b) => {
      const av = (a[sortKey] ?? '') as any
      const bv = (b[sortKey] ?? '') as any
      if (av === bv) return 0
      if (sortDir === 'asc') return av > bv ? 1 : -1
      return av < bv ? 1 : -1
    })
    return sorted
  }, [rows, q, sortKey, sortDir])

  const typeAgg = useMemo(() => {
    const acc: Record<string, { count: number; active: number; sumR2: number; r2n: number; sumMape: number; mapen: number }> = {}
    rows.forEach(r => {
      if (!acc[r.model_type]) acc[r.model_type] = { count: 0, active: 0, sumR2: 0, r2n: 0, sumMape: 0, mapen: 0 }
      const bucket = acc[r.model_type]
      bucket.count += 1
      if (r.is_active) bucket.active += 1
      if (typeof r.r_squared === 'number') {
        bucket.sumR2 += r.r_squared
        bucket.r2n += 1
      }
      if (typeof r.mape === 'number') {
        bucket.sumMape += r.mape
        bucket.mapen += 1
      }
    })
    return Object.entries(acc).map(([type, v]) => ({
      type,
      count: v.count,
      active: v.active,
      avgR2: v.r2n ? v.sumR2 / v.r2n : null,
      avgMape: v.mapen ? v.sumMape / v.mapen : null,
    }))
  }, [rows])

  const maxCount = typeAgg.reduce((m, t) => Math.max(m, t.count), 1)
  const maxR2 = typeAgg.reduce((m, t) => Math.max(m, t.avgR2 ?? 0), 0.0001)

  // Group models by type for detailed charts
  const modelsByType = useMemo(() => {
    const grouped: Record<string, EngineSummary[]> = {}
    rows.forEach(r => {
      if (!grouped[r.model_type]) grouped[r.model_type] = []
      grouped[r.model_type].push(r)
    })
    return grouped
  }, [rows])

  const hasMultipleTypes = Object.keys(modelsByType).length > 1

  // Prepare data for R² distribution by type
  const r2ByType = useMemo(() => {
    return rows
      .filter(r => typeof r.r_squared === 'number')
      .map(r => ({ type: r.model_type, r2: r.r_squared!, name: r.name }))
      .sort((a, b) => a.type.localeCompare(b.type))
  }, [rows])

  const maxR2Value = r2ByType.reduce((m, d) => Math.max(m, d.r2), 0.0001)

  const changeSort = (k: keyof EngineSummary) => {
    if (k === sortKey) setSortDir(sortDir === 'asc' ? 'desc' : 'asc')
    else {
      setSortKey(k)
      setSortDir('desc')
    }
  }

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto' }}>
      <div className="page-header">
        <div className="page-header-breadcrumb">
          <svg width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
            <path d="M2.5 8a5.5 5.5 0 0 1 8.25-4.764.5.5 0 0 0 .5-.866A6.5 6.5 0 1 0 14.5 8a.5.5 0 0 0-1 0 5.5 5.5 0 1 1-11 0z"/>
            <path d="M15.354 3.354a.5.5 0 0 0-.708-.708L8 9.293 5.354 6.646a.5.5 0 1 0-.708.708l3 3a.5.5 0 0 0 .708 0l7-7z"/>
          </svg>
          Analytics / Models
        </div>
        <p className="page-header-subtitle">Browse and compare all registered prediction engines by performance metrics. Sort by clicking column headers.</p>
      </div>

      {/* Quick Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }} className="animate-slide-up animate-delay-1">
        <div style={{ background: '#1e293b', padding: '1rem', borderRadius: 8, border: '1px solid #334155' }}>
          <div style={{ color: '#94a3b8', fontSize: '0.875rem', marginBottom: '0.25rem' }}>Total Models</div>
          <div style={{ color: '#f1f5f9', fontSize: '1.75rem', fontWeight: 700 }}>{rows.length}</div>
        </div>
        <div style={{ background: '#1e293b', padding: '1rem', borderRadius: 8, border: '1px solid #334155' }}>
          <div style={{ color: '#94a3b8', fontSize: '0.875rem', marginBottom: '0.25rem' }}>Active Models</div>
          <div style={{ color: '#60a5fa', fontSize: '1.75rem', fontWeight: 700 }}>{rows.filter(r => r.is_active).length}</div>
        </div>
        <div style={{ background: '#1e293b', padding: '1rem', borderRadius: 8, border: '1px solid #334155' }}>
          <div style={{ color: '#94a3b8', fontSize: '0.875rem', marginBottom: '0.25rem' }}>Model Types</div>
          <div style={{ color: '#f1f5f9', fontSize: '1.75rem', fontWeight: 700 }}>{new Set(rows.map(r => r.model_type)).size}</div>
        </div>
      </div>

      {/* Mini charts */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
        <div style={{ background: '#1e293b', padding: '1rem', borderRadius: 8, border: '1px solid #334155' }}>
          <div style={{ color: '#94a3b8', fontSize: '0.875rem', marginBottom: '0.35rem' }}>Models by Type</div>
          {typeAgg.length === 0 && <div style={{ color: '#94a3b8', fontSize: '0.9rem' }}>No data yet.</div>}
          {typeAgg.map(t => (
            <div key={t.type} style={{ marginBottom: '0.5rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.9rem', color: '#e2e8f0' }}>
                <span>{t.type}</span>
                <span>{t.count}</span>
              </div>
              <div style={{ background: '#0f172a', borderRadius: 6, height: 10, overflow: 'hidden', border: '1px solid #334155' }}>
                <div style={{ height: '100%', width: `${(t.count / maxCount) * 100}%`, background: 'linear-gradient(90deg, #60a5fa, #2563eb)' }} />
              </div>
            </div>
          ))}
        </div>
        <div style={{ background: '#1e293b', padding: '1rem', borderRadius: 8, border: '1px solid #334155' }}>
          <div style={{ color: '#94a3b8', fontSize: '0.875rem', marginBottom: '0.35rem' }}>Average R² by Type</div>
          {typeAgg.length === 0 && <div style={{ color: '#94a3b8', fontSize: '0.9rem' }}>No data yet.</div>}
          {typeAgg.map(t => (
            <div key={t.type} style={{ marginBottom: '0.5rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.9rem', color: '#e2e8f0' }}>
                <span>{t.type}</span>
                <span>{t.avgR2 == null ? '—' : t.avgR2.toFixed(3)}</span>
              </div>
              <div style={{ background: '#0f172a', borderRadius: 6, height: 10, overflow: 'hidden', border: '1px solid #334155' }}>
                <div style={{ height: '100%', width: `${((t.avgR2 ?? 0) / maxR2) * 100}%`, background: 'linear-gradient(90deg, #22d3ee, #0ea5e9)' }} />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* R² Distribution by Type - Show if multiple types exist */}
      {hasMultipleTypes && r2ByType.length > 0 && (
        <div style={{ background: '#1e293b', padding: '1.5rem', borderRadius: 8, border: '1px solid #334155', marginBottom: '1.5rem' }}>
          <h3 style={{ color: '#f1f5f9', margin: '0 0 1rem 0', fontSize: '1.125rem' }}>R² Distribution by Model Type</h3>
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: '0.5rem', height: 180, padding: '0.5rem 0' }}>
            {r2ByType.map((d, i) => (
              <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', alignItems: 'center', minWidth: 0 }}>
                <div 
                  style={{ 
                    width: '100%', 
                    background: d.type === 'ridge_regression' ? 'linear-gradient(180deg, #60a5fa, #2563eb)' : 
                               d.type === 'hedonic_regression' ? 'linear-gradient(180deg, #22d3ee, #0ea5e9)' : 
                               'linear-gradient(180deg, #a78bfa, #7c3aed)',
                    borderRadius: '4px 4px 0 0',
                    height: `${(d.r2 / maxR2Value) * 100}%`,
                    minHeight: d.r2 > 0 ? '4px' : '0',
                    position: 'relative',
                    transition: 'all 0.2s ease'
                  }}
                  title={`${d.name}: ${d.r2.toFixed(4)}`}
                >
                  <div style={{ 
                    position: 'absolute', 
                    top: '-1.25rem', 
                    left: '50%', 
                    transform: 'translateX(-50%)', 
                    fontSize: '0.7rem', 
                    color: '#94a3b8',
                    whiteSpace: 'nowrap',
                    opacity: 0.8
                  }}>
                    {d.r2.toFixed(3)}
                  </div>
                </div>
                <div style={{ 
                  fontSize: '0.7rem', 
                  color: '#cbd5e1', 
                  marginTop: '0.5rem', 
                  textAlign: 'center',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  width: '100%'
                }} title={d.name}>
                  {d.name.length > 10 ? d.name.substring(0, 8) + '…' : d.name}
                </div>
                <div style={{ fontSize: '0.65rem', color: '#64748b', textAlign: 'center' }}>
                  {d.type.replace('_', ' ')}
                </div>
              </div>
            ))}
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '0.5rem', fontSize: '0.75rem', color: '#64748b', paddingTop: '0.5rem', borderTop: '1px solid #334155' }}>
            <span>Models by type & R²</span>
            <span>Max: {maxR2Value.toFixed(4)}</span>
          </div>
        </div>
      )}

      {/* Per-Type Breakdown - Show if multiple types */}
      {hasMultipleTypes && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
          {Object.entries(modelsByType).map(([type, models]) => {
            const withR2 = models.filter(m => typeof m.r_squared === 'number')
            const avgR2 = withR2.length > 0 ? withR2.reduce((s, m) => s + m.r_squared!, 0) / withR2.length : null
            const avgMape = models.filter(m => typeof m.mape === 'number').reduce((s, m, _, arr) => s + m.mape / arr.length, 0)
            
            return (
              <div key={type} style={{ background: '#1e293b', padding: '1rem', borderRadius: 8, border: '1px solid #334155' }}>
                <div style={{ fontSize: '0.95rem', fontWeight: 700, color: '#60a5fa', marginBottom: '0.75rem', textTransform: 'capitalize' }}>
                  {type.replace(/_/g, ' ')}
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', marginBottom: '0.75rem' }}>
                  <div>
                    <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Count</div>
                    <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#e2e8f0' }}>{models.length}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Active</div>
                    <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#22d3ee' }}>{models.filter(m => m.is_active).length}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Avg R²</div>
                    <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#e2e8f0' }}>{avgR2 == null ? '—' : avgR2.toFixed(3)}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Avg MAPE</div>
                    <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#e2e8f0' }}>{avgMape ? avgMape.toFixed(2) + '%' : '—'}</div>
                  </div>
                </div>
                <div style={{ fontSize: '0.7rem', color: '#64748b', borderTop: '1px solid #334155', paddingTop: '0.5rem' }}>
                  {models.slice(0, 3).map(m => m.name).join(', ')}
                  {models.length > 3 && ` +${models.length - 3} more`}
                </div>
              </div>
            )
          })}
        </div>
      )}

      <div style={{ margin: '1rem 0' }}>
        <input
          placeholder="Search by name, type or version"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          style={{ padding: '0.5rem', border: '1px solid #475569', borderRadius: 6, width: '100%', maxWidth: 420, background: '#0f172a', color: '#e2e8f0' }}
        />
      </div>

      <div style={{ overflowX: 'auto', background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }}>
        <table className="results" style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th onClick={() => changeSort('name')} style={{ cursor: 'pointer', userSelect: 'none' }}>Name</th>
              <th onClick={() => changeSort('model_type')} style={{ cursor: 'pointer', userSelect: 'none' }}>Type</th>
              <th onClick={() => changeSort('version')} style={{ cursor: 'pointer', userSelect: 'none' }}>Version</th>
              <th onClick={() => changeSort('r_squared')} style={{ cursor: 'pointer', userSelect: 'none' }}>R²</th>
              <th onClick={() => changeSort('mape')} style={{ cursor: 'pointer', userSelect: 'none' }}>MAPE (%)</th>
              <th onClick={() => changeSort('rmse')} style={{ cursor: 'pointer', userSelect: 'none' }}>RMSE</th>
              <th onClick={() => changeSort('training_sample_size')} style={{ cursor: 'pointer', userSelect: 'none' }}>Samples</th>
              <th onClick={() => changeSort('is_active')} style={{ cursor: 'pointer', userSelect: 'none' }}>Active</th>
              <th onClick={() => changeSort('created_at')} style={{ cursor: 'pointer', userSelect: 'none' }}>Created</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(r => (
              <tr key={r.id}>
                <td>{r.name}</td>
                <td>{r.model_type}</td>
                <td>{r.version}</td>
                <td>{r.r_squared == null ? '—' : r.r_squared.toFixed(4)}</td>
                <td>{r.mape?.toFixed?.(2)}</td>
                <td>{r.rmse == null ? '—' : r.rmse.toFixed(4)}</td>
                <td>{r.training_sample_size ?? '—'}</td>
                <td>{r.is_active ? 'Yes' : 'No'}</td>
                <td>{new Date(r.created_at).toLocaleString()}</td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={9} style={{ textAlign: 'center', padding: '1rem', color: '#94a3b8' }}>No models found.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
