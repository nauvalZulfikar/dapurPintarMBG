import { useEffect, useState } from 'react'
import { listSuppliers, createSupplier, updateSupplier, deleteSupplier } from '../api/suppliers'
import { useAuth } from '../hooks/useAuth'

const KATEGORI_OPTIONS = ['sayur', 'daging', 'ayam', 'ikan', 'beras', 'telur', 'tahu_tempe', 'buah', 'bumbu', 'lainnya']

export default function AdminSuppliers() {
  const { hasPermission } = useAuth()
  const canEdit = hasPermission('supplier.manage')
  const [suppliers, setSuppliers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [includeInactive, setIncludeInactive] = useState(false)
  const [adding, setAdding] = useState(false)
  const [editingId, setEditingId] = useState(null)

  const empty = {
    name: '', contact: '', npwp: '', rekening: '', bank_name: '',
    kategori: 'sayur', rating: 5, notes: '',
  }
  const [form, setForm] = useState(empty)

  const refresh = async () => {
    setLoading(true); setError('')
    try {
      const r = await listSuppliers(includeInactive)
      setSuppliers(r.data.suppliers || [])
    } catch (e) {
      setError(e.response?.data?.detail || e.message)
    } finally {
      setLoading(false)
    }
  }
  useEffect(() => { refresh() /* eslint-disable-next-line */ }, [includeInactive])

  const startAdd = () => { setForm(empty); setAdding(true); setEditingId(null) }
  const startEdit = (s) => {
    setForm({
      name: s.name || '', contact: s.contact || '', npwp: s.npwp || '',
      rekening: s.rekening || '', bank_name: s.bank_name || '',
      kategori: s.kategori || 'sayur', rating: s.rating || 5, notes: s.notes || '',
    })
    setEditingId(s.id); setAdding(false)
  }

  const submit = async () => {
    setError('')
    try {
      const payload = { ...form, rating: Number(form.rating) || 5 }
      if (editingId) {
        await updateSupplier(editingId, payload)
      } else {
        await createSupplier(payload)
      }
      setAdding(false); setEditingId(null)
      refresh()
    } catch (e) {
      setError(e.response?.data?.detail || e.message)
    }
  }

  const onDelete = async (s) => {
    if (!confirm(`Nonaktifkan supplier "${s.name}"?`)) return
    try {
      await deleteSupplier(s.id)
      refresh()
    } catch (e) {
      setError(e.response?.data?.detail || e.message)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-gray-800 dark:text-gray-100">Master Supplier</h2>
        <div className="flex items-center gap-3">
          <label className="text-sm text-gray-600 dark:text-gray-300 flex items-center gap-2">
            <input type="checkbox" checked={includeInactive} onChange={e => setIncludeInactive(e.target.checked)} />
            Tampilkan non-aktif
          </label>
          {canEdit && (
            <button onClick={startAdd} className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded">
              + Tambah Supplier
            </button>
          )}
        </div>
      </div>

      {error && <div className="text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 px-3 py-2 rounded">{error}</div>}

      {(adding || editingId) && canEdit && (
        <div className="bg-white dark:bg-gray-800 p-4 rounded border border-gray-200 dark:border-gray-700">
          <h3 className="font-medium mb-3">{editingId ? 'Edit Supplier' : 'Supplier Baru'}</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <Field label="Nama Supplier *">
              <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} className={inp} />
            </Field>
            <Field label="Kontak (HP/WA)">
              <input value={form.contact} onChange={e => setForm({ ...form, contact: e.target.value })} className={inp} />
            </Field>
            <Field label="Kategori">
              <select value={form.kategori} onChange={e => setForm({ ...form, kategori: e.target.value })} className={inp}>
                {KATEGORI_OPTIONS.map(k => <option key={k} value={k}>{k}</option>)}
              </select>
            </Field>
            <Field label="Rating (1-5)">
              <input type="number" min="1" max="5" value={form.rating} onChange={e => setForm({ ...form, rating: e.target.value })} className={inp} />
            </Field>
            <Field label="NPWP">
              <input value={form.npwp} onChange={e => setForm({ ...form, npwp: e.target.value })} className={inp} />
            </Field>
            <Field label="Bank">
              <input value={form.bank_name} onChange={e => setForm({ ...form, bank_name: e.target.value })} className={inp} />
            </Field>
            <Field label="Rekening" className="md:col-span-2">
              <input value={form.rekening} onChange={e => setForm({ ...form, rekening: e.target.value })} className={inp} />
            </Field>
            <Field label="Catatan" className="md:col-span-2">
              <textarea rows={2} value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} className={inp} />
            </Field>
          </div>
          <div className="mt-3 flex gap-2">
            <button onClick={submit} className="px-3 py-1.5 bg-green-600 hover:bg-green-700 text-white text-sm rounded">
              {editingId ? 'Simpan' : 'Tambah'}
            </button>
            <button onClick={() => { setAdding(false); setEditingId(null) }} className="px-3 py-1.5 bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 text-sm rounded">
              Batal
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="text-sm text-gray-500">Memuat...</div>
      ) : (
        <div className="bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700 overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 dark:bg-gray-700/50 text-gray-600 dark:text-gray-300">
              <tr>
                <th className="px-3 py-2 text-left">Nama</th>
                <th className="px-3 py-2 text-left">Kategori</th>
                <th className="px-3 py-2 text-left">Kontak</th>
                <th className="px-3 py-2 text-left">NPWP</th>
                <th className="px-3 py-2 text-center">Rating</th>
                <th className="px-3 py-2 text-left">Status</th>
                {canEdit && <th className="px-3 py-2 text-right">Aksi</th>}
              </tr>
            </thead>
            <tbody>
              {suppliers.length === 0 ? (
                <tr><td colSpan={canEdit ? 7 : 6} className="text-center py-6 text-gray-400">Belum ada supplier</td></tr>
              ) : suppliers.map(s => (
                <tr key={s.id} className="border-t border-gray-100 dark:border-gray-700">
                  <td className="px-3 py-2 font-medium">{s.name}</td>
                  <td className="px-3 py-2">{s.kategori || '—'}</td>
                  <td className="px-3 py-2">{s.contact || '—'}</td>
                  <td className="px-3 py-2 text-xs font-mono">{s.npwp || '—'}</td>
                  <td className="px-3 py-2 text-center">{'⭐'.repeat(Math.max(0, Math.min(5, s.rating || 0)))}</td>
                  <td className="px-3 py-2">
                    {s.is_active
                      ? <span className="text-xs px-2 py-0.5 rounded bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400">Aktif</span>
                      : <span className="text-xs px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-700 text-gray-500">Non-aktif</span>}
                  </td>
                  {canEdit && (
                    <td className="px-3 py-2 text-right space-x-2">
                      <button onClick={() => startEdit(s)} className="text-xs text-blue-600 hover:underline">Edit</button>
                      {s.is_active && <button onClick={() => onDelete(s)} className="text-xs text-red-600 hover:underline">Nonaktifkan</button>}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

const inp = "w-full px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500"

function Field({ label, children, className = '' }) {
  return (
    <label className={`block ${className}`}>
      <span className="text-xs text-gray-600 dark:text-gray-400 block mb-1">{label}</span>
      {children}
    </label>
  )
}
