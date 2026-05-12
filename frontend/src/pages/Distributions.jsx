import { useEffect, useState } from 'react'
import {
  schoolsByWave, distributionsToday, listLeftovers, createLeftover,
  listVehicles, createVehicle, listDrivers, createDriver,
} from '../api/distributions'
import { useAuth } from '../hooks/useAuth'

export default function Distributions() {
  const { hasPermission } = useAuth()
  const canLeftover = hasPermission('distribution.leftover')
  const canVehicle = hasPermission('vehicle.manage')
  const canDriver = hasPermission('driver.manage')

  const [today, setToday] = useState(null)
  const [waves, setWaves] = useState(null)
  const [leftovers, setLeftovers] = useState([])
  const [vehicles, setVehicles] = useState([])
  const [drivers, setDrivers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [tab, setTab] = useState('today')

  const refresh = async () => {
    setLoading(true); setError('')
    try {
      const [t, w, lv, v, d] = await Promise.all([
        distributionsToday(), schoolsByWave(), listLeftovers(),
        listVehicles().catch(() => ({ data: { vehicles: [] } })),
        listDrivers().catch(() => ({ data: { drivers: [] } })),
      ])
      setToday(t.data); setWaves(w.data)
      setLeftovers(lv.data.leftovers || [])
      setVehicles(v.data.vehicles || [])
      setDrivers(d.data.drivers || [])
    } catch (e) { setError(e.response?.data?.detail || e.message) }
    finally { setLoading(false) }
  }
  useEffect(() => { refresh() }, [])

  const onLeftover = async () => {
    const school = window.prompt('Sekolah?')
    if (!school) return
    const qtyStr = window.prompt('Jumlah sisa porsi?', '1')
    if (!qtyStr) return
    const qty = parseInt(qtyStr, 10)
    if (!qty || qty < 1) { setError('Qty invalid.'); return }
    const kategori = window.prompt('Kategori? return / extra / disposal', 'return')
    if (!kategori || !['return', 'extra', 'disposal'].includes(kategori)) {
      setError('Kategori invalid.'); return
    }
    const notes = window.prompt('Catatan (opsional)?') || ''
    try {
      await createLeftover({ qty, kategori, school_name: school, notes })
      refresh()
    } catch (e) { setError(e.response?.data?.detail || e.message) }
  }

  const onAddVehicle = async () => {
    const plate = window.prompt('Plat nomor?')
    if (!plate) return
    const model = window.prompt('Model (opsional)?') || ''
    try { await createVehicle({ plate, model, capacity_porsi: 0 }); refresh() }
    catch (e) { setError(e.response?.data?.detail || e.message) }
  }

  const onAddDriver = async () => {
    const name = window.prompt('Nama driver?')
    if (!name) return
    const phone = window.prompt('Nomor HP (opsional)?') || ''
    try { await createDriver({ name, phone }); refresh() }
    catch (e) { setError(e.response?.data?.detail || e.message) }
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-bold text-gray-800 dark:text-gray-100">Distribusi Hari Ini</h2>
        <p className="text-sm text-gray-500 dark:text-gray-400">Aggregate per sekolah · 2-wave classifier · receipt tracking · sisa porsi.</p>
      </div>

      {error && <div className="text-sm text-red-600 bg-red-50 dark:bg-red-900/20 px-3 py-2 rounded">{error}</div>}

      <div className="flex flex-wrap gap-2">
        {[
          { key: 'today', label: 'Aggregate Hari Ini' },
          { key: 'waves', label: 'Wave 1 & 2' },
          { key: 'leftovers', label: 'Sisa Porsi' },
          { key: 'fleet', label: 'Vehicle & Driver' },
        ].map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`px-3 py-1.5 text-sm rounded ${tab === t.key
              ? 'bg-blue-600 text-white' : 'bg-gray-100 dark:bg-gray-700'}`}>
            {t.label}
          </button>
        ))}
      </div>

      {loading ? <div className="text-sm text-gray-500">Memuat...</div> : (
        <>
          {tab === 'today' && today && (
            <div className="space-y-3">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <Stat label="Target" value={today.total_target} />
                <Stat label="Dispatched" value={today.total_dispatched} accent="blue" />
                <Stat label="Confirmed by Guru" value={today.total_confirmed} accent="green" />
                <Stat label="Scans Today" value={today.scans_today} />
              </div>
              <div className="bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 dark:bg-gray-700/50 text-xs uppercase">
                    <tr>
                      <th className="px-3 py-2 text-left">Sekolah</th>
                      <th className="px-3 py-2 text-center">Wave</th>
                      <th className="px-3 py-2 text-right">Target</th>
                      <th className="px-3 py-2 text-right">Dispatched</th>
                      <th className="px-3 py-2 text-right">Confirmed</th>
                      <th className="px-3 py-2 text-right">Sisa</th>
                      <th className="px-3 py-2 text-left">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {today.schools.map(s => {
                      const fully = s.confirmed >= s.target && s.target > 0
                      const partial = s.confirmed > 0 && s.confirmed < s.target
                      const status = fully ? 'fully' : partial ? 'partial' : 'pending'
                      return (
                        <tr key={s.school_id} className="border-t border-gray-100 dark:border-gray-700">
                          <td className="px-3 py-1.5">{s.school_name}</td>
                          <td className="px-3 py-1.5 text-center">
                            <span className={`text-xs px-2 py-0.5 rounded ${s.wave === 1 ? 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400' : 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400'}`}>
                              {s.wave}
                            </span>
                          </td>
                          <td className="px-3 py-1.5 text-right tabular-nums">{s.target}</td>
                          <td className="px-3 py-1.5 text-right tabular-nums">{s.dispatched}</td>
                          <td className="px-3 py-1.5 text-right tabular-nums">{s.confirmed}</td>
                          <td className="px-3 py-1.5 text-right tabular-nums">{s.leftover_total || '—'}</td>
                          <td className="px-3 py-1.5">
                            {status === 'fully' && <span className="text-xs text-green-600">✓ Lengkap</span>}
                            {status === 'partial' && <span className="text-xs text-amber-600">~ Sebagian</span>}
                            {status === 'pending' && <span className="text-xs text-gray-400">— Belum</span>}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {tab === 'waves' && waves && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <WaveCard wave={1} title="Wave 1 (08:00) — PAUD/TK/SD 1-3" data={waves.wave_1} total={waves.wave_1_total_students} accent="orange" />
              <WaveCard wave={2} title="Wave 2 (10:00) — SD 4-6/SMP/SMA" data={waves.wave_2} total={waves.wave_2_total_students} accent="purple" />
            </div>
          )}

          {tab === 'leftovers' && (
            <div className="space-y-3">
              {canLeftover && (
                <button onClick={onLeftover} className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded">
                  + Catat Sisa Porsi
                </button>
              )}
              <div className="bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 dark:bg-gray-700/50 text-xs uppercase">
                    <tr>
                      <th className="px-3 py-2 text-left">Sekolah</th>
                      <th className="px-3 py-2 text-right">Qty</th>
                      <th className="px-3 py-2 text-left">Kategori</th>
                      <th className="px-3 py-2 text-left">Catatan</th>
                      <th className="px-3 py-2 text-left">Waktu</th>
                    </tr>
                  </thead>
                  <tbody>
                    {leftovers.length === 0 ? (
                      <tr><td colSpan={5} className="text-center py-6 text-gray-400">Belum ada sisa porsi hari ini.</td></tr>
                    ) : leftovers.map(l => (
                      <tr key={l.id} className="border-t border-gray-100 dark:border-gray-700">
                        <td className="px-3 py-1.5">{l.school_name || '—'}</td>
                        <td className="px-3 py-1.5 text-right tabular-nums">{l.qty}</td>
                        <td className="px-3 py-1.5">
                          <span className={`text-xs px-2 py-0.5 rounded ${
                            l.kategori === 'return' ? 'bg-amber-100 dark:bg-amber-900/30 text-amber-700' :
                            l.kategori === 'extra' ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-700' :
                            'bg-red-100 dark:bg-red-900/30 text-red-700'
                          }`}>{l.kategori}</span>
                        </td>
                        <td className="px-3 py-1.5 text-xs text-gray-600 dark:text-gray-400">{l.notes}</td>
                        <td className="px-3 py-1.5 text-xs text-gray-500">{l.created_at?.slice(11, 19)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {tab === 'fleet' && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700 p-4">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="font-medium">🚐 Kendaraan</h3>
                  {canVehicle && <button onClick={onAddVehicle} className="text-xs text-blue-600 hover:underline">+ Tambah</button>}
                </div>
                {vehicles.length === 0 ? <div className="text-sm text-gray-400">Belum ada.</div> : (
                  <ul className="space-y-1 text-sm">
                    {vehicles.map(v => (
                      <li key={v.id} className="flex justify-between border-b border-gray-100 dark:border-gray-700 py-1">
                        <span className="font-mono">{v.plate}</span>
                        <span className="text-gray-500 text-xs">{v.model || '—'}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <div className="bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700 p-4">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="font-medium">👤 Driver</h3>
                  {canDriver && <button onClick={onAddDriver} className="text-xs text-blue-600 hover:underline">+ Tambah</button>}
                </div>
                {drivers.length === 0 ? <div className="text-sm text-gray-400">Belum ada.</div> : (
                  <ul className="space-y-1 text-sm">
                    {drivers.map(d => (
                      <li key={d.id} className="flex justify-between border-b border-gray-100 dark:border-gray-700 py-1">
                        <span>{d.name}</span>
                        <span className="text-gray-500 text-xs">{d.phone || '—'}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}

function Stat({ label, value, accent }) {
  const cls = accent === 'green' ? 'text-green-600 dark:text-green-400'
    : accent === 'blue' ? 'text-blue-600 dark:text-blue-400'
    : 'text-gray-700 dark:text-gray-200'
  return (
    <div className="bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700 p-3">
      <div className="text-xs text-gray-500 dark:text-gray-400">{label}</div>
      <div className={`text-2xl font-bold tabular-nums ${cls}`}>{(value || 0).toLocaleString('id-ID')}</div>
    </div>
  )
}

function WaveCard({ wave, title, data, total, accent }) {
  const bg = accent === 'orange' ? 'border-orange-300 dark:border-orange-700' : 'border-purple-300 dark:border-purple-700'
  return (
    <div className={`bg-white dark:bg-gray-800 rounded border-2 ${bg} p-4`}>
      <div className="font-semibold mb-2">{title}</div>
      <div className="text-xs text-gray-500 mb-3">{data.length} sekolah · {total.toLocaleString('id-ID')} siswa</div>
      <ul className="text-sm space-y-1 max-h-80 overflow-y-auto">
        {data.map(s => (
          <li key={s.id} className="flex justify-between border-b border-gray-100 dark:border-gray-700 py-1">
            <span className="truncate">{s.name}</span>
            <span className="text-xs text-gray-500 tabular-nums">{s.student_count} siswa · {s.distance}m</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
