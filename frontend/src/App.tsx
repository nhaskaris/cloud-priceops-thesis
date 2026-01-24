import './App.css'
import { useState } from 'react'
import { BrowserRouter, Link, Route, Routes } from 'react-router-dom'
import Landing from './components/Landing'
import ModelsDashboard from './components/ModelsDashboard'
import ContributeModelForm from './components/ContributeModelForm'
import Documentation from './components/Documentation'
import PricingAnalyzer from './components/PricingAnalyzer'

const BACKEND_URL = (import.meta.env.VITE_APP_BACKEND_URL as string) || 'http://localhost:8000'

function App() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  return (
    <BrowserRouter>
      <div className="App">
        <header className="App-header">
          <div className="header-inner">
            <h1>Cloud PriceOps</h1>
            
            {/* Hamburger button for mobile */}
            <button 
              className="mobile-menu-toggle" 
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              aria-label="Toggle menu"
            >
              <svg width="24" height="24" fill="currentColor" viewBox="0 0 16 16">
                {mobileMenuOpen ? (
                  <path d="M2.146 2.854a.5.5 0 1 1 .708-.708L8 7.293l5.146-5.147a.5.5 0 0 1 .708.708L8.707 8l5.147 5.146a.5.5 0 0 1-.708.708L8 8.707l-5.146 5.147a.5.5 0 0 1-.708-.708L7.293 8 2.146 2.854Z"/>
                ) : (
                  <path fillRule="evenodd" d="M2.5 12a.5.5 0 0 1 .5-.5h10a.5.5 0 0 1 0 1H3a.5.5 0 0 1-.5-.5zm0-4a.5.5 0 0 1 .5-.5h10a.5.5 0 0 1 0 1H3a.5.5 0 0 1-.5-.5zm0-4a.5.5 0 0 1 .5-.5h10a.5.5 0 0 1 0 1H3a.5.5 0 0 1-.5-.5z"/>
                )}
              </svg>
            </button>

            <nav className={`main-nav ${mobileMenuOpen ? 'mobile-open' : ''}`}>
              <Link to="/" onClick={() => setMobileMenuOpen(false)}>Home</Link>
              <Link to="/analyze" onClick={() => setMobileMenuOpen(false)}>Analyze</Link>
              <Link to="/models" onClick={() => setMobileMenuOpen(false)}>Models</Link>
              
              <Link to="/contribute" onClick={() => setMobileMenuOpen(false)}>Contribute</Link>
              <Link to="/docs" onClick={() => setMobileMenuOpen(false)}>Docs</Link>
              <a href={`${BACKEND_URL}/schema/swagger-ui/`} target="_blank" rel="noopener noreferrer">API</a>
            </nav>
          </div>
        </header>
        <main>
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/analyze" element={<PricingAnalyzer />} />
            <Route path="/models" element={<ModelsDashboard />} />
            // ...existing code...
            <Route path="/contribute" element={<ContributeModelForm />} />
            <Route path="/docs" element={<Documentation />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}

export default App
