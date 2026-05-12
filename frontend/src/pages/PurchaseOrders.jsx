import { useEffect, useState } from 'react'
import { listPurchaseOrders, createPurchaseOrder, updatePurchaseOrder, deletePurchaseOrder, getPurchaseOrder } from '../api/inspections'
import { listSuppliers } from '../api/suppliers'
import { useAuth } from '../hooks/useAuth'

const STATUS_PILL = {
  draft:     'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300',
  sent:      'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400',
  partial:   'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400',
  received:  'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400',
  closed:    'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400',
  cancelled: 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400',
}

export default function PurchaseOrders() {
  const { hasPermission } = useAuth()
  const canEdit = hasPermission('po.create')
  const [pos, setPos] = useState([])
  const [suppliers, setSuppliers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [filter, setFilter] = useState('')
  const [adding, setAdding] = useState(false)
  const [viewingId, setViewingId] = useState(null)
  const [viewingPO, setViewingPO] = useState(null)

  const empty = {
    supplier_id: '', expected_delivery_date: '', notes: '',
    lines: [{ item_name: '', total_weight_grams: 0, unit: 'kg', expected_containers: 1, unit_price_idr: 0 }],
  }
  const [form, setForm] = useState(empty)

  const refresh = async () => {
    setLoading(true); setError('')
    try {
      const r = await listPurchaseOrders(filter ? { status: filter } : {})
      setPos(r.data.purchase_orders || [])
    } catch (e) { setError(e.response?.data?.detail || e.message) }
    finally { setLoading(false) }
  }
  useEffect(() => { refresh() /* eslint-disable-next-line */ }, [filter])
  useEffect(() => {
    listSuppliers().then(r => setSuppliers(r.data.suppliers || [])).catch(() => {})
  }, [])

  const addLine = () => setForm({ ...form, lines: [...form.lines, { item_name: '', total_weight_grams: 0, unit: 'kg', expected_containers: 1, unit_price_idr: 0 }] })
  const removeLine = (i) => setForm({ ...form, lines: form.lines.filter((_, idx) => idx !== i) })
  const updateLine = (i, field, val) => setForm({
    ...form,
    lines: form.lines.map((l, idx) => idx === i ? { ...l, [field]: val } : l),
  })

  const totalEstimate = form.lines.reduce((sum, l) => {
    const kg = (Number(l.total_weight_grams) || 0) / 1000
    return sum + (Number(l.unit_price_idr) || 0) * kg
  }, 0)

  const submit = async () => {
    if (!form.supplier_id) { setError('Supplier wajib dipilih.'); return }
    if (form.lines.length === 0) { setError('Minimal 1 line.'); return }
    setError('')
    try {
      const payload = {
        supplier_id: Number(form.supplier_id),
        expected_delivery_date: form.expected_delivery_date || null,
        notes: form.notes || null,
        lines: form.lines.map(l => ({
          item_name: l.item_name,
          total_weight_grams: Number(l.total_weight_grams) || 0,
          unit: l.unit || 'kg',
          expected_containers: Number(l.expected_containers) || 1,
          unit_price_idr: Number(l.unit_price_idr) || 0,
        })),
      }
      await createPurchaseOrder(payload)
      setAdding(false); setForm(empty)
      refresh()
    } catch (e) { setError(e.response?.data?.detail || e.message) }
  }

  const sendPO = async (id) => {
    if (!confirm('Tandai PO sebagai sent?')) return
    try { await updatePurchaseOrder(id, { status: 'sent' }); refresh() }
    catch (e) { setError(e.response?.data?.detail || e.message) }
  }

  const removePO = async (id) => {
    if (!confirm('Hapus PO?')) return
    try { await deletePurchaseOrder(id); refresh() }
    catch (e) { setError(e.response?.data?.detail || e.message) }
  }

  const viewPO = async (id) => {
    setViewingId(id); setViewingPO(null)
    try { const r = await getPurchaseOrder(id); setViewingPO(r.data) }
    catch (e) { setError(e.response?.data?.detail || e.message) }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-gray-800 dark:text-gray-100">Purchase Orders</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400">Akuntan generate PO dari forecast menu approved.</p>
        </div>
        {canEdit && (
          <button onClick={() => setAdding(!adding)} className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded">
            {adding ? 'Tutup' : '+ PO Baru'}
          </button>
        )}
      </div>

      {error && <div className="text-sm text-red-600 bg-red-50 dark:bg-red-900/20 px-3 py-2 rounded">{error}</div>}

      <div className="flex flex-wrap gap-2">
        {['', 'draft', 'sent', 'partial', 'received', 'closed', 'cancelled'].map(s => (
          <button key={s} onClick={() => setFilter(s)}
            className={`px-3 py-1 text-xs rounded ${filter === s
              ? 'bg-blue-600 text-white' : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300'}`}>
            {s || 'Semua'}
          </button>
        ))}
      </div>

      {adding && canEdit && (
        <div className="bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700 p-4 space-y-3">
          <h3 className="font-medium">PO Baru</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <label className="block">
              <span className="text-xs text-gray-600 dark:text-gray-400 block mb-1">Supplier *</span>
              <select value={form.supplier_id} onChange={e => setForm({ ...form, supplier_id: e.target.value })} className={inp}>
                <option value="">— pilih supplier —</option>
                {suppliers.map(s => <option key={s.id} value={s.id}>{s.name} ({s.kategori || '—'})</option>)}
              </select>
            </label>
            <label className="block">
              <span className="text-xs text-gray-600 dark:text-gray-400 block mb-1">Tanggal Pengiriman</span>
              <input type="date" value={form.expected_delivery_date} onChange={e => setForm({ ...form, expected_delivery_date: e.target.value })} className={inp} />
            </label>
            <label className="block md:col-span-2">
              <span className="text-xs text-gray-600 dark:text-gray-400 block mb-1">Catatan</span>
              <input value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} className={inp} />
            </label>
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-sm font-medium">Line Items</h4>
              <button onClick={addLine} className="text-xs text-blue-600 hover:underline">+ Tambah Line</button>
            </div>
            <div className="space-y-2">
              {form.lines.map((l, i) => (
                <div key={i} className="grid grid-cols-12 gap-2 items-end bg-gray-50 dark:bg-gray-900/50 p-2 rounded">
                  <label className="col-span-3 block">
                    <span className="text-xs text-gray-500 block mb-1">Bahan</span>
                    <input value={l.item_name} onChange={e => updateLine(i, 'item_name', e.target.value)} className={inp} placeholder="Ayam Fillet" />
                  </label>
                  <label className="col-span-2 block">
                    <span className="text-xs text-gray-500 block mb-1">Berat (g)</span>
                    <input type="number" min="0" value={l.total_weight_grams} onChange={e => updateLine(i, 'total_weight_grams', e.target.value)} className={inp} />
                  </label>
                  <label className="col-span-1 block">
                    <span className="text-xs text-gray-500 block mb-1">Unit</span>
                    <input value={l.unit} onChange={e => updateLine(i, 'unit', e.target.value)} className={inp} />
                  </label>
                  <label className="col-span-2 block">
                    <span className="text-xs text-gray-500 block mb-1">Expected #Box</span>
                    <input type="number" min="1" value={l.expected_containers} onChange={e => updateLine(i, 'expected_containers', e.target.value)} className={inp} />
                  </label>
                  <label className="col-span-3 block">
                    <span className="text-xs text-gray-500 block mb-1">Harga / kg (Rp)</span>
                    <input type="number" min="0" value={l.unit_price_idr} onChange={e => updateLine(i, 'unit_price_idr', e.target.value)} className={inp} />
                  </label>
                  <button onClick={() => removeLine(i)} className="col-span-1 text-red-500 text-sm hover:underline">×</button>
                </div>
              ))}
            </div>
            <div className="text-right text-sm font-medium mt-2">
              Total estimasi: <span className="text-blue-600">Rp{Math.round(totalEstimate).toLocaleString('id-ID')}</span>
            </div>
          </div>

          <button onClick={submit} className="px-3 py-1.5 bg-green-600 hover:bg-green-700 text-white text-sm rounded">
            Simpan Draft
          </button>
        </div>
      )}

      {loading ? <div className="text-sm text-gray-500">Memuat...</div> : (
        <div className="bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700 overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 dark:bg-gray-700/50 text-xs uppercase">
              <tr>
                <th className="px-3 py-2 text-left">ID</th>
                <th className="px-3 py-2 text-left">Status</th>
                <th className="px-3 py-2 text-left">Supplier</th>
                <th className="px-3 py-2 text-left">Tgl Pengiriman</th>
                <th className="px-3 py-2 text-right">Total</th>
                <th className="px-3 py-2 text-right">Aksi</th>
              </tr>
            </thead>
            <tbody>
              {pos.length === 0 ? (
                <tr><td colSpan={6} className="text-center py-6 text-gray-400">Belum ada PO.</td></tr>
              ) : pos.map(p => {
                const sup = suppliers.find(s => s.id === p.supplier_id)
                return (
                  <tr key={p.id} className="border-t border-gray-100 dark:border-gray-700">
                    <td className="px-3 py-2 font-mono text-xs">PO-{p.id}</td>
                    <td className="px-3 py-2">
                      <span className={`text-xs px-2 py-0.5 rounded ${STATUS_PILL[p.status] || ''}`}>{p.status}</span>
                    </td>
                    <td className="px-3 py-2">{sup?.name || `#${p.supplier_id}`}</td>
                    <td className="px-3 py-2 text-xs">{p.expected_delivery_date || '—'}</td>
                    <td className="px-3 py-2 text-right tabular-nums">Rp{(p.total_amount_idr || 0).toLocaleString('id-ID')}</td>
                    <td className="px-3 py-2 text-right space-x-2 whitespace-nowrap">
                      <button onClick={() => viewPO(p.id)} className="text-xs text-blue-600 hover:underline">Detail</button>
                      {canEdit && p.status === 'draft' && <button onClick={() => sendPO(p.id)} className="text-xs text-green-600 hover:underline">Kirim</button>}
                      {canEdit && p.status === 'draft' && <button onClick={() => removePO(p.id)} className="text-xs text-red-600 hover:underline">Hapus</button>}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {viewingId && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setViewingId(null)}>
          <div className="bg-white dark:bg-gray-800 rounded p-6 max-w-3xl w-full max-h-[80vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <h3 className="text-lg font-bold mb-3">PO-{viewingId}</h3>
            {!viewingPO ? <div className="text-sm text-gray-500">Memuat...</div> : (
              <div>
                <div className="text-sm text-gray-600 dark:text-gray-400 mb-3">
                  Status: <span className={`text-xs px-2 py-0.5 rounded ${STATUS_PILL[viewingPO.status] || ''}`}>{viewingPO.status}</span>
                  {' · '}Total: <span className="font-semibold">Rp{(viewingPO.total_amount_idr || 0).toLocaleString('id-ID')}</span>
                </div>
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 dark:bg-gray-700/50 text-xs uppercase">
                    <tr>
                      <th className="px-2 py-1.5 text-left">Bahan</th>
                      <th className="px-2 py-1.5 text-right">Berat (g)</th>
                      <th className="px-2 py-1.5 text-right">Box</th>
                      <th className="px-2 py-1.5 text-right">Harga/kg</th>
                      <th className="px-2 py-1.5 text-right">Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(viewingPO.lines || []).map(l => (
                      <tr key={l.id} className="border-t border-gray-100 dark:border-gray-700">
                        <td className="px-2 py-1.5">{l.item_name}</td>
                        <td className="px-2 py-1.5 text-right tabular-nums">{l.total_weight_grams.toLocaleString('id-ID')}</td>
                        <td className="px-2 py-1.5 text-right">{l.expected_containers}</td>
                        <td className="px-2 py-1.5 text-right tabular-nums">Rp{l.unit_price_idr.toLocaleString('id-ID')}</td>
                        <td className="px-2 py-1.5 text-right tabular-nums">Rp{l.line_total_idr.toLocaleString('id-ID')}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <button onClick={() => setViewingId(null)} className="mt-4 px-3 py-1.5 bg-gray-200 dark:bg-gray-700 text-sm rounded">Tutup</button>
          </div>
        </div>
      )}
    </div>
  )
}

const inp = "w-full px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
