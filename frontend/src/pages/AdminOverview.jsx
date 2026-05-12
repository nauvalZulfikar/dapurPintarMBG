import { useEffect, useState } from 'react'
import { crossKitchenOverview } from '../api/admin'
import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, CartesianGrid } from 'recharts'

export default function AdminOverview() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10))

  useEffect(() => {
    setLoading(true); setError('')
    crossKitchenOverview(date)
      .then(r => setData(r.data))
      .catch(e => setError(e.response?.data?.detail || e.message))
      .finally(() => setLoading(false))
  }, [date])

  const kitchens = data?.kitchens || []
  const totals = data?.totals || {}

  // merge all kitchens' trend into one chart dataset by date
  const trendData = mergeTrends(kitchens, data?.week_start, date)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-900 dark:text-white">All Kitchens Overview</h1>
        <input
          type="date"
          value={date}
          onChange={e => setDate(e.target.value)}
          className="px-2 py-1.5 bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded text-sm text-gray-900 dark:text-white"
        />
      </div>

      {error && <div className="bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 px-3 py-2 rounded text-sm">{error}</div>}

      <div className="grid grid-cols-5 gap-3">
        <Totals label="Kitchens"  value={kitchens.length} />
        <Totals label="Received"  value={totals.received || 0} />
        <Totals label="Processed" value={totals.processed || 0} />
        <Totals label="Packed"    value={totals.packed || 0} />
        <Totals label="Delivered" value={totals.delivered || 0} />
      </div>

      <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 dark:bg-gray-700/50 text-left text-xs uppercase tracking-wider text-gray-500 dark:text-gray-400">
            <tr>
              <th className="px-3 py-2">Kitchen</th>
              <th className="px-3 py-2 text-right">Received</th>
              <th className="px-3 py-2 text-right">Processed</th>
              <th className="px-3 py-2 text-right">Packed</th>
              <th className="px-3 py-2 text-right">Delivered</th>
              <th className="px-3 py-2 text-right">Errors</th>
              <th className="px-3 py-2">Last delivery</th>
              <th className="px-3 py-2">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
            {loading ? (
              <tr><td colSpan={8} className="px-3 py-6 text-center text-gray-500 dark:text-gray-400">Loading…</td></tr>
            ) : kitchens.length === 0 ? (
              <tr><td colSpan={8} className="px-3 py-6 text-center text-gray-500 dark:text-gray-400">No kitchens</td></tr>
            ) : kitchens.map(k => {
              const silent = k.received + k.processed + k.packed + k.delivered === 0
              return (
                <tr key={k.kitchen_id} className="text-gray-900 dark:text-gray-100">
                  <td className="px-3 py-2">
                    <div className="font-medium">{k.name}</div>
                    <div className="text-xs text-gray-500 dark:text-gray-400 font-mono">{k.slug}</div>
                  </td>
                  <td className="px-3 py-2 text-right">{k.received}</td>
                  <td className="px-3 py-2 text-right">{k.processed}</td>
                  <td className="px-3 py-2 text-right">{k.packed}</td>
                  <td className="px-3 py-2 text-right">{k.delivered}</td>
                  <td className={`px-3 py-2 text-right ${k.errors > 0 ? 'text-red-600 font-medium' : ''}`}>{k.errors}</td>
                  <td className="px-3 py-2 text-xs text-gray-500 dark:text-gray-400">{k.last_delivery || '—'}</td>
                  <td className="px-3 py-2">
                    {silent ? (
                      <span className="inline-block px-2 py-0.5 rounded text-xs bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">silent today</span>
                    ) : (
                      <span className="inline-block px-2 py-0.5 rounded text-xs bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">active</span>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {trendData.length > 0 && (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
          <h2 className="text-sm font-semibold mb-3 text-gray-700 dark:text-gray-300">7-day received trend — per kitchen</h2>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={trendData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" strokeOpacity={0.15} />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              {kitchens.map((k, i) => (
                <Bar key={k.kitchen_id} dataKey={k.name} stackId="a" fill={COLORS[i % COLORS.length]} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}

function Totals({ label, value }) {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-3">
      <div className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider">{label}</div>
      <div className="text-2xl font-semibold mt-1 text-gray-900 dark:text-white">{value}</div>
    </div>
  )
}

function mergeTrends(kitchens, weekStart, endDate) {
  if (!weekStart || !endDate) return []
  const days = []
  const start = new Date(weekStart)
  const end = new Date(endDate)
  for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
    days.push(d.toISOString().slice(0, 10))
  }
  return days.map(day => {
    const row = { date: day.slice(5) }
    kitchens.forEach(k => {
      const hit = (k.trend || []).find(t => t.date === day)
      row[k.name] = hit ? hit.received : 0
    })
    return row
  })
}

const COLORS = ['#1B3A6B', '#C9A96E', '#2D8659', '#C4544A', '#8B5CF6', '#E89F1B']
