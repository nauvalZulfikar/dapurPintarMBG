import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { login as apiLogin, getMe, switchKitchen as apiSwitchKitchen } from '../api/auth'

const AuthContext = createContext(null)

const LS_TOKEN = 'token'
const LS_KITCHEN = 'active_kitchen_id'

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [kitchens, setKitchens] = useState([])
  const [permissions, setPermissions] = useState([])
  const [activeKitchenId, setActiveKitchenId] = useState(() => {
    const raw = localStorage.getItem(LS_KITCHEN)
    return raw ? Number(raw) : null
  })
  const [loading, setLoading] = useState(true)

  const applyMe = useCallback((data) => {
    setUser({ id: data.id, username: data.username, role: data.role, org_id: data.org_id })
    setKitchens(data.kitchens || [])
    setPermissions(data.permissions || [])
    const nextActive = data.active_kitchen_id ?? (data.kitchens?.[0]?.id ?? null)
    setActiveKitchenId(nextActive)
    if (nextActive != null) {
      localStorage.setItem(LS_KITCHEN, String(nextActive))
    } else {
      localStorage.removeItem(LS_KITCHEN)
    }
  }, [])

  useEffect(() => {
    const token = localStorage.getItem(LS_TOKEN)
    if (!token) {
      setLoading(false)
      return
    }
    getMe()
      .then((res) => applyMe(res.data))
      .catch(() => {
        localStorage.removeItem(LS_TOKEN)
        localStorage.removeItem(LS_KITCHEN)
      })
      .finally(() => setLoading(false))
  }, [applyMe])

  const login = async (username, password) => {
    const res = await apiLogin(username, password)
    localStorage.setItem(LS_TOKEN, res.data.access_token)
    // prefer data from /login directly, but re-fetch /me for consistency
    const me = await getMe()
    applyMe(me.data)
  }

  const logout = () => {
    localStorage.removeItem(LS_TOKEN)
    localStorage.removeItem(LS_KITCHEN)
    setUser(null)
    setKitchens([])
    setPermissions([])
    setActiveKitchenId(null)
  }

  const switchKitchen = async (kitchen_id) => {
    const res = await apiSwitchKitchen(kitchen_id)
    localStorage.setItem(LS_TOKEN, res.data.access_token)
    localStorage.setItem(LS_KITCHEN, String(kitchen_id))
    setActiveKitchenId(kitchen_id)
  }

  const activeKitchen = kitchens.find(k => k.id === activeKitchenId) || null
  const hasPermission = (perm) => permissions.includes(perm)
  const hasAny = (perms) => perms.some(p => permissions.includes(p))

  return (
    <AuthContext.Provider value={{
      user, loading, kitchens, activeKitchenId, activeKitchen,
      permissions, hasPermission, hasAny,
      login, logout, switchKitchen,
    }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
