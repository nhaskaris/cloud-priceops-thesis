import { Link } from 'react-router-dom'

export default function Landing() {
  return (
    <div style={{ maxWidth: 1200, margin: '0 auto' }}>
      {/* Hero Section */}
      <div className="page-header" style={{ textAlign: 'center', padding: '1rem 0' }}>
        <div className="page-header-breadcrumb" style={{ marginLeft: 'auto', marginRight: 'auto' }}>
          <svg width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
            <path d="M8 2a.5.5 0 0 1 .5.5V4a.5.5 0 0 1-1 0V2.5A.5.5 0 0 1 8 2zM3.732 3.732a.5.5 0 0 1 .707 0l.915.914a.5.5 0 1 1-.708.708l-.914-.915a.5.5 0 0 1 0-.707zM2 8a.5.5 0 0 1 .5-.5h1.586a.5.5 0 0 1 0 1H2.5A.5.5 0 0 1 2 8zm9.5 0a.5.5 0 0 1 .5-.5h1.5a.5.5 0 0 1 0 1H12a.5.5 0 0 1-.5-.5zm.754-4.246a.389.389 0 0 0-.527-.02L7.547 7.31A.91.91 0 1 0 8.85 8.569l3.434-4.297a.389.389 0 0 0-.029-.518z"/>
            <path fillRule="evenodd" d="M6.664 15.889A8 8 0 1 1 9.336.11a8 8 0 0 1-2.672 15.78zm-4.665-4.283A11.945 11.945 0 0 1 8 10c2.186 0 4.236.585 6.001 1.606a7 7 0 1 0-12.002 0z"/>
          </svg>
          Platform Home
        </div>
        <h1 className="page-header-title" style={{ fontSize: '3rem', marginBottom: '1rem' }}>
          Cloud PriceOps
        </h1>
      </div>

      {/* Two User Paths */}
      <section style={{ marginBottom: '3rem' }} className="animate-slide-up animate-delay-1">
        <div style={{ display: 'grid', gap: '2rem', gridTemplateColumns: '1fr 1fr' }}>
          
          {/* Predict Flow */}
          <div style={{ background: '#1e293b', padding: '2rem', borderRadius: 12, border: '2px solid #3b82f6', display: 'flex', flexDirection: 'column', height: '100%' }}>
            <div style={{ background: '#3b82f6', color: 'white', padding: '0.5rem 1rem', borderRadius: 6, display: 'inline-block', fontSize: '0.875rem', fontWeight: 600, marginBottom: '1rem' }}>
              FOR USERS
            </div>
            <h3 style={{ color: '#f1f5f9', marginTop: 0, fontSize: '1.75rem', marginBottom: '1rem' }}>
              Get Price Predictions
            </h3>
            <p style={{ color: '#94a3b8', marginBottom: '1.5rem', lineHeight: 1.6 }}>
              Quick and easy price estimation for cloud resources
            </p>
            
            <div style={{ marginBottom: '1.5rem' }}>
              <div style={{ color: '#cbd5e1', marginBottom: '0.75rem', display: 'flex', alignItems: 'flex-start' }}>
                <span style={{ color: '#60a5fa', fontWeight: 700, marginRight: '0.75rem', fontSize: '1.25rem' }}>1</span>
                <span>Enter your resource specifications (vCPU, memory, region, etc.)</span>
              </div>
              <div style={{ color: '#cbd5e1', marginBottom: '0.75rem', display: 'flex', alignItems: 'flex-start' }}>
                <span style={{ color: '#60a5fa', fontWeight: 700, marginRight: '0.75rem', fontSize: '1.25rem' }}>2</span>
                <span>Select a model type (Regression, etc.)</span>
              </div>
              <div style={{ color: '#cbd5e1', marginBottom: '0.75rem', display: 'flex', alignItems: 'flex-start' }}>
                <span style={{ color: '#60a5fa', fontWeight: 700, marginRight: '0.75rem', fontSize: '1.25rem' }}>3</span>
                <span>Get instant price prediction with hourly, monthly, and yearly costs</span>
              </div>
            </div>

            <Link to="/predict" className="btn-primary" style={{ display: 'block', textAlign: 'center', marginTop: 'auto', padding: '0.875rem' }}>
              Start Predicting →
            </Link>
          </div>

          {/* Contribute Flow */}
          <div style={{ background: '#1e293b', padding: '2rem', borderRadius: 12, border: '2px solid #3b82f6', display: 'flex', flexDirection: 'column', height: '100%' }}>
            <div style={{ background: '#3b82f6', color: 'white', padding: '0.5rem 1rem', borderRadius: 6, display: 'inline-block', fontSize: '0.875rem', fontWeight: 600, marginBottom: '1rem' }}>
              FOR CONTRIBUTORS
            </div>
            <h3 style={{ color: '#f1f5f9', marginTop: 0, fontSize: '1.75rem', marginBottom: '1rem' }}>
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

      {/* Models Dashboard Section */}
      <section style={{ background: '#1e293b', padding: '2rem', borderRadius: 12, border: '1px solid #334155', textAlign: 'center', marginBottom: '2rem' }}>
        <h3 style={{ color: '#f1f5f9', marginTop: 0, fontSize: '1.5rem' }}>Explore All Models</h3>
        <p style={{ color: '#cbd5e1', marginBottom: '1.5rem', lineHeight: 1.6 }}>
          Browse all registered models, compare performance metrics (R², MAPE, RMSE), and track model versions
        </p>
        <Link to="/models" className="btn-secondary" style={{ display: 'inline-block', padding: '0.75rem 1.5rem' }}>
          Open Models →
        </Link>
      </section>

      {/* Documentation Link */}
      <section style={{ background: '#1e293b', padding: '2rem', borderRadius: 12, border: '1px solid #334155', textAlign: 'center' }}>
        <h3 style={{ color: '#f1f5f9', marginTop: 0, fontSize: '1.5rem' }}>Need Help?</h3>
        <p style={{ color: '#cbd5e1', marginBottom: '1.5rem', lineHeight: 1.6 }}>
          Check out our complete documentation with step-by-step guides, API examples, and code samples
        </p>
        <Link to="/docs" className="btn-secondary" style={{ display: 'inline-block', padding: '0.75rem 1.5rem' }}>
          Read Documentation →
        </Link>
      </section>
    </div>
  )
}
