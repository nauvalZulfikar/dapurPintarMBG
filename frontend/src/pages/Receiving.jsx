import { useState, useRef, useEffect, useCallback } from 'react'
import { createItem, getItems, updateItem, deleteItem } from '../api/items'
import DataTable from '../components/DataTable'
import Pagination from '../components/Pagination'
import { formatDateTime, todayISO } from '../utils/format'

const CHECKLIST_ITEMS = [
  { key: 'packaging_ok', label: 'Packaging OK' },
  { key: 'expiry_ok', label: 'Expiry OK' },
  { key: 'temperature_ok', label: 'Temperature OK' },
  { key: 'cleanliness_ok', label: 'Cleanliness OK' },
]

const INPUT = 'w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-accent'
const CARD = 'bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700'

export default function Receiving() {
  const [name, setName] = useState('')
  const [weight, setWeight] = useState('')
  const [unit, setUnit] = useState('g')
  const [checklist, setChecklist] = useState({})
  const [notes, setNotes] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const nameRef = useRef(null)

  // Table state
  const [items, setItems] = useState([])
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [tableLoading, setTableLoading] = useState(false)
  const [search, setSearch] = useState('')
  const [date, setDate] = useState(todayISO())

  // Edit modal state
  const [editItem, setEditItem] = useState(null)
  const [editName, setEditName] = useState('')
  const [editWeight, setEditWeight] = useState('')
  const [editUnit, setEditUnit] = useState('g')
  const [editLoading, setEditLoading] = useState(false)

  // Delete confirm state
  const [deleteId, setDeleteId] = useState(null)
  const [deleteLoading, setDeleteLoading] = useState(false)

  const loadItems = useCallback(() => {
    setTableLoading(true)
    getItems({ date, page, search: search || undefined })
      .then((r) => {
        setItems(r.data.items)
        setTotalPages(r.data.total_pages)
      })
      .catch(() => {})
      .finally(() => setTableLoading(false))
  }, [date, page, search])

  useEffect(() => { loadItems() }, [loadItems])

  const playSound = (ok) => {
    try {
      new Audio(ok ? '/SUCCESS.mp3' : '/FAILED.mp3').play()
    } catch {}
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!name.trim() || !weight || Number(weight) <= 0) {
      setResult({ ok: false, message: 'Name and weight are required' })
      playSound(false)
      return
    }

    const payload = {
      name: name.trim(),
      weight: Number(weight),
      unit,
      checklist,
      notes: notes.trim() || undefined,
    }

    setResult({ ok: true, message: 'Submitted' })
    playSound(true)
    setName('')
    setWeight('')
    setChecklist({})
    setNotes('')
    nameRef.current?.focus()

    createItem(payload)
      .then(() => { loadItems() })
      .catch((err) => {
        setResult({ ok: false, message: err.response?.data?.detail || 'Failed to create item' })
        playSound(false)
      })
  }

  // Edit handlers
  const openEdit = (item) => {
    setEditItem(item)
    setEditName(item.name)
    setEditWeight(item.unit === 'kg' ? item.weight_grams / 1000 : item.weight_grams)
    setEditUnit(item.unit || 'g')
  }

  const handleEdit = () => {
    if (!editName.trim() || !editWeight || Number(editWeight) <= 0) return
    setEditLoading(true)
    updateItem(editItem.id, { name: editName.trim(), weight: Number(editWeight), unit: editUnit })
      .then(() => {
        setEditItem(null)
        loadItems()
      })
      .catch((err) => {
        setResult({ ok: false, message: err.response?.data?.detail || 'Failed to update' })
      })
      .finally(() => setEditLoading(false))
  }

  // Delete handlers
  const handleDelete = () => {
    setDeleteLoading(true)
    deleteItem(deleteId)
      .then(() => {
        setDeleteId(null)
        loadItems()
      })
      .catch((err) => {
        setResult({ ok: false, message: err.response?.data?.detail || 'Failed to delete' })
      })
      .finally(() => setDeleteLoading(false))
  }

  const columns = [
    { key: 'id', label: 'ID' },
    { key: 'name', label: 'Nama' },
    { key: 'weight_grams', label: 'Berat (g)' },
    { key: 'unit', label: 'Unit' },
    { key: 'created_at_receiving', label: 'Waktu', render: (v) => formatDateTime(v) },
    {
      key: '_actions',
      label: '',
      render: (_, row) => (
        <div className="flex gap-2">
          <button
            onClick={() => openEdit(row)}
            className="px-2 py-1 text-xs bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400 rounded hover:bg-yellow-200 dark:hover:bg-yellow-900/50"
          >
            Edit
          </button>
          <button
            onClick={() => setDeleteId(row.id)}
            className="px-2 py-1 text-xs bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 rounded hover:bg-red-200 dark:hover:bg-red-900/50"
          >
            Hapus
          </button>
        </div>
      ),
    },
  ]

  return (
    <div className="space-y-6">
      <div className="max-w-lg">
        <h2 className="text-xl font-bold text-gray-800 dark:text-gray-100 mb-4">Receiving</h2>

        {result && (
          <div className={`mb-4 p-3 rounded text-sm ${
            result.ok
              ? 'bg-green-50 dark:bg-green-900/30 text-green-700 dark:text-green-400 border border-green-200 dark:border-green-800'
              : 'bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-400 border border-red-200 dark:border-red-800'
          }`}>
            {result.message}
          </div>
        )}

        <form onSubmit={handleSubmit} className={`${CARD} p-4 space-y-4`}>
          <div>
            <label className="block text-sm text-gray-600 dark:text-gray-300 mb-1">Nama Bahan</label>
            <input
              ref={nameRef}
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className={INPUT}
              autoFocus
              required
            />
          </div>

          <div className="flex gap-3">
            <div className="flex-1">
              <label className="block text-sm text-gray-600 dark:text-gray-300 mb-1">Berat</label>
              <input
                type="number"
                value={weight}
                onChange={(e) => setWeight(e.target.value)}
                min="0"
                step="any"
                className={INPUT}
                required
              />
            </div>
            <div className="w-24">
              <label className="block text-sm text-gray-600 dark:text-gray-300 mb-1">Unit</label>
              <select
                value={unit}
                onChange={(e) => setUnit(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-100"
              >
                <option value="g">g</option>
                <option value="kg">kg</option>
                <option value="pcs">pcs</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-sm text-gray-600 dark:text-gray-300 mb-2">QC Checklist</label>
            <div className="space-y-1">
              {CHECKLIST_ITEMS.map((item) => (
                <label key={item.key} className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
                  <input
                    type="checkbox"
                    checked={!!checklist[item.key]}
                    onChange={(e) => setChecklist({ ...checklist, [item.key]: e.target.checked })}
                    className="rounded"
                  />
                  {item.label}
                </label>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm text-gray-600 dark:text-gray-300 mb-1">Catatan</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              className={INPUT}
            />
          </div>

          <button
            type="submit"
            className="w-full py-2 bg-brand text-white rounded text-sm font-medium hover:bg-brand-dark"
          >
            Submit
          </button>
        </form>
      </div>

      {/* Items Table */}
      <div className={CARD}>
        <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-3">Daftar Bahan Diterima</h3>
          <div className="flex flex-wrap gap-3">
            <input
              type="date"
              value={date}
              onChange={(e) => { setDate(e.target.value); setPage(1) }}
              className="px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-100"
            />
            <input
              type="text"
              placeholder="Cari nama..."
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1) }}
              className="px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded text-sm w-48 bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500"
            />
          </div>
        </div>
        <div className="p-4">
          <DataTable columns={columns} data={items} loading={tableLoading} />
          <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
        </div>
      </div>

      {/* Edit Modal */}
      {editItem && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setEditItem(null)}>
          <div className={`${CARD} p-6 w-full max-w-md mx-4`} onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-bold text-gray-800 dark:text-gray-100 mb-4">Edit Item</h3>
            <div className="space-y-3">
              <div>
                <label className="block text-sm text-gray-600 dark:text-gray-300 mb-1">Nama</label>
                <input type="text" value={editName} onChange={(e) => setEditName(e.target.value)} className={INPUT} />
              </div>
              <div className="flex gap-3">
                <div className="flex-1">
                  <label className="block text-sm text-gray-600 dark:text-gray-300 mb-1">Berat</label>
                  <input type="number" value={editWeight} onChange={(e) => setEditWeight(e.target.value)} min="0" step="any" className={INPUT} />
                </div>
                <div className="w-24">
                  <label className="block text-sm text-gray-600 dark:text-gray-300 mb-1">Unit</label>
                  <select value={editUnit} onChange={(e) => setEditUnit(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-100">
                    <option value="g">g</option>
                    <option value="kg">kg</option>
                    <option value="pcs">pcs</option>
                  </select>
                </div>
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-6">
              <button onClick={() => setEditItem(null)}
                className="px-4 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700">
                Batal
              </button>
              <button onClick={handleEdit} disabled={editLoading}
                className="px-4 py-2 text-sm bg-brand text-white rounded hover:bg-brand-dark disabled:opacity-50">
                {editLoading ? 'Saving...' : 'Simpan'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteId && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setDeleteId(null)}>
          <div className={`${CARD} p-6 w-full max-w-sm mx-4`} onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-bold text-gray-800 dark:text-gray-100 mb-2">Hapus Item?</h3>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-6">
              Item <span className="font-mono font-medium">{deleteId}</span> akan dihapus permanen.
            </p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setDeleteId(null)}
                className="px-4 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700">
                Batal
              </button>
              <button onClick={handleDelete} disabled={deleteLoading}
                className="px-4 py-2 text-sm bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50">
                {deleteLoading ? 'Deleting...' : 'Hapus'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
