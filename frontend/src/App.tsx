import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import Live from './pages/Live'
import Events from './pages/Events'
import Config from './pages/Config'
import Analyze from './pages/Analyze'
import System from './pages/System'
import Login from './pages/Login'
import { isAuthenticated } from './auth'

function RequireAuth({ children }: { children: React.ReactNode }) {
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />
  }
  return <>{children}</>
}

function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route path="/" element={<Live />} />
        <Route path="/events" element={<Events />} />
        <Route path="/config" element={<Config />} />
        <Route path="/analyze" element={<Analyze />} />
        <Route path="/system" element={<System />} />
      </Route>
    </Routes>
  )
}

export default App
