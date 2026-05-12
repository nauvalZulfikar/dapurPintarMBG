import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { listNotifications, unreadCount, markRead, markAllRead } from '../api/notifications'

const POLL_INTERVAL_MS = 30000

const CATEGORY_PILL = {
  menu:         'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400',
  receiving:    'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400',
  production:   'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-400',
  distribution: 'bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-400',
  finance:      'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400',
  compliance:   'bg-pink-100 dark:bg-pink-900/30 text-pink-700 dark:text-pink-400',
  system:       'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300',
}

export default function NotificationBell() {
  const [open, setOpen] = useState(false)
  const [count, setCount] = useState(0)
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const ref = useRef(null)

  const refreshCount = async () => {
    try { const r = await unreadCount(); setCount(r.data.unread || 0) }
    catch { /* silent — auth might be loading */ }
  }

  const loadList = async () => {
    setLoading(true)
    try {
      const r = await listNotifications({ limit: 30 })
      setItems(r.data.notifications || [])
    } catch { /* ignore */ }
    finally { setLoading(false) }
  }

  useEffect(() => {
    refreshCount()
    const t = setInterval(refreshCount, POLL_INTERVAL_MS)
    return () => clearInterval(t)
  }, [])

  // Close dropdown when clicking outside
  useEffect(() => {
    const onClick = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [])

  const onToggle = async () => {
    const next = !open
    setOpen(next)
    if (next) await loadList()
  }

  const onClickItem = async (n) => {
    if (!n.read) {
      try {
        await markRead(n.id)
        setItems(items.map(it => it.id === n.id ? { ...it, read: true } : it))
        setCount(c => Math.max(0, c - 1))
      } catch { /* ignore */ }
    }
    if (n.link) { navigate(n.link); setOpen(false) }
  }

  const onMarkAll = async () => {
    try {
      await markAllRead()
      setItems(items.map(it => ({ ...it, read: true })))
      setCount(0)
    } catch { /* ignore */ }
  }

  return (
    <div ref={ref} className="relative">
      <button
        onClick={onToggle}
        title="Notifikasi"
        className="relative p-1.5 text-white/60 hover:text-white hover:bg-white/10 rounded transition-colors"
      >
        <span className="text-lg">🔔</span>
        {count > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] px-1 bg-red-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center">
            {count > 99 ? '99+' : count}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-80 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-xl z-50 max-h-[70vh] overflow-hidden flex flex-col">
          <div className="flex items-center justify-between px-3 py-2 border-b border-gray-200 dark:border-gray-700">
            <span className="text-sm font-semibold text-gray-800 dark:text-gray-100">Notifikasi</span>
            {count > 0 && (
              <button onClick={onMarkAll} className="text-xs text-blue-600 hover:underline">Mark all read</button>
            )}
          </div>
          <div className="flex-1 overflow-y-auto">
            {loading ? (
              <div className="p-4 text-sm text-gray-400 text-center">Memuat...</div>
            ) : items.length === 0 ? (
              <div className="p-6 text-sm text-gray-400 text-center">Belum ada notifikasi.</div>
            ) : items.map(n => (
              <button
                key={n.id}
                onClick={() => onClickItem(n)}
                className={`w-full text-left px-3 py-2 border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50 ${
                  !n.read ? 'bg-blue-50/50 dark:bg-blue-900/10' : ''
                }`}
              >
                <div className="flex items-start gap-2">
                  {!n.read && <span className="mt-1.5 w-2 h-2 bg-blue-500 rounded-full flex-shrink-0" />}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className={`text-[10px] px-1.5 py-0.5 rounded ${CATEGORY_PILL[n.category] || ''}`}>{n.category}</span>
                      <span className="text-[10px] text-gray-400">{formatRel(n.created_at)}</span>
                    </div>
                    <div className="text-sm font-medium text-gray-800 dark:text-gray-100 truncate">{n.title}</div>
                    {n.body && <div className="text-xs text-gray-500 dark:text-gray-400 line-clamp-2 mt-0.5">{n.body}</div>}
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function formatRel(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const diff = (Date.now() - d.getTime()) / 1000
  if (diff < 60) return 'baru saja'
  if (diff < 3600) return `${Math.floor(diff / 60)}m`
  if (diff < 86400) return `${Math.floor(diff / 3600)}j`
  return d.toLocaleDateString('id-ID', { day: 'numeric', month: 'short' })
}
