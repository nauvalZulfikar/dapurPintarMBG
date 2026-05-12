import { useEffect, useState } from 'react'
import {
  listSavedMenusFiltered, approveMenu, rejectMenu, lockMenu,
  archiveMenu, revertMenuToDraft, submitMenuForReview, cycleCheck, menuForecast,
} from '../api/menuPhase2'
import { useAuth } from '../hooks/useAuth'

const STATUS_PILL = {
  draft:           'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300',
  pending_review:  'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400',
  approved:        'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400',
  locked:          'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400',
  rejected:        'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400',
  archived:        'bg-gray-200 dark:bg-gray-600 text-gray-500 dark:text-gray-400',
}

const STATUS_LABEL = {
  draft: 'Draft', pending_review: 'Nunggu Review', approved: 'Disetujui',
  locked: 'Terkunci', rejected: 'Ditolak', archived: 'Arsip',
}

export default function MenuApproval() {
  const { hasPermission } = useAuth()
  const canApprove = hasPermission('menu.approve')
  const canSubmit = hasPermission('menu.submit_for_review')
  const canLock = hasPermission('menu.lock')

  const [filter, setFilter] = useState('pending_review')
  const [menus, setMenus] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState(null)

  const [cycleData, setCycleData] = useState(null)
  const [forecast, setForecast] = useState(null)
  const [forecastFrom, setForecastFrom] = useState(() => isoToday())
  const [forecastTo, setForecastTo] = useState(() => isoPlusDays(7))

  const refresh = async () => {
    setLoading(true); setError('')
    try {
      const params = filter === 'all' ? {} : { status: filter }
      const r = await listSavedMenusFiltered(params)
      setMenus(r.data.menus || [])
    } catch (e) { setError(e.response?.data?.detail || e.message) }
    finally { setLoading(false) }
  }
  useEffect(() => { refresh() /* eslint-disable-next-line */ }, [filter])
  useEffect(() => { cycleCheck(20).then(r => setCycleData(r.data)).catch(() => {}) }, [])

  const runForecast = async () => {
    setError('')
    try {
      const r = await menuForecast(forecastFrom, forecastTo)
      setForecast(r.data)
    } catch (e) { setError(e.response?.data?.detail || e.message) }
  }

  const action = async (id, fn, prompt = null) => {
    let notes = null
    if (prompt) {
      notes = window.prompt(prompt)
      if (notes === null) return
      if (!notes.trim()) { setError('Catatan wajib diisi.'); return }
    }
    setBusyId(id); setError('')
    try {
      await fn(id, notes)
      await refresh()
    } catch (e) { setError(e.response?.data?.detail || e.message) }
    finally { setBusyId(null) }
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-bold text-gray-800 dark:text-gray-100">Approval Menu</h2>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          Alur: Draft → Nunggu Review → Disetujui → Terkunci. Cycle 20 hari & forecast bahan ada di bawah.
        </p>
      </div>

      {error && <div className="text-sm text-red-600 bg-red-50 dark:bg-red-900/20 px-3 py-2 rounded">{error}</div>}

      {cycleData?.warnings?.length > 0 && (
        <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-300 dark:border-amber-700 rounded p-3">
          <div className="text-sm font-medium text-amber-800 dark:text-amber-300">⚠️ Siklus 20 hari BGN</div>
          <ul className="mt-1 text-xs text-amber-700 dark:text-amber-400 list-disc pl-5">
            {cycleData.warnings.map((w, i) => <li key={i}>{w}</li>)}
          </ul>
        </div>
      )}

      {/* Filter */}
      <div className="flex flex-wrap gap-2">
        {['pending_review', 'draft', 'approved', 'locked', 'rejected', 'archived', 'all'].map(s => (
          <button key={s} onClick={() => setFilter(s)}
            className={`px-3 py-1 text-xs rounded ${filter === s
              ? 'bg-blue-600 text-white'
              : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200'}`}>
            {STATUS_LABEL[s] || (s === 'all' ? 'Semua' : s)}
          </button>
        ))}
      </div>

      {/* Menus list */}
      {loading ? <div className="text-sm text-gray-500">Memuat...</div> : (
        <div className="bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700 overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 dark:bg-gray-700/50 text-gray-600 dark:text-gray-300 text-xs uppercase tracking-wider">
              <tr>
                <th className="px-3 py-2 text-left">Nama</th>
                <th className="px-3 py-2 text-left">Status</th>
                <th className="px-3 py-2 text-left">Source</th>
                <th className="px-3 py-2 text-left">Target Tgl</th>
                <th className="px-3 py-2 text-left">Dibuat</th>
                <th className="px-3 py-2 text-left">Catatan</th>
                <th className="px-3 py-2 text-right">Aksi</th>
              </tr>
            </thead>
            <tbody>
              {menus.length === 0 ? (
                <tr><td colSpan={7} className="text-center py-6 text-gray-400">Tidak ada menu di status ini.</td></tr>
              ) : menus.map(m => (
                <tr key={m.id} className="border-t border-gray-100 dark:border-gray-700">
                  <td className="px-3 py-2 font-medium">{m.name}</td>
                  <td className="px-3 py-2">
                    <span className={`text-xs px-2 py-0.5 rounded ${STATUS_PILL[m.status] || ''}`}>
                      {STATUS_LABEL[m.status] || m.status}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-xs text-gray-500">{m.source}</td>
                  <td className="px-3 py-2 text-xs">{m.target_date || '—'}</td>
                  <td className="px-3 py-2 text-xs text-gray-500">{m.created_by_username}</td>
                  <td className="px-3 py-2 text-xs text-gray-600 dark:text-gray-400 truncate max-w-[200px]">{m.review_notes || ''}</td>
                  <td className="px-3 py-2 text-right space-x-2 whitespace-nowrap">
                    {m.status === 'draft' && canSubmit &&
                      <button disabled={busyId === m.id} onClick={() => action(m.id, submitMenuForReview)}
                        className="text-xs text-blue-600 hover:underline disabled:opacity-50">Submit</button>}
                    {m.status === 'pending_review' && canApprove && (
                      <>
                        <button disabled={busyId === m.id} onClick={() => action(m.id, approveMenu)}
                          className="text-xs text-green-600 hover:underline disabled:opacity-50">Approve</button>
                        <button disabled={busyId === m.id} onClick={() => action(m.id, rejectMenu, 'Alasan reject:')}
                          className="text-xs text-red-600 hover:underline disabled:opacity-50">Reject</button>
                      </>
                    )}
                    {m.status === 'approved' && canLock &&
                      <button disabled={busyId === m.id} onClick={() => action(m.id, lockMenu)}
                        className="text-xs text-blue-600 hover:underline disabled:opacity-50">Lock</button>}
                    {m.status === 'rejected' && canSubmit &&
                      <button disabled={busyId === m.id} onClick={() => action(m.id, revertMenuToDraft)}
                        className="text-xs text-gray-600 hover:underline disabled:opacity-50">Revisi</button>}
                    {['approved', 'locked', 'draft', 'rejected'].includes(m.status) && (
                      <button disabled={busyId === m.id} onClick={() => action(m.id, archiveMenu)}
                        className="text-xs text-gray-500 hover:underline disabled:opacity-50">Arsip</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Forecast */}
      <div className="bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700 p-4">
        <h3 className="text-sm font-medium mb-3">Forecast Bahan dari Menu Approved</h3>
        <div className="flex flex-wrap gap-2 items-end mb-3">
          <label className="block">
            <span className="text-xs text-gray-600 dark:text-gray-400 block mb-1">Dari</span>
            <input type="date" value={forecastFrom} onChange={e => setForecastFrom(e.target.value)} className={inp} />
          </label>
          <label className="block">
            <span className="text-xs text-gray-600 dark:text-gray-400 block mb-1">Sampai</span>
            <input type="date" value={forecastTo} onChange={e => setForecastTo(e.target.value)} className={inp} />
          </label>
          <button onClick={runForecast} className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded">
            Hitung
          </button>
        </div>
        {forecast && (
          <div>
            <div className="text-xs text-gray-500 dark:text-gray-400 mb-2">
              {forecast.menus_analyzed} menu approved · {forecast.total_students} siswa target ·
              <span className="font-semibold text-blue-600 dark:text-blue-400 ml-1">
                Total est: Rp{(forecast.total_cost_idr || 0).toLocaleString('id-ID')}
              </span>
            </div>
            {Object.keys(forecast.bahan).length === 0 ? (
              <div className="text-sm text-gray-400 py-3 text-center">Tidak ada bahan dalam range ini.</div>
            ) : (
              <table className="w-full text-sm">
                <thead className="bg-gray-50 dark:bg-gray-700/50 text-xs">
                  <tr>
                    <th className="px-3 py-1.5 text-left">Bahan</th>
                    <th className="px-3 py-1.5 text-right">Total (g)</th>
                    <th className="px-3 py-1.5 text-right">Est Biaya</th>
                    <th className="px-3 py-1.5 text-right">Muncul</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(forecast.bahan).map(([name, info]) => (
                    <tr key={name} className="border-t border-gray-100 dark:border-gray-700">
                      <td className="px-3 py-1.5">{name}</td>
                      <td className="px-3 py-1.5 text-right tabular-nums">{info.grams_total.toLocaleString('id-ID')}</td>
                      <td className="px-3 py-1.5 text-right tabular-nums">Rp{info.est_cost_idr.toLocaleString('id-ID')}</td>
                      <td className="px-3 py-1.5 text-right">{info.appearances}x</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function isoToday() { return new Date().toISOString().slice(0, 10) }
function isoPlusDays(n) { const d = new Date(); d.setDate(d.getDate() + n); return d.toISOString().slice(0, 10) }
const inp = "px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
