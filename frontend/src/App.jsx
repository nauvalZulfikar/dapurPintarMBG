import { Routes, Route } from 'react-router-dom'
import { AuthProvider, useAuth } from './hooks/useAuth'
import { Navigate } from 'react-router-dom'
import ProtectedRoute from './components/ProtectedRoute'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Receiving from './pages/Receiving'
import ScanErrors from './pages/ScanErrors'
import MenuPlanner from './pages/MenuPlanner'
import Countdown from './pages/Countdown'
import AdminKitchens from './pages/AdminKitchens'
import AdminUsers from './pages/AdminUsers'
import AdminOverview from './pages/AdminOverview'
import AdminOrgs from './pages/AdminOrgs'
import AdminSchools from './pages/AdminSchools'
import AdminSuppliers from './pages/AdminSuppliers'
import BuildMenuManual from './pages/BuildMenuManual'
import MenuApproval from './pages/MenuApproval'
import PurchaseOrders from './pages/PurchaseOrders'
import JointInspection from './pages/JointInspection'
import Production from './pages/Production'
import Distributions from './pages/Distributions'
import Finance from './pages/Finance'
import AslapDashboard from './pages/AslapDashboard'
import Executive from './pages/Executive'
import VarianceReport from './pages/VarianceReport'
import NutritionReport from './pages/NutritionReport'

function SuperadminRoute({ children }) {
  const { user, loading } = useAuth()
  if (loading) return null
  const isSuper = ['superadmin', 'admin', 'platform_admin'].includes(user?.role)
  return isSuper ? children : <Navigate to="/" replace />
}

function PlatformRoute({ children }) {
  const { user, loading } = useAuth()
  if (loading) return null
  return user?.role === 'platform_admin' ? children : <Navigate to="/" replace />
}

function PermissionRoute({ perm, children }) {
  const { loading, permissions } = useAuth()
  if (loading) return null
  return permissions.includes(perm) ? children : <Navigate to="/" replace />
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/countdown/:trayId" element={<Countdown />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<Layout />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/receiving" element={<PermissionRoute perm="items.create"><Receiving /></PermissionRoute>} />
            <Route path="/menu-planner" element={<PermissionRoute perm="menu.view"><MenuPlanner /></PermissionRoute>} />
            <Route path="/menu-manual" element={<PermissionRoute perm="menu.calc"><BuildMenuManual /></PermissionRoute>} />
            <Route path="/menu-approval" element={<PermissionRoute perm="menu.save"><MenuApproval /></PermissionRoute>} />
            <Route path="/purchase-orders" element={<PermissionRoute perm="po.view"><PurchaseOrders /></PermissionRoute>} />
            <Route path="/inspections" element={<PermissionRoute perm="inspection.view"><JointInspection /></PermissionRoute>} />
            <Route path="/production" element={<PermissionRoute perm="production.view"><Production /></PermissionRoute>} />
            <Route path="/distributions" element={<PermissionRoute perm="distribution.view"><Distributions /></PermissionRoute>} />
            <Route path="/finance" element={<PermissionRoute perm="finance.view"><Finance /></PermissionRoute>} />
            <Route path="/aslap" element={<PermissionRoute perm="checklist.view"><AslapDashboard /></PermissionRoute>} />
            <Route path="/executive" element={<PermissionRoute perm="executive.kpi_view"><Executive /></PermissionRoute>} />
            <Route path="/scan-errors" element={<PermissionRoute perm="scan_errors.view"><ScanErrors /></PermissionRoute>} />
            <Route path="/admin/overview" element={<SuperadminRoute><AdminOverview /></SuperadminRoute>} />
            <Route path="/admin/organizations" element={<PlatformRoute><AdminOrgs /></PlatformRoute>} />
            <Route path="/admin/kitchens" element={<PermissionRoute perm="admin.kitchens"><AdminKitchens /></PermissionRoute>} />
            <Route path="/admin/users" element={<PermissionRoute perm="admin.users"><AdminUsers /></PermissionRoute>} />
            <Route path="/admin/schools" element={<PermissionRoute perm="school.view"><AdminSchools /></PermissionRoute>} />
            <Route path="/admin/suppliers" element={<PermissionRoute perm="supplier.view"><AdminSuppliers /></PermissionRoute>} />
            <Route path="/reports/variance" element={<PermissionRoute perm="reports.variance"><VarianceReport /></PermissionRoute>} />
            <Route path="/nutrisi" element={<PermissionRoute perm="nutrition.report"><NutritionReport /></PermissionRoute>} />
            <Route path="/menu-library" element={<Navigate to="/menu-planner" replace />} />
          </Route>
        </Route>
      </Routes>
    </AuthProvider>
  )
}
