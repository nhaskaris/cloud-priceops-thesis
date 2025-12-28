import './App.css'
import { BrowserRouter, Link, Route, Routes } from 'react-router-dom'
import PredictForm from './components/PredictForm'
import Landing from './components/Landing'
import ModelsDashboard from './components/ModelsDashboard'
import ContributeModelForm from './components/ContributeModelForm'
import Documentation from './components/Documentation'

const BACKEND_URL = (import.meta.env.VITE_APP_BACKEND_URL as string) || 'http://localhost:8000'

function App() {
  return (
    <BrowserRouter>
      <div className="App">
        <header className="App-header">
          <div className="header-inner">
            <h1>Cloud PriceOps</h1>
            <nav className="main-nav">
              <Link to="/">Home</Link>
              <Link to="/predict">Predict</Link>
              <Link to="/models">Models</Link>
              <Link to="/contribute">Contribute</Link>
              <Link to="/docs">Docs</Link>
              <a href={`${BACKEND_URL}/api/schema/swagger-ui/`} target="_blank" rel="noopener noreferrer">API</a>
            </nav>
          </div>
        </header>
        <main>
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/predict" element={<PredictForm />} />
            <Route path="/models" element={<ModelsDashboard />} />
            <Route path="/contribute" element={<ContributeModelForm />} />
            <Route path="/docs" element={<Documentation />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}

export default App
