import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { useDarkMode } from '../hooks/useDarkMode'
import NotificationBell from './NotificationBell'

// Grouped nav — kelompok per alur kerja SPPG MBG (Babak 1-7).
// Items are filtered per-user by `perm`; items with no `perm` are always shown.
// Empty sections (after filter) auto-hidden.
const NAV_SECTIONS = [
  // Entry point — semua role bisa lihat dashboard.
  {
    key: 'home',
    items: [
      { to: '/',             label: 'Dashboard',    icon: '⊞', perm: 'dashboard.view' },
      { to: '/executive',    label: 'Executive',    icon: '📈', perm: 'executive.kpi_view' },
    ],
  },
  // Babak 2 — Ahli Gizi: rencana menu + AKG + approval workflow.
  {
    key: 'gizi',
    header: 'Menu & Gizi',
    items: [
      { to: '/menu-planner',   label: 'Menu Planner',   icon: '☰',  perm: 'menu.view' },
      { to: '/menu-manual',    label: 'Build Manual',   icon: '✎',  perm: 'menu.calc' },
      { to: '/menu-approval',  label: 'Approval Menu',  icon: '✓',  perm: 'menu.save' },
      { to: '/nutrisi',        label: 'Nutrisi Harian', icon: '📊', perm: 'nutrition.report' },
    ],
  },
  // Babak 3 — Penerimaan bahan: PO → truk datang → Joint Inspection → cetak label.
  {
    key: 'penerimaan',
    header: 'Penerimaan Bahan',
    items: [
      { to: '/purchase-orders', label: 'Purchase Orders',  icon: '📋', perm: 'po.view' },
      { to: '/inspections',     label: 'Joint Inspection', icon: '🤝', perm: 'inspection.view' },
      { to: '/receiving',       label: 'Receiving (Quick)', icon: '↓', perm: 'items.create' },
    ],
  },
  // Babak 4 + 5 — Dapur masak + anter ke sekolah.
  {
    key: 'operasi',
    header: 'Produksi & Distribusi',
    items: [
      { to: '/production',     label: 'Production',     icon: '🍳', perm: 'production.view' },
      { to: '/distributions',  label: 'Distribusi',     icon: '🚐', perm: 'distribution.view' },
    ],
  },
  // Babak 7 — ASLAP daily ops + monitoring.
  {
    key: 'lapangan',
    header: 'Lapangan & Monitoring',
    items: [
      { to: '/aslap',           label: 'ASLAP Daily',    icon: '📝', perm: 'checklist.view' },
      { to: '/scan-errors',     label: 'Scan Errors',    icon: '⚠',  perm: 'scan_errors.view' },
      { to: '/reports/variance', label: 'Variance Report', icon: '📉', perm: 'reports.variance' },
    ],
  },
  // Babak 6 — Akuntan: price + expense + LRA.
  {
    key: 'keuangan',
    header: 'Keuangan',
    items: [
      { to: '/finance',        label: 'Akuntan Finance', icon: '💰', perm: 'finance.view' },
    ],
  },
  // Babak 1 — Master data per kitchen.
  {
    key: 'master',
    header: 'Master Data',
    items: [
      { to: '/admin/schools',   label: 'Sekolah',   icon: '🏫', perm: 'school.view' },
      { to: '/admin/suppliers', label: 'Supplier',  icon: '📦', perm: 'supplier.view' },
    ],
  },
  // Babak 0 — Admin SPPG (kitchen-scoped).
  {
    key: 'admin',
    header: 'Admin Dapur',
    items: [
      { to: '/admin/overview', label: 'All Kitchens', icon: '🌐', minRole: 'superadmin' },
      { to: '/admin/kitchens', label: 'Kitchens',     icon: '🏠', perm: 'admin.kitchens' },
      { to: '/admin/users',    label: 'Users',        icon: '👤', perm: 'admin.users' },
    ],
  },
  // Platform-wide (lu = IT dev only).
  {
    key: 'platform',
    header: 'Platform',
    minRole: 'platform_admin',
    items: [
      { to: '/admin/organizations', label: 'Organizations', icon: '🏢' },
    ],
  },
]

function sectionVisible(minRole, { isSuperadmin, isPlatformAdmin }) {
  if (!minRole) return true
  if (minRole === 'superadmin')     return isSuperadmin
  if (minRole === 'platform_admin') return isPlatformAdmin
  return true
}

function itemVisible(item, permissions, flags) {
  if (item.minRole && !sectionVisible(item.minRole, flags)) return false
  if (!item.perm) return true
  return permissions.includes(item.perm)
}

const LS_OPEN_SECTIONS = 'sidebar_open_sections'

function loadOpenSections() {
  try {
    const raw = localStorage.getItem(LS_OPEN_SECTIONS)
    return raw ? new Set(JSON.parse(raw)) : null
  } catch { return null }
}

export default function Layout() {
  const { user, logout, kitchens, activeKitchen, activeKitchenId, switchKitchen, permissions } = useAuth()
  const navigate = useNavigate()
  const [collapsed, setCollapsed] = useState(false)
  const [dark, setDark] = useDarkMode()
  const [switching, setSwitching] = useState(false)
  // Open/closed state for collapsible nav groups. Default: all open.
  const [openSections, setOpenSections] = useState(() => {
    const persisted = loadOpenSections()
    if (persisted) return persisted
    return new Set(NAV_SECTIONS.filter(s => s.header).map(s => s.key))
  })

  const toggleSection = (key) => {
    setOpenSections(prev => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key); else next.add(key)
      try { localStorage.setItem(LS_OPEN_SECTIONS, JSON.stringify([...next])) } catch { /* ignore */ }
      return next
    })
  }

  const isPlatformAdmin = user?.role === 'platform_admin'
  const isSuperadmin    = isPlatformAdmin || user?.role === 'superadmin' || user?.role === 'admin'
  const flags = { isSuperadmin, isPlatformAdmin }

  const sections = NAV_SECTIONS
    .filter(s => sectionVisible(s.minRole, flags))
    .map(s => ({ ...s, items: s.items.filter(i => itemVisible(i, permissions, flags)) }))
    .filter(s => s.items.length > 0)

  const onPickKitchen = async (e) => {
    const val = e.target.value
    if (val === 'all') {
      navigate('/admin/overview')
      return
    }
    const newId = Number(val)
    if (newId === activeKitchenId) return
    setSwitching(true)
    try {
      await switchKitchen(newId)
      window.location.reload()
    } catch (err) {
      console.error('switch kitchen failed', err)
      setSwitching(false)
    }
  }

  const title  = activeKitchen?.label_title || activeKitchen?.name || 'Dapur Pintar'
  const roleLabel =
    isPlatformAdmin ? 'platform' :
    isSuperadmin    ? 'superadmin' : null

  return (
    <div className="flex h-screen bg-gray-50 dark:bg-gray-900">
      <aside className={`${collapsed ? 'w-14' : 'w-60'} bg-brand flex flex-col flex-shrink-0 transition-all duration-200`}>

        {/* Brand */}
        <div className="px-3 py-4 flex items-center justify-between gap-2 min-h-[64px] border-b border-white/10">
          {!collapsed && (
            <div className="min-w-0">
              <div className="text-[10px] font-semibold text-gold uppercase tracking-widest truncate">Dapur Pintar</div>
              <div className="text-base font-bold text-white leading-tight truncate">{title}</div>
            </div>
          )}
          <div className="flex-shrink-0 flex items-center gap-1">
            {!collapsed && <NotificationBell />}
            <button
              onClick={() => setCollapsed(c => !c)}
              className="text-white/50 hover:text-white text-sm px-1"
              title={collapsed ? 'Expand' : 'Collapse'}
            >
              {collapsed ? '→' : '←'}
            </button>
          </div>
        </div>

        {/* Kitchen switcher */}
        {!collapsed && (kitchens.length > 1 || isSuperadmin) && (
          <div className="px-3 py-3 border-b border-white/10">
            <label className="text-[10px] uppercase tracking-wider text-white/40 block mb-1">Kitchen</label>
            <select
              value={activeKitchenId ?? ''}
              onChange={onPickKitchen}
              disabled={switching}
              className="w-full bg-white/10 text-white text-sm rounded px-2 py-1.5 outline-none hover:bg-white/15 disabled:opacity-50"
            >
              {isSuperadmin && <option value="all" className="text-gray-900 dark:text-white">🌐 All kitchens</option>}
              {kitchens.map(k => (
                <option key={k.id} value={k.id} className="text-gray-900 dark:text-white">
                  {k.name}{k.role ? ` · ${k.role}` : ''}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto py-2">
          {sections.map((section, idx) => {
            // Sections without a header are pinned at the top (e.g. Dashboard).
            // Sections with a header become collapsible dropdowns.
            const isCollapsible = !!section.header && !collapsed
            const isOpen = !isCollapsible || openSections.has(section.key)

            return (
              <div key={section.key} className={idx > 0 ? 'mt-2 pt-2 border-t border-white/10' : ''}>
                {section.header && !collapsed && (
                  <button
                    onClick={() => toggleSection(section.key)}
                    className="w-full flex items-center justify-between px-4 py-1.5 text-[10px] uppercase tracking-wider text-white/40 hover:text-white/80 font-semibold transition-colors"
                  >
                    <span>{section.header}</span>
                    <span className="text-[8px] text-white/40 transition-transform" style={{ transform: isOpen ? 'rotate(0deg)' : 'rotate(-90deg)' }}>
                      ▼
                    </span>
                  </button>
                )}
                {isOpen && (
                  <div className="px-2 space-y-0.5 pb-1">
                    {section.items.map(item => (
                      <NavLink
                        key={item.to}
                        to={item.to}
                        end={item.to === '/'}
                        title={collapsed ? item.label : undefined}
                        className={({ isActive }) =>
                          `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                            isActive
                              ? 'bg-white/15 text-white font-medium'
                              : 'text-white/60 hover:bg-white/10 hover:text-white'
                          }`
                        }
                      >
                        <span className="flex-shrink-0 w-5 text-center text-base">{item.icon}</span>
                        {!collapsed && <span className="truncate">{item.label}</span>}
                      </NavLink>
                    ))}
                  </div>
                )}
              </div>
            )
          })}
        </nav>

        {/* User panel */}
        <div className="p-2 border-t border-white/10 space-y-1">
          <button
            onClick={() => setDark(d => !d)}
            title={dark ? 'Switch to light mode' : 'Switch to dark mode'}
            className={`w-full py-1.5 text-xs text-white/60 hover:text-white hover:bg-white/10 rounded-lg transition-colors flex items-center gap-2 ${collapsed ? 'justify-center px-1' : 'px-3'}`}
          >
            <span className="w-4 text-center">{dark ? '☀' : '☾'}</span>
            {!collapsed && <span>{dark ? 'Light mode' : 'Dark mode'}</span>}
          </button>

          {!collapsed && (
            <div className="px-3 pt-1 pb-0.5">
              <div className="text-xs text-white/70 truncate font-medium">{user?.username}</div>
              {roleLabel && (
                <div className="text-[10px] text-gold/80 uppercase tracking-wider">{roleLabel}</div>
              )}
            </div>
          )}

          <button
            onClick={logout}
            title={collapsed ? 'Logout' : undefined}
            className={`w-full py-1.5 text-xs text-white/60 hover:text-white hover:bg-white/10 rounded-lg transition-colors flex items-center gap-2 ${collapsed ? 'justify-center px-1' : 'px-3'}`}
          >
            <span className="w-4 text-center">⏻</span>
            {!collapsed && <span>Logout</span>}
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-auto p-6">
        <Outlet />
      </main>
    </div>
  )
}
