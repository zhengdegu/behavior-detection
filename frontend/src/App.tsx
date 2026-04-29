import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Live from './pages/Live'
import Events from './pages/Events'
import Config from './pages/Config'
import Analyze from './pages/Analyze'
import System from './pages/System'

function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
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
