import { Link } from 'react-router-dom'

export default function Landing() {
  return (
    <div style={{ maxWidth: 1200, margin: '0 auto' }}>
      {/* Hero Section */}
      <div className="page-header" style={{ textAlign: 'center', padding: '1rem 0' }}>
        <div className="page-header-breadcrumb" style={{ marginLeft: 'auto', marginRight: 'auto' }}>
          Platform Home
        </div>
        <h1 className="page-header-title" style={{ fontSize: '3.5rem', marginBottom: '1rem', fontWeight: 800 }}>
          Cloud PriceOps
        </h1>
        <p className="page-header-subtitle" style={{ fontSize: '1.2rem', color: '#94a3b8', maxWidth: '600px', margin: '0 auto' }}>
          AI-powered cloud infrastructure cost optimization and prediction platform
        </p>
      </div>

      {/* Key Features */}
      <section style={{ marginBottom: '3rem', marginTop: '3rem' }}>
        <div style={{ display: 'grid', gap: '1.5rem', gridTemplateColumns: 'repeat(3, 1fr)' }}>
          <div style={{ background: '#1e293b', padding: '1.5rem', borderRadius: 10, border: '1px solid #334155', textAlign: 'center' }}>
            <h4 style={{ color: '#f1f5f9', margin: '0 0 0.5rem 0', fontSize: '1.1rem' }}>Instant Predictions</h4>
            <p style={{ color: '#94a3b8', fontSize: '0.9rem', margin: 0, lineHeight: 1.5 }}>Get accurate hourly cost estimates in seconds</p>
          </div>
          <div style={{ background: '#1e293b', padding: '1.5rem', borderRadius: 10, border: '1px solid #334155', textAlign: 'center' }}>
            <h4 style={{ color: '#f1f5f9', margin: '0 0 0.5rem 0', fontSize: '1.1rem' }}>IaaS Specialized</h4>
            <p style={{ color: '#94a3b8', fontSize: '0.9rem', margin: 0, lineHeight: 1.5 }}>Models trained on real infrastructure pricing data</p>
          </div>
          <div style={{ background: '#1e293b', padding: '1.5rem', borderRadius: 10, border: '1px solid #334155', textAlign: 'center' }}>
            <h4 style={{ color: '#f1f5f9', margin: '0 0 0.5rem 0', fontSize: '1.1rem' }}>Model Comparison</h4>
            <p style={{ color: '#94a3b8', fontSize: '0.9rem', margin: 0, lineHeight: 1.5 }}>Track R², MAPE, and performance metrics</p>
          </div>
        </div>
      </section>

      {/* Two User Paths */}
      <section style={{ marginBottom: '3rem' }}>
        <h2 style={{ textAlign: 'center', color: '#f1f5f9', fontSize: '2rem', marginBottom: '2rem' }}>Get Started</h2>
        <div style={{ display: 'grid', gap: '2rem', gridTemplateColumns: '1fr 1fr' }}>
          
          {/* Predict/Optimize Flow */}
          <div style={{ background: '#1e293b', padding: '2rem', borderRadius: 12, border: '2px solid #3b82f6', display: 'flex', flexDirection: 'column', height: '100%' }}>
            <div style={{ background: '#3b82f6', color: 'white', padding: '0.5rem 1rem', borderRadius: 6, display: 'inline-block', fontSize: '0.875rem', fontWeight: 600, marginBottom: '1rem' }}>
              FOR USERS
            </div>
            <h3 style={{ color: '#f1f5f9', marginTop: 0, fontSize: '1.5rem', marginBottom: '0.75rem' }}>
              Analyze Cloud Pricing
            </h3>
            <p style={{ color: '#94a3b8', marginBottom: '1.5rem', lineHeight: 1.6 }}>
              Get price predictions and find cost optimization opportunities
            </p>
            
            <div style={{ marginBottom: '1.5rem' }}>
              <div style={{ color: '#cbd5e1', marginBottom: '0.75rem', display: 'flex', alignItems: 'flex-start' }}>
                <span style={{ color: '#60a5fa', fontWeight: 700, marginRight: '0.75rem', fontSize: '1.25rem' }}>1</span>
                <span><strong>Simple Mode:</strong> Enter current specs and cost to find cheaper alternatives</span>
              </div>
              <div style={{ color: '#cbd5e1', marginBottom: '0.75rem', display: 'flex', alignItems: 'flex-start' }}>
                <span style={{ color: '#60a5fa', fontWeight: 700, marginRight: '0.75rem', fontSize: '1.25rem' }}>2</span>
                <span><strong>Advanced Mode:</strong> Get detailed predictions with model selection and payment options</span>
              </div>
              <div style={{ color: '#cbd5e1', marginBottom: '0.75rem', display: 'flex', alignItems: 'flex-start' }}>
                <span style={{ color: '#60a5fa', fontWeight: 700, marginRight: '0.75rem', fontSize: '1.25rem' }}>3</span>
                <span>Compare with actual database pricing and see savings opportunities</span>
              </div>
            </div>

            <Link to="/analyze" className="btn-primary" style={{ display: 'block', textAlign: 'center', marginTop: 'auto', padding: '0.875rem' }}>
              Start Analysis →
            </Link>
          </div>

          {/* Contribute Flow */}
          <div style={{ background: '#1e293b', padding: '2rem', borderRadius: 12, border: '2px solid #3b82f6', display: 'flex', flexDirection: 'column', height: '100%' }}>
            <div style={{ background: '#3b82f6', color: 'white', padding: '0.5rem 1rem', borderRadius: 6, display: 'inline-block', fontSize: '0.875rem', fontWeight: 600, marginBottom: '1rem' }}>
              FOR CONTRIBUTORS
            </div>
            <h3 style={{ color: '#f1f5f9', marginTop: 0, fontSize: '1.5rem', marginBottom: '0.75rem' }}>
              Register Your Model
            </h3>
            <p style={{ color: '#94a3b8', marginBottom: '1.5rem', lineHeight: 1.6 }}>
              Share your trained models with the community
            </p>
            
            <div style={{ marginBottom: '1.5rem' }}>
              <div style={{ color: '#cbd5e1', marginBottom: '0.75rem', display: 'flex', alignItems: 'flex-start' }}>
                <span style={{ color: '#94a3b8', fontWeight: 700, marginRight: '0.75rem', fontSize: '1.25rem' }}>1</span>
                <span>Train your model on cloud pricing data</span>
              </div>
              <div style={{ color: '#cbd5e1', marginBottom: '0.75rem', display: 'flex', alignItems: 'flex-start' }}>
                <span style={{ color: '#94a3b8', fontWeight: 700, marginRight: '0.75rem', fontSize: '1.25rem' }}>2</span>
                <span>Upload model files (binary, encoder, scaler)</span>
              </div>
              <div style={{ color: '#cbd5e1', marginBottom: '0.75rem', display: 'flex', alignItems: 'flex-start' }}>
                <span style={{ color: '#94a3b8', fontWeight: 700, marginRight: '0.75rem', fontSize: '1.25rem' }}>3</span>
                <span>Provide metadata and performance metrics (R², MAPE, etc.)</span>
              </div>
              <div style={{ color: '#cbd5e1', marginBottom: '0.75rem', display: 'flex', alignItems: 'flex-start' }}>
                <span style={{ color: '#94a3b8', fontWeight: 700, marginRight: '0.75rem', fontSize: '1.25rem' }}>4</span>
                <span>Your model becomes available for predictions and comparisons</span>
              </div>
            </div>

            <Link to="/contribute" className="btn-primary" style={{ display: 'block', textAlign: 'center', marginTop: 'auto', padding: '0.875rem' }}>
              Contribute Model →
            </Link>
          </div>
        </div>
      </section>

      {/* Additional Resources */}
      <section style={{ marginBottom: '2rem' }}>
        <div style={{ display: 'grid', gap: '1.5rem', gridTemplateColumns: '1fr 1fr' }}>
          <div style={{ background: '#1e293b', padding: '2rem', borderRadius: 12, border: '1px solid #334155', textAlign: 'center' }}>
            <h3 style={{ color: '#f1f5f9', marginTop: 0, fontSize: '1.3rem', marginBottom: '0.75rem' }}>Explore Models</h3>
            <p style={{ color: '#cbd5e1', marginBottom: '1.5rem', lineHeight: 1.6, fontSize: '0.95rem' }}>
              Compare performance metrics and track all registered models
            </p>
            <Link to="/models" className="btn-secondary" style={{ display: 'inline-block', padding: '0.75rem 1.5rem' }}>
              View Models →
            </Link>
          </div>
          
          <div style={{ background: '#1e293b', padding: '2rem', borderRadius: 12, border: '1px solid #334155', textAlign: 'center' }}>
            <h3 style={{ color: '#f1f5f9', marginTop: 0, fontSize: '1.3rem', marginBottom: '0.75rem' }}>Documentation</h3>
            <p style={{ color: '#cbd5e1', marginBottom: '1.5rem', lineHeight: 1.6, fontSize: '0.95rem' }}>
              API guides, examples, and integration tutorials
            </p>
            <Link to="/docs" className="btn-secondary" style={{ display: 'inline-block', padding: '0.75rem 1.5rem' }}>
              Read Docs →
            </Link>
          </div>
        </div>
      </section>
    </div>
  )
}
