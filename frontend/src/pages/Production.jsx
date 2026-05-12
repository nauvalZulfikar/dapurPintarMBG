import { useEffect, useState, useRef } from 'react'
import { Html5Qrcode } from 'html5-qrcode'
import {
  todayMenu, listBatches, getBatch, startBatch,
  qcApprove, endBatch, scanProcessing,
} from '../api/production'
import { useAuth } from '../hooks/useAuth'

const STATUS_PILL = {
  started:    'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400',
  qc_pending: 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400',
  qc_passed:  'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400',
  ended:      'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300',
  aborted:    'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400',
}

export default function Production() {
  const { hasPermission } = useAuth()
  const canStart = hasPermission('production.start_batch')
  const canEnd = hasPermission('production.end_batch')
  const canQC = hasPermission('production.qc_approve')
  const canScan = hasPermission('production.processing_scan')

  const [menus, setMenus] = useState([])
  const [batches, setBatches] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busyKey, setBusyKey] = useState(null)
  const [viewing, setViewing] = useState(null)

  const refresh = async () => {
    setLoading(true); setError('')
    try {
      const [m, b] = await Promise.all([todayMenu(), listBatches()])
      setMenus(m.data.menus || [])
      setBatches(b.data.batches || [])
    } catch (e) { setError(e.response?.data?.detail || e.message) }
    finally { setLoading(false) }
  }
  useEffect(() => { refresh() }, [])

  const reload = async (id) => {
    try { const r = await getBatch(id); setViewing(r.data) }
    catch (e) { setError(e.response?.data?.detail || e.message) }
  }

  const onStart = async (menu) => {
    const porsiStr = window.prompt(`Berapa porsi untuk "${menu.name}"?`, '100')
    if (!porsiStr) return
    const porsi = parseInt(porsiStr, 10)
    if (!porsi || porsi < 1) { setError('Porsi invalid.'); return }

    // Dry-run preview
    setBusyKey(`start-${menu.id}`); setError('')
    try {
      const dryR = await startBatch({ menu_plan_id: menu.id, target_porsi: porsi, dry_run: true })
      const plan = dryR.data.plan || []
      const shortages = dryR.data.shortages || []
      let msg = `Plan untuk ${porsi} porsi "${menu.name}":\n\n`
      plan.forEach(line => {
        msg += `• ${line.ingredient_name}: ${line.grams_needed}g (${line.containers.length} container)`
        if (line.shortage_grams > 0) msg += `  ⚠️ KURANG ${line.shortage_grams}g`
        msg += '\n'
      })
      if (shortages.length > 0) {
        alert(msg + '\n\nGAK BISA START — bahan kurang.')
        return
      }
      if (!confirm(msg + '\nLanjutkan start batch?')) return

      const r = await startBatch({ menu_plan_id: menu.id, target_porsi: porsi, dry_run: false })
      alert(`✅ Batch ${r.data.id} started! Timer 6 jam berjalan.`)
      refresh()
    } catch (e) { setError(e.response?.data?.detail || e.message) }
    finally { setBusyKey(null) }
  }

  const onQC = async (batch) => {
    if (!canQC) return
    const loc = window.prompt('Lokasi sample retention?', 'Kulkas QC')
    if (loc === null) return
    const notes = window.prompt('Catatan QC (opsional)?') || ''
    setBusyKey(`qc-${batch.id}`); setError('')
    try {
      await qcApprove(batch.id, { sample_location: loc, notes })
      reload(batch.id); refresh()
    } catch (e) { setError(e.response?.data?.detail || e.message) }
    finally { setBusyKey(null) }
  }

  const onEnd = async (batch) => {
    if (!confirm(`Selesaikan batch ${batch.id}?`)) return
    setBusyKey(`end-${batch.id}`); setError('')
    try {
      await endBatch(batch.id)
      reload(batch.id); refresh()
    } catch (e) { setError(e.response?.data?.detail || e.message) }
    finally { setBusyKey(null) }
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-bold text-gray-800 dark:text-gray-100">Production — Tablet Kepala Chef</h2>
        <p className="text-sm text-gray-500 dark:text-gray-400">Mulai batch dari menu approved. FIFO auto-debit. Timer 6 jam SOP BGN.</p>
      </div>

      {error && <div className="text-sm text-red-600 bg-red-50 dark:bg-red-900/20 px-3 py-2 rounded">{error}</div>}

      {/* Today's Menu */}
      <div className="bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700 p-4">
        <h3 className="font-medium mb-3">Menu Approved Hari Ini</h3>
        {loading ? <div className="text-sm text-gray-500">Memuat...</div> : (
          menus.length === 0 ? (
            <div className="text-sm text-gray-400">Belum ada menu approved untuk hari ini. Cek halaman Approval Menu.</div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {menus.map(m => (
                <div key={m.id} className="border border-gray-200 dark:border-gray-700 rounded p-3 hover:border-blue-400">
                  <div className="font-semibold text-gray-800 dark:text-gray-100">{m.name}</div>
                  <div className="text-xs text-gray-500 mt-1">status: {m.status}</div>
                  <div className="text-xs text-gray-600 dark:text-gray-300 mt-2 space-y-0.5">
                    {(m.recipe || []).slice(0, 5).map((r, i) => (
                      <div key={i}>• {r.name}: {r.grams}g/porsi</div>
                    ))}
                    {(m.recipe || []).length > 5 && <div className="text-gray-400">+{m.recipe.length - 5} bahan lagi</div>}
                  </div>
                  {canStart && (
                    <button disabled={busyKey === `start-${m.id}`} onClick={() => onStart(m)}
                      className="mt-3 w-full px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded disabled:opacity-50">
                      ▶ Confirm & Mulai Produksi
                    </button>
                  )}
                </div>
              ))}
            </div>
          )
        )}
      </div>

      {/* Active Batches */}
      <div className="bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700 p-4">
        <h3 className="font-medium mb-3">Batch Aktif</h3>
        {batches.length === 0 ? (
          <div className="text-sm text-gray-400">Belum ada batch.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-gray-700/50 text-xs uppercase">
                <tr>
                  <th className="px-2 py-1.5 text-left">ID</th>
                  <th className="px-2 py-1.5 text-left">Menu</th>
                  <th className="px-2 py-1.5 text-right">Porsi</th>
                  <th className="px-2 py-1.5 text-left">Status</th>
                  <th className="px-2 py-1.5 text-left">Timer</th>
                  <th className="px-2 py-1.5 text-right">Aksi</th>
                </tr>
              </thead>
              <tbody>
                {batches.map(b => {
                  const overdue = b.elapsed_minutes && b.elapsed_minutes > 5 * 60 && !b.ended_at
                  return (
                    <tr key={b.id} className="border-t border-gray-100 dark:border-gray-700">
                      <td className="px-2 py-1.5 font-mono text-xs">B-{b.id}</td>
                      <td className="px-2 py-1.5">{b.menu_name}</td>
                      <td className="px-2 py-1.5 text-right">{b.target_porsi}</td>
                      <td className="px-2 py-1.5"><span className={`text-xs px-2 py-0.5 rounded ${STATUS_PILL[b.status] || ''}`}>{b.status}</span></td>
                      <td className={`px-2 py-1.5 text-xs ${overdue ? 'text-red-600 font-semibold' : ''}`}>
                        {b.ended_at ? '—' : (b.elapsed_minutes ? `${Math.floor(b.elapsed_minutes / 60)}h ${b.elapsed_minutes % 60}m` : '—')}
                        {overdue && ' ⚠️'}
                      </td>
                      <td className="px-2 py-1.5 text-right space-x-2 whitespace-nowrap">
                        <button onClick={() => reload(b.id)} className="text-xs text-blue-600 hover:underline">Detail</button>
                        {canQC && b.status === 'started' && (
                          <button disabled={busyKey === `qc-${b.id}`} onClick={() => onQC(b)}
                            className="text-xs text-green-600 hover:underline disabled:opacity-50">QC OK</button>
                        )}
                        {canEnd && ['started', 'qc_passed'].includes(b.status) && (
                          <button disabled={busyKey === `end-${b.id}`} onClick={() => onEnd(b)}
                            className="text-xs text-gray-600 hover:underline disabled:opacity-50">Selesai</button>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {canScan && <ProcessingScanCard />}

      {viewing && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setViewing(null)}>
          <div className="bg-white dark:bg-gray-800 rounded p-6 max-w-3xl w-full max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <h3 className="text-lg font-bold mb-3">Batch B-{viewing.id} — {viewing.menu_name}</h3>
            <div className="text-sm text-gray-600 dark:text-gray-400 space-y-1 mb-3">
              <div>Status: <span className={`text-xs px-2 py-0.5 rounded ${STATUS_PILL[viewing.status] || ''}`}>{viewing.status}</span></div>
              <div>Porsi: {viewing.target_porsi}</div>
              <div>Timer: {viewing.elapsed_minutes}m {viewing.sop_breached && <span className="text-red-600 font-semibold">⚠️ Lewat SOP</span>}</div>
            </div>

            <h4 className="text-sm font-semibold mt-4 mb-2">Container yang dipakai ({viewing.consumed_items?.length || 0})</h4>
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-gray-700/50 text-xs">
                <tr>
                  <th className="px-2 py-1.5 text-left">Item ID</th>
                  <th className="px-2 py-1.5 text-left">Bahan</th>
                  <th className="px-2 py-1.5 text-right">Gram</th>
                </tr>
              </thead>
              <tbody>
                {(viewing.consumed_items || []).map(ci => (
                  <tr key={ci.id} className="border-t border-gray-100 dark:border-gray-700">
                    <td className="px-2 py-1.5 font-mono text-xs">{ci.item_id}</td>
                    <td className="px-2 py-1.5">{ci.ingredient_name}</td>
                    <td className="px-2 py-1.5 text-right tabular-nums">{ci.grams_used.toLocaleString('id-ID')}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            {viewing.samples?.length > 0 && (
              <>
                <h4 className="text-sm font-semibold mt-4 mb-2">Food Samples (48h retention)</h4>
                <ul className="text-sm space-y-1">
                  {viewing.samples.map(s => (
                    <li key={s.id} className="text-gray-600 dark:text-gray-400">
                      📦 {s.location} · expire {s.expire_at?.slice(0, 16).replace('T', ' ')}
                    </li>
                  ))}
                </ul>
              </>
            )}

            <button onClick={() => setViewing(null)} className="mt-4 px-3 py-1.5 bg-gray-200 dark:bg-gray-700 text-sm rounded">Tutup</button>
          </div>
        </div>
      )}
    </div>
  )
}


function ProcessingScanCard() {
  const [scanning, setScanning] = useState(false)
  const [scanResult, setScanResult] = useState(null)
  const [error, setError] = useState('')
  const divRef = useRef(null)
  const qrRef = useRef(null)

  const start = async () => {
    setError(''); setScanResult(null); setScanning(true)
    setTimeout(async () => {
      try {
        const div = divRef.current
        if (!div) return
        const qr = new Html5Qrcode(div.id)
        qrRef.current = qr
        await qr.start(
          { facingMode: 'environment' },
          { fps: 10, qrbox: { width: 280, height: 140 } },
          async (decoded) => {
            const code = String(decoded || '').trim().toUpperCase()
            try {
              const r = await scanProcessing(code)
              setScanResult({ code, ok: r.data.ok, reason: r.data.reason })
            } catch (e) {
              setScanResult({ code, ok: false, reason: e.response?.data?.detail || e.message })
            }
            stop()
          },
          () => {}
        )
      } catch (e) {
        setError('Tidak bisa akses kamera. Pastikan permission diberikan + HTTPS.')
        setScanning(false)
      }
    }, 50)
  }

  const stop = async () => {
    setScanning(false)
    const qr = qrRef.current
    if (qr) {
      try { await qr.stop(); qr.clear() } catch { /* ignore */ }
      qrRef.current = null
    }
  }

  useEffect(() => () => { stop() /* eslint-disable-next-line */ }, [])

  return (
    <div className="bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700 p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-medium">Tablet Scan — Step Processing (JWT auth)</h3>
        <button onClick={scanning ? stop : start}
          className={`px-3 py-1.5 text-sm text-white rounded ${scanning ? 'bg-red-600' : 'bg-blue-600 hover:bg-blue-700'}`}>
          {scanning ? '✕ Stop' : '📷 Scan'}
        </button>
      </div>
      {error && <div className="text-xs text-red-600 mb-2">{error}</div>}
      {scanning && (
        <div className="rounded border border-gray-300 dark:border-gray-600 p-2 bg-gray-900">
          <div id="processing-scanner" ref={divRef} />
          <p className="text-xs text-gray-300 mt-1">Arahkan kamera ke barcode container BHN.</p>
        </div>
      )}
      {scanResult && (
        <div className={`mt-2 text-sm px-3 py-2 rounded ${scanResult.ok
          ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400'
          : 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400'}`}>
          {scanResult.ok ? '✅ Processed' : '❌ ' + (scanResult.reason || 'gagal')}: <span className="font-mono">{scanResult.code}</span>
        </div>
      )}
    </div>
  )
}
