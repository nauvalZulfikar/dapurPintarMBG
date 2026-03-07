import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { useDarkMode } from '../hooks/useDarkMode'

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', icon: '⊞' },
  { to: '/receiving', label: 'Receiving', icon: '↓' },
  { to: '/menu-planner', label: 'Menu Planner', icon: '☰' },
  { to: '/scan-errors', label: 'Scan Errors', icon: '⚠' },
]

export default function Layout() {
  const { user, logout } = useAuth()
  const [collapsed, setCollapsed] = useState(false)
  const [dark, setDark] = useDarkMode()

  return (
    <div className="flex h-screen bg-gray-50 dark:bg-gray-900">
      {/* Sidebar */}
      <aside className={`${collapsed ? 'w-14' : 'w-56'} bg-brand flex flex-col flex-shrink-0 transition-all duration-200`}>
        {/* Logo / title */}
        <div className="px-3 py-4 flex items-center justify-between gap-2 min-h-[60px] border-b border-white/10">
          {!collapsed && (
            <div>
              <div className="text-xs font-semibold text-gold uppercase tracking-widest">Dapur Pintar</div>
              <div className="text-base font-bold text-white leading-tight">MBG</div>
            </div>
          )}
          <button
            onClick={() => setCollapsed(c => !c)}
            className="flex-shrink-0 text-white/50 hover:text-white text-sm px-1"
            title={collapsed ? 'Expand' : 'Collapse'}
          >
            {collapsed ? '→' : '←'}
          </button>
        </div>

        <nav className="flex-1 p-2 space-y-0.5 mt-1">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              title={collapsed ? item.label : undefined}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                  isActive
                    ? 'bg-white/15 text-white font-medium'
                    : 'text-white/60 hover:bg-white/10 hover:text-white'
                }`
              }
            >
              <span className="flex-shrink-0 w-4 text-center text-base">{item.icon}</span>
              {!collapsed && <span>{item.label}</span>}
            </NavLink>
          ))}
        </nav>

        <div className="p-2 border-t border-white/10 space-y-1">
          {/* Dark mode toggle */}
          <button
            onClick={() => setDark(d => !d)}
            title={dark ? 'Switch to light mode' : 'Switch to dark mode'}
            className={`w-full py-1.5 text-xs text-white/60 hover:text-white hover:bg-white/10 rounded-lg transition-colors flex items-center gap-2 ${collapsed ? 'justify-center px-1' : 'px-2'}`}
          >
            <span>{dark ? '☀' : '☾'}</span>
            {!collapsed && <span>{dark ? 'Light mode' : 'Dark mode'}</span>}
          </button>

          {!collapsed && <div className="text-xs text-white/40 px-2">{user?.username}</div>}
          <button
            onClick={logout}
            title={collapsed ? 'Logout' : undefined}
            className={`w-full py-1.5 text-xs text-white/60 hover:text-white hover:bg-white/10 rounded-lg transition-colors ${collapsed ? 'px-1' : 'px-2'}`}
          >
            {collapsed ? '⏻' : 'Logout'}
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto p-6">
        <Outlet />
      </main>
    </div>
  )
}
