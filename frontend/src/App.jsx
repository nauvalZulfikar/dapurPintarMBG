import { Routes, Route } from 'react-router-dom'
import { AuthProvider } from './hooks/useAuth'
import ProtectedRoute from './components/ProtectedRoute'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Receiving from './pages/Receiving'
import ScanErrors from './pages/ScanErrors'
import MenuPlanner from './pages/MenuPlanner'
import Countdown from './pages/Countdown'

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/countdown/:trayId" element={<Countdown />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<Layout />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/receiving" element={<Receiving />} />
            <Route path="/menu-planner" element={<MenuPlanner />} />
            <Route path="/scan-errors" element={<ScanErrors />} />
          </Route>
        </Route>
      </Routes>
    </AuthProvider>
  )
}
