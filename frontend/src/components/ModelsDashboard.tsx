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
        <h1 className="page-header-title">Model Comparison Dashboard</h1>
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
