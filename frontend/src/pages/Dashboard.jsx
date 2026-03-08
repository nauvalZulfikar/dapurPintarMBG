import { useState, useEffect, useCallback } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  LineChart, Line, CartesianGrid,
  PieChart, Pie, Cell,
} from 'recharts'
import MetricCard from '../components/MetricCard'
import DataTable from '../components/DataTable'
import Pagination from '../components/Pagination'
import { getOverview } from '../api/overview'
import { getItems } from '../api/items'
import { getTrays } from '../api/trays'
import { getDelivery } from '../api/delivery'
import { getStats } from '../api/stats'
import { useSSE } from '../hooks/useSSE'
import { formatDateTime, todayISO } from '../utils/format'

const ITEM_COLUMNS = [
  { key: 'id', label: 'ID' },
  { key: 'name', label: 'Name' },
  { key: 'weight_grams', label: 'Weight (g)' },
  { key: 'receiving', label: 'Received', render: (v) => v ? 'Yes' : 'No' },
  { key: 'created_at_receiving', label: 'Received At', render: (v) => formatDateTime(v) },
  { key: 'processing', label: 'Processed', render: (v) => v ? 'Yes' : 'No' },
  { key: 'created_at_processing', label: 'Processed At', render: (v) => formatDateTime(v) },
]

const TRAY_COLUMNS = [
  { key: 'tray_id', label: 'Tray ID' },
  { key: 'packing', label: 'Packed', render: (v) => v ? 'Yes' : 'No' },
  { key: 'created_at_packing', label: 'Packed At', render: (v) => formatDateTime(v) },
  { key: 'delivery', label: 'Delivered', render: (v) => v ? 'Yes' : 'No' },
  { key: 'created_at_delivery', label: 'Delivered At', render: (v) => formatDateTime(v) },
]

const PIE_COLORS = ['#6BAFD6', '#e5e7eb']

function durationColor(mins, thresholds) {
  if (mins === null || mins === undefined) return 'text-gray-400'
  if (mins <= thresholds[0]) return 'text-green-600'
  if (mins <= thresholds[1]) return 'text-yellow-500'
  return 'text-red-600'
}

function fmtDuration(mins) {
  if (mins === null || mins === undefined) return '—'
  if (mins < 60) return `${Math.round(mins)} min`
  return `${(mins / 60).toFixed(1)} hr`
}

function fmtTime(isoStr) {
  if (!isoStr) return '—'
  return new Date(isoStr).toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' })
}

const CARD = 'bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700'
const HEADING = 'text-sm font-semibold text-gray-700 dark:text-gray-200'

// ── Pipeline Funnel ──────────────────────────────────────────────────────────
function PipelineFunnel({ metrics }) {
  const steps = [
    { label: 'Received', value: metrics?.items_received ?? 0, color: 'bg-accent' },
    { label: 'Processed', value: metrics?.items_processed ?? 0, color: 'bg-brand-mid' },
    { label: 'Packed', value: metrics?.trays_packed ?? 0, color: 'bg-brand' },
    { label: 'Delivered', value: metrics?.trays_delivered ?? 0, color: 'bg-green-500' },
  ]
  const max = steps[0].value || 1

  return (
    <div className={`${CARD} p-4`}>
      <h3 className={`${HEADING} mb-4`}>Pipeline Funnel</h3>
      <div className="flex items-center gap-2">
        {steps.map((step, i) => {
          const pct = Math.round((step.value / max) * 100)
          return (
            <div key={step.label} className="flex items-center gap-2 flex-1">
              <div className="flex-1 text-center">
                <div className={`${step.color} rounded-lg py-3 px-2 text-white`}>
                  <div className="text-2xl font-bold">{step.value}</div>
                  <div className="text-xs mt-1">{step.label}</div>
                  <div className="text-xs opacity-75">{i === 0 ? '100%' : `${pct}%`}</div>
                </div>
              </div>
              {i < steps.length - 1 && (
                <div className="text-gray-300 dark:text-gray-600 text-xl font-bold flex-shrink-0">→</div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── Processing Donut ─────────────────────────────────────────────────────────
function ProcessingDonut({ metrics }) {
  const received = metrics?.items_received ?? 0
  const processed = metrics?.items_processed ?? 0
  const pending = Math.max(0, received - processed)
  const data = received === 0
    ? [{ name: 'No data', value: 1 }]
    : [{ name: 'Processed', value: processed }, { name: 'Pending', value: pending }]
  const colors = received === 0 ? ['#e5e7eb'] : PIE_COLORS

  return (
    <div className={`${CARD} p-4`}>
      <h3 className={`${HEADING} mb-2`}>Item Processing Rate</h3>
      <ResponsiveContainer width="100%" height={160}>
        <PieChart>
          <Pie data={data} cx="50%" cy="50%" innerRadius={45} outerRadius={65} dataKey="value" startAngle={90} endAngle={-270}>
            {data.map((_, i) => <Cell key={i} fill={colors[i % colors.length]} />)}
          </Pie>
          <Tooltip formatter={(v, n) => [v, n]} />
        </PieChart>
      </ResponsiveContainer>
      <div className="flex justify-center gap-4 text-xs mt-1">
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-accent inline-block" /><span className="text-gray-600 dark:text-gray-300">{processed} processed</span></span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-gray-200 dark:bg-gray-600 inline-block" /><span className="text-gray-600 dark:text-gray-300">{pending} pending</span></span>
      </div>
    </div>
  )
}

// ── Tray Fill Rate ───────────────────────────────────────────────────────────
function TrayFillRate({ metrics, totalStudents }) {
  const packed = metrics?.trays_packed ?? 0
  const needed = totalStudents || 0
  const pct = needed === 0 ? 0 : Math.min(100, Math.round((packed / needed) * 100))
  const barColor = pct >= 100 ? 'bg-green-500' : pct >= 60 ? 'bg-yellow-400' : 'bg-red-400'

  return (
    <div className={`${CARD} p-4`}>
      <h3 className={`${HEADING} mb-3`}>Tray Fill Rate</h3>
      <div className="text-3xl font-bold text-gray-800 dark:text-gray-100 mb-1">{pct}%</div>
      <div className="text-xs text-gray-500 dark:text-gray-400 mb-3">{packed} of {needed} trays needed</div>
      <div className="w-full bg-gray-100 dark:bg-gray-700 rounded-full h-4 overflow-hidden">
        <div className={`${barColor} h-4 rounded-full transition-all duration-500`} style={{ width: `${pct}%` }} />
      </div>
      <div className="flex justify-between text-xs text-gray-400 dark:text-gray-500 mt-1">
        <span>0</span>
        <span>{needed} students</span>
      </div>
    </div>
  )
}

// ── Duration Stats ────────────────────────────────────────────────────────────
function DurationStats({ stats }) {
  const r2p = stats?.avg_receive_to_process_mins
  const p2d = stats?.avg_pack_to_deliver_mins

  return (
    <div className={`${CARD} p-4`}>
      <h3 className={`${HEADING} mb-4`}>Avg Durations</h3>
      <div className="space-y-4">
        <div>
          <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Receiving → Processing</div>
          <div className={`text-2xl font-bold ${durationColor(r2p, [60, 120])}`}>
            {fmtDuration(r2p)}
          </div>
          <div className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">shorter is better</div>
        </div>
        <div className="border-t border-gray-100 dark:border-gray-700 pt-4">
          <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Packing → Delivery</div>
          <div className={`text-2xl font-bold ${durationColor(p2d, [30, 60])}`}>
            {fmtDuration(p2d)}
          </div>
          <div className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">shorter is better</div>
        </div>
      </div>
    </div>
  )
}

// ── Hourly Activity Chart ─────────────────────────────────────────────────────
function HourlyActivity({ stats }) {
  const data = stats?.hourly_scans ?? []
  if (data.length === 0) {
    return (
      <div className={`${CARD} p-4`}>
        <h3 className={`${HEADING} mb-2`}>Hourly Scan Activity</h3>
        <div className="text-sm text-gray-400 dark:text-gray-500 py-8 text-center">No scan activity</div>
      </div>
    )
  }
  return (
    <div className={`${CARD} p-4`}>
      <h3 className={`${HEADING} mb-4`}>Hourly Scan Activity</h3>
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={data} margin={{ top: 0, right: 10, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
          <XAxis dataKey="hour" tickFormatter={(h) => `${h}:00`} tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip formatter={(v) => [v, 'scans']} labelFormatter={(h) => `${h}:00`} />
          <Line type="monotone" dataKey="scans" stroke="#1B3A6B" strokeWidth={2} dot={{ r: 3 }} activeDot={{ r: 5 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

// ── Accordion wrapper ─────────────────────────────────────────────────────────
function Accordion({ title, badge, defaultOpen = false, children }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className={CARD}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-4 py-3 text-left"
      >
        <div className="flex items-center gap-2">
          <h3 className={HEADING}>{title}</h3>
          {badge && <span className="text-xs bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 px-2 py-0.5 rounded-full">{badge}</span>}
        </div>
        <span className="text-gray-400 dark:text-gray-500 text-xs">{open ? '▲ collapse' : '▼ expand'}</span>
      </button>
      {open && <div className="px-4 pb-4">{children}</div>}
    </div>
  )
}

// ── Delivery School Status ────────────────────────────────────────────────────
function DeliverySchoolStatus({ deliveryData }) {
  const [showAll, setShowAll] = useState(false)
  const count = deliveryData?.length ?? 0
  const visible = showAll ? deliveryData : (deliveryData ?? []).slice(0, 3)

  const SchoolCard = ({ school }) => {
    const needed = school.student_count
    const delivered = school.meals_delivered ?? 0
    const pct = needed === 0 ? 0 : Math.round((delivered / needed) * 100)
    const fully = pct >= 100
    const partial = pct > 0 && pct < 100
    const barColor = fully ? 'bg-green-500' : partial ? 'bg-yellow-400' : 'bg-gray-200 dark:bg-gray-600'
    const badge = fully
      ? 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-400'
      : partial
      ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-400'
      : 'bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400'
    const label = fully ? '✓ Delivered' : partial ? 'Partial' : 'Pending'
    const distLabel = school.distance >= 1000
      ? `${(school.distance / 1000).toFixed(1)} km`
      : `${school.distance} m`

    return (
      <div className="border border-gray-100 dark:border-gray-700 rounded-lg p-3">
        <div className="flex items-start justify-between gap-2 mb-1">
          <div className="text-sm font-medium text-gray-800 dark:text-gray-100 leading-tight">{school.school_name}</div>
          <span className={`text-xs px-2 py-0.5 rounded-full whitespace-nowrap flex-shrink-0 ${badge}`}>{label}</span>
        </div>
        <div className="text-xs text-gray-400 dark:text-gray-500 mb-2">{distLabel} · {needed} students</div>
        <div className="text-xs text-gray-500 dark:text-gray-400 mb-2">{delivered}/{needed} meals</div>
        <div className="w-full bg-gray-100 dark:bg-gray-700 rounded-full h-2">
          <div className={`${barColor} h-2 rounded-full transition-all duration-500`} style={{ width: `${pct}%` }} />
        </div>
      </div>
    )
  }

  const content = count === 0
    ? <div className="text-sm text-gray-400 dark:text-gray-500 py-4 text-center">No schools loaded</div>
    : (
      <>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {visible.map((school) => <SchoolCard key={school.school_id} school={school} />)}
        </div>
        {count > 3 && (
          <button onClick={() => setShowAll((v) => !v)}
            className="mt-3 text-xs text-accent hover:underline">
            {showAll ? '▲ Show top 3 only' : `▼ Show all ${count} schools`}
          </button>
        )}
      </>
    )

  return (
    <Accordion title="Delivery Status per School" badge={`${count} schools`} defaultOpen>
      {content}
    </Accordion>
  )
}

// ── Delivery Timeline ─────────────────────────────────────────────────────────
function DeliveryTimeline({ deliveryData }) {
  const [showAll, setShowAll] = useState(false)
  const count = deliveryData?.length ?? 0

  const sorted = [...(deliveryData ?? [])].sort((a, b) => {
    const aD = (a.meals_delivered ?? 0) >= a.student_count && a.student_count > 0
    const bD = (b.meals_delivered ?? 0) >= b.student_count && b.student_count > 0
    if (aD && bD) return new Date(a.last_delivered_at) - new Date(b.last_delivered_at)
    if (aD) return -1
    if (bD) return 1
    return (a.distance ?? 0) - (b.distance ?? 0)
  })

  const visible = showAll ? sorted : sorted.slice(0, 3)

  const content = count === 0
    ? <div className="text-sm text-gray-400 dark:text-gray-500 py-4 text-center">No deliveries yet</div>
    : (
      <>
        <div className="space-y-2">
          {visible.map((school) => {
            const delivered = (school.meals_delivered ?? 0) >= school.student_count && school.student_count > 0
            const time = fmtTime(school.last_delivered_at)
            const distLabel = school.distance >= 1000
              ? `${(school.distance / 1000).toFixed(1)} km`
              : `${school.distance} m`
            return (
              <div key={school.school_id} className="flex items-center gap-3">
                <div className={`w-3 h-3 rounded-full flex-shrink-0 ${delivered ? 'bg-green-500' : 'bg-gray-300 dark:bg-gray-600'}`} />
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-gray-700 dark:text-gray-200">{school.school_name}</div>
                  <div className="text-xs text-gray-400 dark:text-gray-500">{distLabel}</div>
                </div>
                <div className="text-sm font-mono text-gray-500 dark:text-gray-400 flex-shrink-0">
                  {delivered ? time : <span className="text-gray-300 dark:text-gray-600">—</span>}
                </div>
              </div>
            )
          })}
        </div>
        {count > 3 && (
          <button onClick={() => setShowAll((v) => !v)}
            className="mt-3 text-xs text-accent hover:underline">
            {showAll ? '▲ Show top 3 only' : `▼ Show all ${count} schools`}
          </button>
        )}
      </>
    )

  return (
    <Accordion title="Delivery Completion Timeline" badge={`${count} schools`} defaultOpen>
      {content}
    </Accordion>
  )
}

// ── Daily Trend ───────────────────────────────────────────────────────────────
function DailyTrend({ stats }) {
  const data = stats?.weekly_trend ?? []
  if (data.length === 0) {
    return (
      <div className={`${CARD} p-4`}>
        <h3 className={`${HEADING} mb-2`}>7-Day Receiving Trend</h3>
        <div className="text-sm text-gray-400 dark:text-gray-500 py-8 text-center">No data</div>
      </div>
    )
  }
  const formatted = data.map((d) => ({
    ...d,
    label: new Date(d.date).toLocaleDateString('id-ID', { month: 'short', day: 'numeric' }),
  }))

  return (
    <div className={`${CARD} p-4`}>
      <h3 className={`${HEADING} mb-4`}>7-Day Receiving Trend</h3>
      <ResponsiveContainer width="100%" height={180}>
        <LineChart data={formatted} margin={{ top: 0, right: 10, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
          <XAxis dataKey="label" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip formatter={(v) => [v, 'items received']} />
          <Line type="monotone" dataKey="received" stroke="#6BAFD6" strokeWidth={2} dot={{ r: 4 }} activeDot={{ r: 6 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

// ── Dashboard ─────────────────────────────────────────────────────────────────
export default function Dashboard() {
  const [date, setDate] = useState(todayISO())
  const [metrics, setMetrics] = useState(null)
  const [metricsLoading, setMetricsLoading] = useState(true)
  const [stats, setStats] = useState(null)
  const [deliveryData, setDeliveryData] = useState([])
  const [tab, setTab] = useState('items')
  const [items, setItems] = useState([])
  const [itemsPage, setItemsPage] = useState(1)
  const [itemsTotalPages, setItemsTotalPages] = useState(1)
  const [itemsLoading, setItemsLoading] = useState(false)
  const [search, setSearch] = useState('')
  const [trays, setTrays] = useState([])
  const [traysPage, setTraysPage] = useState(1)
  const [traysTotalPages, setTraysTotalPages] = useState(1)
  const [traysLoading, setTraysLoading] = useState(false)

  const loadMetrics = useCallback(() => {
    setMetricsLoading(true)
    getOverview(date).then((r) => setMetrics(r.data)).catch(() => {}).finally(() => setMetricsLoading(false))
  }, [date])

  const loadStats = useCallback(() => {
    getStats(date).then((r) => setStats(r.data)).catch(() => {})
  }, [date])

  const loadDelivery = useCallback(() => {
    getDelivery(date).then((r) => setDeliveryData(r.data.assignments)).catch(() => {})
  }, [date])

  const loadItems = useCallback(() => {
    setItemsLoading(true)
    getItems({ date, page: itemsPage, search: search || undefined })
      .then((r) => { setItems(r.data.items); setItemsTotalPages(r.data.total_pages) })
      .catch(() => {}).finally(() => setItemsLoading(false))
  }, [date, itemsPage, search])

  const loadTrays = useCallback(() => {
    setTraysLoading(true)
    getTrays({ date, page: traysPage })
      .then((r) => { setTrays(r.data.trays); setTraysTotalPages(r.data.total_pages) })
      .catch(() => {}).finally(() => setTraysLoading(false))
  }, [date, traysPage])

  useEffect(() => { loadMetrics() }, [loadMetrics])
  useEffect(() => { loadStats() }, [loadStats])
  useEffect(() => { loadDelivery() }, [loadDelivery])
  useEffect(() => { loadItems() }, [loadItems])
  useEffect(() => { loadTrays() }, [loadTrays])

  useSSE(
    () => { loadMetrics(); loadStats(); loadDelivery(); loadItems(); loadTrays() },
    () => { loadMetrics() },
  )

  const onDateChange = (e) => {
    setDate(e.target.value)
    setItemsPage(1)
    setTraysPage(1)
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-gray-800 dark:text-gray-100">Dashboard</h2>
        <input
          type="date" value={date} onChange={onDateChange}
          className="px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-100"
        />
      </div>

      {/* Metric cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard label="Items Received" value={metrics?.items_received} loading={metricsLoading} />
        <MetricCard label="Items Processed" value={metrics?.items_processed} loading={metricsLoading} />
        <MetricCard label="Trays Packed" value={metrics?.trays_packed} loading={metricsLoading} />
        <MetricCard label="Trays Delivered" value={metrics?.trays_delivered} loading={metricsLoading} />
      </div>

      <PipelineFunnel metrics={metrics} />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <ProcessingDonut metrics={metrics} />
        <TrayFillRate metrics={metrics} totalStudents={stats?.total_students} />
        <DurationStats stats={stats} />
      </div>

      <HourlyActivity stats={stats} />

      <DeliverySchoolStatus deliveryData={deliveryData} />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <DeliveryTimeline deliveryData={deliveryData} />
        <DailyTrend stats={stats} />
      </div>

      {/* Items / Trays tabs */}
      <div className={CARD}>
        <div className="flex border-b border-gray-200 dark:border-gray-700">
          {['items', 'trays'].map((t) => (
            <button key={t} onClick={() => setTab(t)}
              className={`px-4 py-2 text-sm font-medium capitalize ${t === tab ? 'text-brand dark:text-accent border-b-2 border-brand dark:border-accent' : 'text-gray-500 dark:text-gray-400'}`}>
              {t === 'items' ? 'Items' : 'Trays'}
            </button>
          ))}
        </div>
        <div className="p-4">
          {tab === 'items' && (
            <>
              <input type="text" placeholder="Search by name..." value={search}
                onChange={(e) => { setSearch(e.target.value); setItemsPage(1) }}
                className="mb-3 px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded text-sm w-64 bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500" />
              <DataTable columns={ITEM_COLUMNS} data={items} loading={itemsLoading} />
              <Pagination page={itemsPage} totalPages={itemsTotalPages} onPageChange={setItemsPage} />
            </>
          )}
          {tab === 'trays' && (
            <>
              <DataTable columns={TRAY_COLUMNS} data={trays} loading={traysLoading} />
              <Pagination page={traysPage} totalPages={traysTotalPages} onPageChange={setTraysPage} />
            </>
          )}
        </div>
      </div>
    </div>
  )
}
