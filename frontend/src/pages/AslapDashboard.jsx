import { useEffect, useState } from 'react'
import {
  getTodayChecklist, submitChecklist,
  submitWaterQuality, listWaterQuality,
  createObservation, listObservations,
  createCommLog, listCommLogs,
  generateWeeklyReport, listWeeklyReports, submitWeeklyReport,
} from '../api/aslap'
import { useAuth } from '../hooks/useAuth'

export default function AslapDashboard() {
  const { hasPermission } = useAuth()
  const canChecklist = hasPermission('checklist.daily')
  const canWater = hasPermission('water_quality.log')
  const canObs = hasPermission('production_observation.create')
  const canComm = hasPermission('school_comm_log.create')
  const canGenReport = hasPermission('aslap_report.generate')
  const canSignoff = hasPermission('aslap_report.signoff')

  const [tab, setTab] = useState('checklist')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  // Checklist
  const [checklist, setChecklist] = useState(null)

  // Water
  const [waterLogs, setWaterLogs] = useState([])

  // Observations
  const [observations, setObservations] = useState([])

  // Comm
  const [commLogs, setCommLogs] = useState([])

  // Reports
  const [reports, setReports] = useState([])

  const refresh = async () => {
    setError('')
    try {
      const [ck, wl, ob, co, rep] = await Promise.all([
        getTodayChecklist(),
        listWaterQuality({ from_date: isoDaysAgo(7), to_date: isoToday() }),
        listObservations({ from_date: isoDaysAgo(7), to_date: isoToday() }),
        listCommLogs(),
        listWeeklyReports(),
      ])
      setChecklist(ck.data)
      setWaterLogs(wl.data.logs || [])
      setObservations(ob.data.observations || [])
      setCommLogs(co.data.logs || [])
      setReports(rep.data.reports || [])
    } catch (e) { setError(e.response?.data?.detail || e.message) }
  }
  useEffect(() => { refresh() }, [])

  // Checklist handlers
  const updateItem = (key, field, val) => {
    setChecklist({
      ...checklist,
      items: checklist.items.map(it => it.key === key ? { ...it, [field]: val, ok: field === 'value' ? !!val : it.ok } : it),
    })
  }
  const onSubmitChecklist = async (asDraft = false) => {
    setBusy(true); setError('')
    try {
      await submitChecklist({
        items: checklist.items, submit: !asDraft, notes: checklist.notes || null,
      })
      refresh()
    } catch (e) { setError(e.response?.data?.detail || e.message) }
    finally { setBusy(false) }
  }

  // Water handlers
  const onAddWater = async () => {
    const tds = window.prompt('TDS (ppm)?')
    if (!tds) return
    const ph = window.prompt('pH (e.g. 7.2)?')
    if (!ph) return
    const bau = window.prompt('Bau? (normal / amis / kimia)', 'normal')
    if (!bau) return
    const warna = window.prompt('Warna? (jernih / keruh / kuning)', 'jernih')
    if (!warna) return
    try {
      const r = await submitWaterQuality({ tds_ppm: parseInt(tds, 10), ph, bau, warna })
      if (r.data.alert_count > 0) alert(`⚠️ ${r.data.alert_count} ALERT:\n${r.data.alerts.join('\n')}`)
      refresh()
    } catch (e) { setError(e.response?.data?.detail || e.message) }
  }

  // Observation handler
  const onAddObservation = async () => {
    const suhu = window.prompt('Suhu masak (°C)?', '95')
    if (!suhu) return
    const waktu = window.prompt('Waktu masak (menit)?', '30')
    if (!waktu) return
    const cleanStr = window.prompt('Kebersihan tim OK? (y/n)', 'y')
    if (!cleanStr) return
    const notes = window.prompt('Catatan (opsional)?') || ''
    try {
      await createObservation({
        suhu_masak: parseInt(suhu, 10),
        waktu_menit: parseInt(waktu, 10),
        kebersihan_ok: cleanStr.toLowerCase().startsWith('y'),
        notes,
      })
      refresh()
    } catch (e) { setError(e.response?.data?.detail || e.message) }
  }

  // Comm handler
  const onAddComm = async () => {
    const school = window.prompt('Nama sekolah?')
    if (!school) return
    const channel = window.prompt('Channel? (call / wa / email / visit / sms)', 'wa')
    if (!channel) return
    const topic = window.prompt('Topik?')
    if (!topic) return
    const response = window.prompt('Response (opsional)?') || ''
    try {
      await createCommLog({ school_name: school, channel, topic, response })
      refresh()
    } catch (e) { setError(e.response?.data?.detail || e.message) }
  }

  // Report handler
  const onGenReport = async () => {
    const start = window.prompt('Week start (Senin)?', isoDaysAgo(7))
    if (!start) return
    const end = window.prompt('Week end?', isoToday())
    if (!end) return
    try {
      await generateWeeklyReport({ week_start: start, week_end: end })
      refresh()
    } catch (e) { setError(e.response?.data?.detail || e.message) }
  }
  const onSubmitReport = async (id) => {
    if (!confirm('Submit report ke Yayasan?')) return
    try { await submitWeeklyReport(id); refresh() }
    catch (e) { setError(e.response?.data?.detail || e.message) }
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-bold text-gray-800 dark:text-gray-100">ASLAP — Operasi Harian</h2>
        <p className="text-sm text-gray-500 dark:text-gray-400">Daily checklist · water quality · production observation · komunikasi sekolah · weekly report</p>
      </div>

      {error && <div className="text-sm text-red-600 bg-red-50 dark:bg-red-900/20 px-3 py-2 rounded">{error}</div>}

      <div className="flex flex-wrap gap-2">
        {[
          { key: 'checklist', label: 'Checklist Hari Ini' },
          { key: 'water',     label: 'Water Quality' },
          { key: 'obs',       label: 'Production Obs' },
          { key: 'comm',      label: 'Komunikasi Sekolah' },
          { key: 'reports',   label: 'Weekly Report' },
        ].map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`px-3 py-1.5 text-sm rounded ${tab === t.key ? 'bg-blue-600 text-white' : 'bg-gray-100 dark:bg-gray-700'}`}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'checklist' && checklist && (
        <div className="bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700 p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-medium">Checklist {checklist.checklist_date}</h3>
            <span className={`text-xs px-2 py-0.5 rounded ${
              checklist.status === 'submitted'
                ? 'bg-green-100 dark:bg-green-900/30 text-green-700' : 'bg-amber-100 dark:bg-amber-900/30 text-amber-700'
            }`}>{checklist.status}</span>
          </div>
          <div className="space-y-2">
            {checklist.items.map(it => (
              <div key={it.key} className="flex items-center gap-3 py-2 border-b border-gray-100 dark:border-gray-700">
                <div className="flex-1">
                  <div className="text-sm">{it.label} {it.required && <span className="text-red-500">*</span>}</div>
                </div>
                {it.type === 'bool' ? (
                  <div className="flex gap-2">
                    <button
                      disabled={checklist.status === 'submitted'}
                      onClick={() => updateItem(it.key, 'value', true)}
                      className={`px-3 py-1 text-xs rounded ${it.value === true ? 'bg-green-600 text-white' : 'bg-gray-200 dark:bg-gray-700'}`}>
                      ✓ OK
                    </button>
                    <button
                      disabled={checklist.status === 'submitted'}
                      onClick={() => updateItem(it.key, 'value', false)}
                      className={`px-3 py-1 text-xs rounded ${it.value === false ? 'bg-red-600 text-white' : 'bg-gray-200 dark:bg-gray-700'}`}>
                      ✗ NO
                    </button>
                  </div>
                ) : (
                  <input
                    type="number"
                    disabled={checklist.status === 'submitted'}
                    value={it.value ?? ''}
                    onChange={e => updateItem(it.key, 'value', parseFloat(e.target.value) || 0)}
                    className="w-24 px-2 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700"
                  />
                )}
              </div>
            ))}
          </div>
          {canChecklist && checklist.status !== 'submitted' && (
            <div className="mt-4 flex gap-2">
              <button disabled={busy} onClick={() => onSubmitChecklist(false)}
                className="px-3 py-1.5 bg-green-600 hover:bg-green-700 text-white text-sm rounded disabled:opacity-50">
                Submit Checklist
              </button>
              <button disabled={busy} onClick={() => onSubmitChecklist(true)}
                className="px-3 py-1.5 bg-gray-200 dark:bg-gray-700 text-sm rounded disabled:opacity-50">
                Save Draft
              </button>
            </div>
          )}
        </div>
      )}

      {tab === 'water' && (
        <div className="space-y-3">
          {canWater && <button onClick={onAddWater} className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded">+ Tes Air Sekarang</button>}
          <div className="bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700 overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-gray-700/50 text-xs uppercase">
                <tr>
                  <th className="px-3 py-2 text-left">Tanggal</th>
                  <th className="px-3 py-2 text-right">TDS (ppm)</th>
                  <th className="px-3 py-2 text-right">pH</th>
                  <th className="px-3 py-2 text-left">Bau</th>
                  <th className="px-3 py-2 text-left">Warna</th>
                  <th className="px-3 py-2 text-left">Alerts</th>
                </tr>
              </thead>
              <tbody>
                {waterLogs.length === 0 ? (
                  <tr><td colSpan={6} className="text-center py-6 text-gray-400">Belum ada test air.</td></tr>
                ) : waterLogs.map(l => (
                  <tr key={l.id} className={`border-t border-gray-100 dark:border-gray-700 ${l.alert_count > 0 ? 'bg-red-50 dark:bg-red-900/10' : ''}`}>
                    <td className="px-3 py-1.5 text-xs">{l.log_date}</td>
                    <td className={`px-3 py-1.5 text-right tabular-nums ${l.tds_ppm > 500 ? 'text-red-600 font-bold' : ''}`}>{l.tds_ppm}</td>
                    <td className={`px-3 py-1.5 text-right tabular-nums ${parseFloat(l.ph) < 6.5 || parseFloat(l.ph) > 8.5 ? 'text-red-600 font-bold' : ''}`}>{l.ph}</td>
                    <td className="px-3 py-1.5">{l.bau}</td>
                    <td className="px-3 py-1.5">{l.warna}</td>
                    <td className="px-3 py-1.5 text-xs text-red-600">
                      {l.alerts?.length > 0 ? `⚠️ ${l.alerts.join(', ')}` : <span className="text-green-600">✓</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'obs' && (
        <div className="space-y-3">
          {canObs && <button onClick={onAddObservation} className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded">+ Catat Observasi</button>}
          <div className="bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700 overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-gray-700/50 text-xs uppercase">
                <tr>
                  <th className="px-3 py-2 text-left">Waktu</th>
                  <th className="px-3 py-2 text-right">Batch</th>
                  <th className="px-3 py-2 text-right">Suhu (°C)</th>
                  <th className="px-3 py-2 text-right">Waktu (m)</th>
                  <th className="px-3 py-2 text-left">Kebersihan</th>
                  <th className="px-3 py-2 text-left">Catatan</th>
                </tr>
              </thead>
              <tbody>
                {observations.length === 0 ? (
                  <tr><td colSpan={6} className="text-center py-6 text-gray-400">Belum ada observasi.</td></tr>
                ) : observations.map(o => (
                  <tr key={o.id} className="border-t border-gray-100 dark:border-gray-700">
                    <td className="px-3 py-1.5 text-xs">{o.observed_at?.slice(0, 16).replace('T', ' ')}</td>
                    <td className="px-3 py-1.5 text-right">{o.batch_id ? `B-${o.batch_id}` : '—'}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums">{o.suhu_masak}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums">{o.waktu_menit}</td>
                    <td className="px-3 py-1.5">{o.kebersihan_ok ? <span className="text-green-600">✓</span> : <span className="text-red-600">✗</span>}</td>
                    <td className="px-3 py-1.5 text-xs text-gray-500">{o.notes}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'comm' && (
        <div className="space-y-3">
          {canComm && <button onClick={onAddComm} className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded">+ Catat Komunikasi</button>}
          <div className="bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700 overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-gray-700/50 text-xs uppercase">
                <tr>
                  <th className="px-3 py-2 text-left">Waktu</th>
                  <th className="px-3 py-2 text-left">Sekolah</th>
                  <th className="px-3 py-2 text-left">Channel</th>
                  <th className="px-3 py-2 text-left">Topik</th>
                  <th className="px-3 py-2 text-left">Response</th>
                </tr>
              </thead>
              <tbody>
                {commLogs.length === 0 ? (
                  <tr><td colSpan={5} className="text-center py-6 text-gray-400">Belum ada komunikasi.</td></tr>
                ) : commLogs.map(l => (
                  <tr key={l.id} className="border-t border-gray-100 dark:border-gray-700">
                    <td className="px-3 py-1.5 text-xs">{l.created_at?.slice(0, 16).replace('T', ' ')}</td>
                    <td className="px-3 py-1.5">{l.school_name}</td>
                    <td className="px-3 py-1.5"><span className="text-xs px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-700">{l.channel}</span></td>
                    <td className="px-3 py-1.5 text-xs">{l.topic}</td>
                    <td className="px-3 py-1.5 text-xs text-gray-500">{l.response}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'reports' && (
        <div className="space-y-3">
          {canGenReport && <button onClick={onGenReport} className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded">+ Generate Laporan Mingguan</button>}
          <div className="space-y-2">
            {reports.length === 0 ? (
              <div className="text-sm text-gray-400 text-center py-8">Belum ada laporan mingguan.</div>
            ) : reports.map(r => (
              <div key={r.id} className="bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700 p-4">
                <div className="flex items-center justify-between mb-2">
                  <div className="font-semibold">Week {r.week_start} → {r.week_end}</div>
                  <span className={`text-xs px-2 py-0.5 rounded ${
                    r.status === 'submitted' ? 'bg-green-100 dark:bg-green-900/30 text-green-700' : 'bg-amber-100 dark:bg-amber-900/30 text-amber-700'
                  }`}>{r.status}</span>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                  <div>📋 Checklist: {r.summary.checklists?.submitted}/{r.summary.checklists?.total}</div>
                  <div>💧 Water: {r.summary.water_quality?.with_alerts}/{r.summary.water_quality?.total} alert</div>
                  <div>🍳 Obs: {r.summary.production_observations?.total} ({r.summary.production_observations?.unclean} unclean)</div>
                  <div>📞 Comm: {r.summary.school_communications?.total} ({r.summary.school_communications?.need_followup} followup)</div>
                </div>
                {canSignoff && r.status !== 'submitted' && (
                  <button onClick={() => onSubmitReport(r.id)} className="mt-2 px-3 py-1 text-xs bg-green-600 hover:bg-green-700 text-white rounded">
                    ✓ Submit ke Yayasan
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function isoToday() { return new Date().toISOString().slice(0, 10) }
function isoDaysAgo(n) { const d = new Date(); d.setDate(d.getDate() - n); return d.toISOString().slice(0, 10) }
