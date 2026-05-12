import { useEffect, useState } from 'react'
import { getVarianceReport } from '../api/menu'

function todayISO() {
  return new Date().toISOString().slice(0, 10)
}
function daysAgoISO(n) {
  const d = new Date()
  d.setDate(d.getDate() - n)
  return d.toISOString().slice(0, 10)
}

export default function VarianceReport() {
  const [from, setFrom] = useState(daysAgoISO(30))
  const [to, setTo] = useState(todayISO())
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [data, setData] = useState(null)

  const load = async () => {
    setLoading(true); setError('')
    try {
      const r = await getVarianceReport(from, to)
      setData(r.data)
    } catch (e) {
      setError(e.response?.data?.detail || e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const fmtPct = (v) => v == null ? '—' : `${v.toFixed(1)}%`
  const wasteColor = (pct) => {
    if (pct == null) return 'text-gray-400 dark:text-gray-500'
    if (pct === 0) return 'text-green-600 dark:text-green-400'
    if (pct < 10) return 'text-amber-600 dark:text-amber-400'
    return 'text-red-600 dark:text-red-400'
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-gray-900 dark:text-white">Laporan Variance & Waste</h1>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            Selisih items diterima → diproses → packed → dikirim. Untuk monitoring waste & losses.
          </p>
        </div>
        <div className="flex gap-2 items-center">
          <input type="date" value={from} onChange={e => setFrom(e.target.value)}
            className="px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-white" />
          <span className="text-gray-400">→</span>
          <input type="date" value={to} onChange={e => setTo(e.target.value)}
            className="px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-white" />
          <button onClick={load} disabled={loading}
            className="px-3 py-1.5 bg-brand text-white rounded text-sm disabled:opacity-50">
            {loading ? 'Loading…' : 'Refresh'}
          </button>
          {data && (
            <a href={`/api/export/range?from=${from}&to=${to}`} target="_blank" rel="noreferrer"
              className="px-3 py-1.5 bg-gray-700 text-white rounded text-sm">
              Export Excel
            </a>
          )}
        </div>
      </div>

      {error && <div className="bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 px-3 py-2 rounded text-sm">{error}</div>}

      {data?.summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <SummaryCard label="Items diterima" value={data.summary.received} sub="total items" />
          <SummaryCard label="Diproses" value={data.summary.processed}
            pct={data.summary.processed_pct} pctLabel="dari diterima" />
          <SummaryCard label="Packed" value={data.summary.packed} sub="total trays" />
          <SummaryCard label="Dikirim" value={data.summary.delivered}
            pct={data.summary.delivered_pct} pctLabel="dari packed" />
        </div>
      )}

      {data?.summary && (
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
            <div className="text-xs uppercase text-gray-500 dark:text-gray-400 mb-1">Processing waste</div>
            <div className={`text-2xl font-bold ${wasteColor(data.summary.processing_waste_pct)}`}>
              {fmtPct(data.summary.processing_waste_pct)}
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
              {(data.summary.received - data.summary.processed)} item tidak diproses
            </div>
          </div>
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
            <div className="text-xs uppercase text-gray-500 dark:text-gray-400 mb-1">Delivery waste</div>
            <div className={`text-2xl font-bold ${wasteColor(data.summary.delivery_waste_pct)}`}>
              {fmtPct(data.summary.delivery_waste_pct)}
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
              {(data.summary.packed - data.summary.delivered)} tray tidak terkirim
            </div>
          </div>
        </div>
      )}

      <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 dark:bg-gray-700/50 text-left text-xs uppercase text-gray-500 dark:text-gray-400">
            <tr>
              <th className="px-3 py-2">Tanggal</th>
              <th className="px-3 py-2 text-right">Diterima</th>
              <th className="px-3 py-2 text-right">Diproses</th>
              <th className="px-3 py-2 text-right">%</th>
              <th className="px-3 py-2 text-right">Packed</th>
              <th className="px-3 py-2 text-right">Dikirim</th>
              <th className="px-3 py-2 text-right">%</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
            {loading && !data ? (
              <tr><td colSpan={7} className="px-3 py-6 text-center text-gray-500 dark:text-gray-400">Loading…</td></tr>
            ) : (data?.days || []).length === 0 ? (
              <tr><td colSpan={7} className="px-3 py-6 text-center text-gray-500 dark:text-gray-400">Tidak ada data</td></tr>
            ) : (data.days || []).map(d => (
              <tr key={d.date} className="text-gray-900 dark:text-gray-100">
                <td className="px-3 py-2">{d.date}</td>
                <td className="px-3 py-2 text-right tabular-nums">{d.received}</td>
                <td className="px-3 py-2 text-right tabular-nums">{d.processed}</td>
                <td className={`px-3 py-2 text-right tabular-nums text-xs ${wasteColor(d.processed_pct != null ? 100 - d.processed_pct : null)}`}>
                  {fmtPct(d.processed_pct)}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">{d.packed}</td>
                <td className="px-3 py-2 text-right tabular-nums">{d.delivered}</td>
                <td className={`px-3 py-2 text-right tabular-nums text-xs ${wasteColor(d.delivered_pct != null ? 100 - d.delivered_pct : null)}`}>
                  {fmtPct(d.delivered_pct)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}


function SummaryCard({ label, value, sub, pct, pctLabel }) {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
      <div className="text-xs uppercase text-gray-500 dark:text-gray-400">{label}</div>
      <div className="text-2xl font-bold text-gray-900 dark:text-white mt-1 tabular-nums">
        {value.toLocaleString('id-ID')}
      </div>
      <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
        {pct != null ? `${pct.toFixed(1)}% ${pctLabel || ''}` : (sub || '')}
      </div>
    </div>
  )
}
