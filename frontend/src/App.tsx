import React, { useState } from 'react'
import './App.css'
import ComparisonChart from './components/ComparisonChart'

type TCOResult = {
  provider: string
  region: string | null
  instance_type: string | null
  price_per_hour: number | null
  monthly_cost: number | null
  yearly_cost: number | null
}

function App() {
  const [resourceType, setResourceType] = useState<'cpu'|'gpu'|'memory'|'storage'|'generic'>('cpu')
  const [cpuHours, setCpuHours] = useState('720')
  const [duration, setDuration] = useState('12')
  const [regions, setRegions] = useState('')
  const [providers, setProviders] = useState({ aws: true, azure: true, gcp: true })
  const [results, setResults] = useState<TCOResult[] | null>(null)
  const [best, setBest] = useState<TCOResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // Frontend displays prices as USD only; no currency conversion

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setResults(null)
    setBest(null)

    const chosenProviders = Object.entries(providers)
      .filter(([, v]) => v)
      .map(([k]) => k)

    const payload = {
      resource_type: resourceType,
      cpu_hours_per_month: parseFloat(cpuHours),
      duration_months: parseInt(duration, 10),
      region_preferences: regions.split(',').map((r) => r.trim()).filter(Boolean),
      providers: chosenProviders,
    }

    try {
      const resp = await fetch('/api/v1/tco/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!resp.ok) {
        const txt = await resp.text()
        throw new Error(txt || resp.statusText)
      }
      const data = await resp.json()
      setResults(data.results || null)
      setBest(data.best || null)
    } catch (err: any) {
      setError(err.message || 'Request failed')
    } finally {
      setLoading(false)
    }
  }

  const formatCurrency = (v: number | null | undefined) => {
    if (v === null || v === undefined) return '-'
    // Prices are stored in USD and displayed as USD
    return `$${Number(v).toFixed(2)}`
  }

  return (
    <div className="App">
      <header className="App-header">
        <h1>CloudPricingOps — TCO Estimator (MVP)</h1>
      </header>
      <main>
        <form onSubmit={handleSubmit} className="form">
          <label>
            Resource type
            <select value={resourceType} onChange={(e) => setResourceType(e.target.value as any)}>
              <option value="cpu">CPU (general purpose)</option>
              <option value="gpu">GPU (accelerated)</option>
              <option value="memory">Memory-optimized</option>
              <option value="storage">Storage-optimized</option>
              <option value="generic">Generic / don't care</option>
            </select>
          </label>
          <label>
            CPU hours per month
            <input value={cpuHours} onChange={(e) => setCpuHours(e.target.value)} />
          </label>
          <label>
            Duration months
            <input value={duration} onChange={(e) => setDuration(e.target.value)} />
          </label>
          <label>
            Regions (comma-separated — leave blank to search all regions)
            <input placeholder="e.g. us-east-1,europe-west1 (leave blank for any)" value={regions} onChange={(e) => setRegions(e.target.value)} />
          </label>
          <div className="providers">
            <label>
              <input type="checkbox" checked={providers.aws} onChange={(e) => setProviders({ ...providers, aws: e.target.checked })} /> AWS
            </label>
            <label>
              <input type="checkbox" checked={providers.azure} onChange={(e) => setProviders({ ...providers, azure: e.target.checked })} /> Azure
            </label>
            <label>
              <input type="checkbox" checked={providers.gcp} onChange={(e) => setProviders({ ...providers, gcp: e.target.checked })} /> GCP
            </label>
          </div>

          <button type="submit" disabled={loading}>{loading ? 'Running...' : 'Estimate TCO'}</button>
        </form>

        {error && <div className="error">Error: {error}</div>}

        {best && (
          <div className="best">
            <h3>Best option: {best.provider} {best.region || ''}</h3>
            <p>Monthly: {formatCurrency(best.monthly_cost)} Yearly: {formatCurrency(best.yearly_cost)}</p>
          </div>
        )}

        {results && (
          <ComparisonChart
            results={results.map(r => ({ provider: r.provider, monthly_cost: r.monthly_cost }))}
          />
        )}

        {results && (
          <table className="results">
            <thead>
              <tr><th>Provider</th><th>Region</th><th>Instance</th><th>$ / hr</th><th>Monthly</th><th>Yearly</th></tr>
            </thead>
            <tbody>
              {results.map((r) => (
                <tr key={r.provider}>
                  <td>{r.provider}</td>
                  <td>{r.region}</td>
                  <td>{r.instance_type}</td>
                  <td>{formatCurrency(r.price_per_hour)}</td>
                  <td>{formatCurrency(r.monthly_cost)}</td>
                  <td>{formatCurrency(r.yearly_cost)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </main>
    </div>
  )
}

export default App
