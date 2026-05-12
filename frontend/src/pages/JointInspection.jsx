import { useEffect, useState } from 'react'
import {
  listInspections, getInspection, createInspection,
  submitSignoff, acceptInspectionLine, rejectInspectionLine, finalizeInspection,
  listPurchaseOrders,
} from '../api/inspections'
import { useAuth } from '../hooks/useAuth'

const STATUS_PILL = {
  pending:    'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300',
  inspecting: 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400',
  accepted:   'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400',
  rejected:   'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400',
  partial:    'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400',
}

const ROLE_LABEL = {
  quality:  'Ahli Gizi (kualitas)',
  quantity: 'Akuntan (kuantitas)',
  physical: 'ASLAP (fisik)',
}

const ROLE_PERM = {
  quality:  'inspection.signoff_quality',
  quantity: 'inspection.signoff_quantity',
  physical: 'inspection.signoff_physical',
}

export default function JointInspection() {
  const { hasPermission } = useAuth()
  const canCreate = hasPermission('inspection.create')
  const canSplit = hasPermission('container.split')
  const canReject = hasPermission('inspection.reject_bahan')
  const canFinalize = hasPermission('inspection.finalize')

  const [list, setList] = useState([])
  const [pos, setPos] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [filter, setFilter] = useState('inspecting')
  const [adding, setAdding] = useState(false)
  const [viewing, setViewing] = useState(null)
  const [busyKey, setBusyKey] = useState(null)

  const [newPoId, setNewPoId] = useState('')
  const [newNotes, setNewNotes] = useState('')

  const refresh = async () => {
    setLoading(true); setError('')
    try {
      const r = await listInspections(filter === 'all' ? {} : { status: filter })
      setList(r.data.inspections || [])
    } catch (e) { setError(e.response?.data?.detail || e.message) }
    finally { setLoading(false) }
  }
  useEffect(() => { refresh() /* eslint-disable-next-line */ }, [filter])
  useEffect(() => { listPurchaseOrders({ status: 'sent' }).then(r => setPos(r.data.purchase_orders || [])).catch(() => {}) }, [])

  const reloadDetail = async (id) => {
    try { const r = await getInspection(id); setViewing(r.data) }
    catch (e) { setError(e.response?.data?.detail || e.message) }
  }

  const open = (insp) => reloadDetail(insp.id)

  const create = async () => {
    if (!newPoId) { setError('Pilih PO dulu.'); return }
    setError('')
    try {
      const r = await createInspection({ po_id: Number(newPoId), notes: newNotes })
      setAdding(false); setNewPoId(''); setNewNotes('')
      refresh()
      open(r.data)
    } catch (e) { setError(e.response?.data?.detail || e.message) }
  }

  const doSignoff = async (role, status) => {
    if (!viewing) return
    if (!hasPermission(ROLE_PERM[role])) {
      setError(`Anda tidak punya permission ${ROLE_PERM[role]}.`); return
    }
    let notes = ''
    if (status === 'rejected') {
      const n = window.prompt(`Catatan reject sebagai ${ROLE_LABEL[role]}:`)
      if (n === null) return
      if (!n.trim()) { setError('Catatan wajib.'); return }
      notes = n
    }
    setBusyKey(`signoff-${role}`); setError('')
    try {
      await submitSignoff(viewing.id, { role, status, notes })
      reloadDetail(viewing.id)
    } catch (e) { setError(e.response?.data?.detail || e.message) }
    finally { setBusyKey(null) }
  }

  const acceptLine = async (line) => {
    if (!viewing || !canSplit) return
    // Quick UX: ask total containers + simple equal split (or default to 1 container = full weight)
    const expected = line.expected_weight_grams || 0
    const countStr = window.prompt(
      `Berapa container untuk ${line.item_name}?\n` +
      `(expected ${expected.toLocaleString('id-ID')}g)\n\n` +
      `Tip: untuk split tidak rata, gunakan halaman PO advanced.`,
      String(line.po_line_id ? Math.max(1, Math.round(expected / 10000)) : 1),
    )
    if (!countStr) return
    const n = parseInt(countStr, 10)
    if (!n || n < 1) { setError('Jumlah container minimal 1.'); return }

    const totalStr = window.prompt(`Total berat aktual (gram)? Untuk ${n} container.`, String(expected))
    if (!totalStr) return
    const total = parseInt(totalStr, 10)
    if (!total || total < 1) { setError('Total berat invalid.'); return }
    const per = Math.floor(total / n)
    const remainder = total - per * n
    const containers = Array.from({ length: n }, (_, i) => ({ weight_grams: i === 0 ? per + remainder : per }))

    const routing = window.prompt('Storage routing? cook_immediate / refrigerate / freeze', 'refrigerate')
    if (!routing || !['cook_immediate', 'refrigerate', 'freeze'].includes(routing)) {
      setError('Routing invalid.'); return
    }

    setBusyKey(`accept-${line.id}`); setError('')
    try {
      const r = await acceptInspectionLine(viewing.id, line.id, { containers, storage_routing: routing })
      alert(`✅ ${r.data.labels_queued} label barcode di-queue ke printer dapur.\nItems: ${r.data.item_ids.length}`)
      reloadDetail(viewing.id)
    } catch (e) { setError(e.response?.data?.detail || e.message) }
    finally { setBusyKey(null) }
  }

  const rejectLine = async (line) => {
    if (!viewing || !canReject) return
    const reason = window.prompt(`Alasan reject ${line.item_name}?`)
    if (!reason || !reason.trim()) return
    const severity = window.prompt('Severity? low / medium / high', 'medium')
    if (!severity || !['low', 'medium', 'high'].includes(severity)) {
      setError('Severity invalid.'); return
    }
    setBusyKey(`reject-${line.id}`); setError('')
    try {
      await rejectInspectionLine(viewing.id, line.id, { reason, severity })
      reloadDetail(viewing.id)
    } catch (e) { setError(e.response?.data?.detail || e.message) }
    finally { setBusyKey(null) }
  }

  const onFinalize = async () => {
    if (!viewing || !canFinalize) return
    if (!confirm('Finalize inspection? Status akan dihitung dari sign-off + line outcomes.')) return
    setBusyKey('finalize'); setError('')
    try {
      const r = await finalizeInspection(viewing.id)
      setViewing(r.data)
      refresh()
    } catch (e) { setError(e.response?.data?.detail || e.message) }
    finally { setBusyKey(null) }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-gray-800 dark:text-gray-100">Joint Inspection</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400">3-orang sign-off saat bahan datang dari supplier (BGN compliance).</p>
        </div>
        {canCreate && (
          <button onClick={() => setAdding(!adding)} className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded">
            {adding ? 'Tutup' : '+ Mulai Inspeksi'}
          </button>
        )}
      </div>

      {error && <div className="text-sm text-red-600 bg-red-50 dark:bg-red-900/20 px-3 py-2 rounded">{error}</div>}

      {adding && canCreate && (
        <div className="bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700 p-4">
          <h3 className="font-medium mb-3">Inspeksi Baru</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <label className="block">
              <span className="text-xs text-gray-600 dark:text-gray-400 block mb-1">PO yang dikirim *</span>
              <select value={newPoId} onChange={e => setNewPoId(e.target.value)} className={inp}>
                <option value="">— pilih PO —</option>
                {pos.map(p => <option key={p.id} value={p.id}>PO-{p.id} · {p.expected_delivery_date || '—'} · Rp{(p.total_amount_idr || 0).toLocaleString('id-ID')}</option>)}
              </select>
            </label>
            <label className="block">
              <span className="text-xs text-gray-600 dark:text-gray-400 block mb-1">Catatan</span>
              <input value={newNotes} onChange={e => setNewNotes(e.target.value)} className={inp} placeholder="Truk dateng 04:00" />
            </label>
          </div>
          <button onClick={create} className="mt-3 px-3 py-1.5 bg-green-600 hover:bg-green-700 text-white text-sm rounded">
            Mulai
          </button>
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        {['inspecting', 'pending', 'accepted', 'partial', 'rejected', 'all'].map(s => (
          <button key={s} onClick={() => setFilter(s)}
            className={`px-3 py-1 text-xs rounded ${filter === s
              ? 'bg-blue-600 text-white' : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300'}`}>
            {s === 'all' ? 'Semua' : s}
          </button>
        ))}
      </div>

      {loading ? <div className="text-sm text-gray-500">Memuat...</div> : (
        <div className="bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700 overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 dark:bg-gray-700/50 text-xs uppercase">
              <tr>
                <th className="px-3 py-2 text-left">ID</th>
                <th className="px-3 py-2 text-left">Status</th>
                <th className="px-3 py-2 text-left">PO</th>
                <th className="px-3 py-2 text-left">Supplier</th>
                <th className="px-3 py-2 text-left">Dibuat</th>
                <th className="px-3 py-2 text-right">Aksi</th>
              </tr>
            </thead>
            <tbody>
              {list.length === 0 ? (
                <tr><td colSpan={6} className="text-center py-6 text-gray-400">Tidak ada inspeksi.</td></tr>
              ) : list.map(i => (
                <tr key={i.id} className="border-t border-gray-100 dark:border-gray-700">
                  <td className="px-3 py-2 font-mono text-xs">INS-{i.id}</td>
                  <td className="px-3 py-2"><span className={`text-xs px-2 py-0.5 rounded ${STATUS_PILL[i.status] || ''}`}>{i.status}</span></td>
                  <td className="px-3 py-2 text-xs">{i.po_id ? `PO-${i.po_id}` : '—'}</td>
                  <td className="px-3 py-2 text-xs">{i.supplier_id ? `#${i.supplier_id}` : '—'}</td>
                  <td className="px-3 py-2 text-xs">{i.created_at?.slice(0, 19).replace('T', ' ')}</td>
                  <td className="px-3 py-2 text-right">
                    <button onClick={() => open(i)} className="text-xs text-blue-600 hover:underline">Buka</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {viewing && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setViewing(null)}>
          <div className="bg-white dark:bg-gray-800 rounded p-6 max-w-4xl w-full max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-lg font-bold">INS-{viewing.id} · {viewing.po_id ? `PO-${viewing.po_id}` : 'manual'}</h3>
              <span className={`text-xs px-2 py-0.5 rounded ${STATUS_PILL[viewing.status] || ''}`}>{viewing.status}</span>
            </div>

            {/* Sign-offs */}
            <div className="mb-4">
              <h4 className="text-sm font-semibold mb-2">3-Sign-Off</h4>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                {['quality', 'quantity', 'physical'].map(role => {
                  const so = (viewing.signoffs || []).find(s => s.role_required === role)
                  const myPerm = hasPermission(ROLE_PERM[role])
                  return (
                    <div key={role} className="border border-gray-200 dark:border-gray-700 rounded p-2">
                      <div className="text-xs font-medium text-gray-500 dark:text-gray-400">{ROLE_LABEL[role]}</div>
                      {so ? (
                        <div className="mt-1">
                          <span className={`text-xs px-2 py-0.5 rounded ${so.status === 'approved' ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400' : 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400'}`}>
                            {so.status}{so.is_offline_sign ? ' (offline)' : ''}
                          </span>
                          {so.notes && <div className="text-xs text-gray-500 mt-1">"{so.notes}"</div>}
                        </div>
                      ) : myPerm && ['inspecting', 'pending'].includes(viewing.status) ? (
                        <div className="mt-2 flex gap-1">
                          <button disabled={busyKey === `signoff-${role}`} onClick={() => doSignoff(role, 'approved')}
                            className="px-2 py-0.5 text-xs bg-green-600 hover:bg-green-700 text-white rounded disabled:opacity-50">Approve</button>
                          <button disabled={busyKey === `signoff-${role}`} onClick={() => doSignoff(role, 'rejected')}
                            className="px-2 py-0.5 text-xs bg-red-600 hover:bg-red-700 text-white rounded disabled:opacity-50">Reject</button>
                        </div>
                      ) : <div className="mt-1 text-xs text-gray-400 italic">menunggu...</div>}
                    </div>
                  )
                })}
              </div>
            </div>

            {/* Lines */}
            <div className="mb-4">
              <h4 className="text-sm font-semibold mb-2">Lines</h4>
              <table className="w-full text-sm">
                <thead className="bg-gray-50 dark:bg-gray-700/50 text-xs uppercase">
                  <tr>
                    <th className="px-2 py-1.5 text-left">Bahan</th>
                    <th className="px-2 py-1.5 text-right">Expected (g)</th>
                    <th className="px-2 py-1.5 text-right">Aktual (g)</th>
                    <th className="px-2 py-1.5 text-right">Box</th>
                    <th className="px-2 py-1.5 text-left">Storage</th>
                    <th className="px-2 py-1.5 text-left">Status</th>
                    <th className="px-2 py-1.5 text-right">Aksi</th>
                  </tr>
                </thead>
                <tbody>
                  {(viewing.lines || []).map(l => (
                    <tr key={l.id} className="border-t border-gray-100 dark:border-gray-700">
                      <td className="px-2 py-1.5">{l.item_name}</td>
                      <td className="px-2 py-1.5 text-right tabular-nums">{(l.expected_weight_grams || 0).toLocaleString('id-ID')}</td>
                      <td className="px-2 py-1.5 text-right tabular-nums">{l.actual_weight_grams ? l.actual_weight_grams.toLocaleString('id-ID') : '—'}</td>
                      <td className="px-2 py-1.5 text-right">{l.container_count || '—'}</td>
                      <td className="px-2 py-1.5 text-xs">{l.storage_routing || '—'}</td>
                      <td className="px-2 py-1.5"><span className={`text-xs px-2 py-0.5 rounded ${STATUS_PILL[l.status] || ''}`}>{l.status}</span></td>
                      <td className="px-2 py-1.5 text-right space-x-2 whitespace-nowrap">
                        {l.status === 'pending' && (
                          <>
                            {canSplit && <button disabled={busyKey === `accept-${l.id}`} onClick={() => acceptLine(l)} className="text-xs text-green-600 hover:underline disabled:opacity-50">Accept</button>}
                            {canReject && <button disabled={busyKey === `reject-${l.id}`} onClick={() => rejectLine(l)} className="text-xs text-red-600 hover:underline disabled:opacity-50">Reject</button>}
                          </>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="flex gap-2">
              {canFinalize && ['inspecting', 'pending'].includes(viewing.status) && (
                <button disabled={busyKey === 'finalize'} onClick={onFinalize} className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded disabled:opacity-50">
                  Finalize
                </button>
              )}
              <button onClick={() => setViewing(null)} className="px-3 py-1.5 bg-gray-200 dark:bg-gray-700 text-sm rounded">Tutup</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

const inp = "w-full px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
