import { useState, useRef, useEffect, useCallback } from 'react'
import { createItem, getItems, updateItem, deleteItem, testPrintItem, createDefect, listDefects, deleteDefect, defectPhotoUrl } from '../api/items'
import DataTable from '../components/DataTable'
import Pagination from '../components/Pagination'
import BhnPicker from '../components/BhnPicker'
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

  // Test-print state
  const [testPrinting, setTestPrinting] = useState(false)

  // Mode toggle: 'receiving' or 'defect'
  const [mode, setMode] = useState('receiving')

  // Defect-only fields
  const [defectReason, setDefectReason] = useState('')
  const [photoFile, setPhotoFile] = useState(null)
  const [photoPreview, setPhotoPreview] = useState(null)

  // Defect sub-mode: 'linked' = parsial dari BHN existing (skenario C),
  // 'standalone' = reject sebelum cetak (skenario A)
  const [defectSubmode, setDefectSubmode] = useState('linked')
  const [defectItemId, setDefectItemId] = useState('')
  const [defectSourceItem, setDefectSourceItem] = useState(null)
  const [allowOldBhn, setAllowOldBhn] = useState(false)

  // Defect table state
  const [defects, setDefects] = useState([])
  const [defectTotal, setDefectTotal] = useState(0)
  const [defectPage, setDefectPage] = useState(1)
  const [defectTotalPages, setDefectTotalPages] = useState(1)
  const [defectLoading, setDefectLoading] = useState(false)
  const [defectDeleteId, setDefectDeleteId] = useState(null)
  const [defectDeleteLoading, setDefectDeleteLoading] = useState(false)
  const [photoView, setPhotoView] = useState(null)

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

  const loadDefects = useCallback(() => {
    setDefectLoading(true)
    listDefects({ date, page: defectPage, search: search || undefined })
      .then((r) => {
        setDefects(r.data.defects)
        setDefectTotal(r.data.total)
        setDefectTotalPages(r.data.total_pages)
      })
      .catch(() => {})
      .finally(() => setDefectLoading(false))
  }, [date, defectPage, search])

  useEffect(() => { loadDefects() }, [loadDefects])

  const onPickPhoto = (e) => {
    const f = e.target.files?.[0] || null
    setPhotoFile(f)
    if (photoPreview) URL.revokeObjectURL(photoPreview)
    setPhotoPreview(f ? URL.createObjectURL(f) : null)
  }

  const clearForm = () => {
    setName('')
    setWeight('')
    setChecklist({})
    setNotes('')
    setDefectReason('')
    setPhotoFile(null)
    if (photoPreview) URL.revokeObjectURL(photoPreview)
    setPhotoPreview(null)
    setDefectItemId('')
    setDefectSourceItem(null)
    nameRef.current?.focus()
  }

  // When user picks a BHN in defect-linked mode, auto-fill name + unit + cap weight
  const handlePickBhn = (item) => {
    setDefectSourceItem(item)
    if (item) {
      setName(item.name)
      setUnit(item.unit || 'g')
      setWeight('')   // user must enter the defected portion explicitly
    }
  }

  const playSound = (ok) => {
    try {
      new Audio(ok ? '/SUCCESS.mp3' : '/FAILED.mp3').play()
    } catch {}
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!name.trim() || !weight || Number(weight) <= 0) {
      setResult({ ok: false, message: 'Nama dan berat wajib diisi' })
      playSound(false)
      return
    }

    if (mode === 'defect') {
      if (!defectReason.trim()) {
        setResult({ ok: false, message: 'Alasan defect wajib diisi' })
        playSound(false)
        return
      }

      // Skenario C (linked): require BHN selection + validate cap client-side
      if (defectSubmode === 'linked') {
        if (!defectItemId || !defectSourceItem) {
          setResult({ ok: false, message: 'Pilih BHN sumber dulu (scan barcode atau pilih dari daftar)' })
          playSound(false)
          return
        }
        const wgGrams = unit === 'kg' ? Number(weight) * 1000 : Number(weight)
        if (wgGrams > defectSourceItem.available_grams) {
          setResult({ ok: false, message: `Berat melebihi sisa available (${defectSourceItem.available_grams}g). Maks ${defectSourceItem.available_grams}g.` })
          playSound(false)
          return
        }
      }

      const fd = new FormData()
      fd.append('name', name.trim())
      fd.append('weight', String(Number(weight)))
      fd.append('unit', unit)
      fd.append('defect_reason', defectReason.trim())
      if (Object.keys(checklist).length) fd.append('checklist', JSON.stringify(checklist))
      if (notes.trim()) fd.append('notes', notes.trim())
      if (photoFile) fd.append('photo', photoFile)
      if (defectSubmode === 'linked' && defectItemId) {
        fd.append('item_id', defectItemId)
        if (allowOldBhn) fd.append('allow_old_bhn', 'true')
      }

      setResult({ ok: true, message: 'Defect tercatat' })
      playSound(true)
      clearForm()

      createDefect(fd)
        .then(() => { loadDefects() })
        .catch((err) => {
          setResult({ ok: false, message: err.response?.data?.detail || 'Gagal mencatat defect' })
          playSound(false)
        })
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
    clearForm()

    createItem(payload)
      .then(() => { loadItems() })
      .catch((err) => {
        setResult({ ok: false, message: err.response?.data?.detail || 'Failed to create item' })
        playSound(false)
      })
  }

  const handleDefectDelete = () => {
    if (!defectDeleteId) return
    setDefectDeleteLoading(true)
    deleteDefect(defectDeleteId)
      .then(() => {
        setDefectDeleteId(null)
        loadDefects()
      })
      .catch((err) => {
        setResult({ ok: false, message: err.response?.data?.detail || 'Gagal hapus defect' })
      })
      .finally(() => setDefectDeleteLoading(false))
  }

  const handleTestPrint = () => {
    setTestPrinting(true)
    testPrintItem()
      .then((r) => {
        setResult({ ok: true, message: `Test print terkirim (${r.data.test_id}) — tidak masuk DB` })
        playSound(true)
      })
      .catch((err) => {
        setResult({ ok: false, message: err.response?.data?.detail || 'Test print gagal' })
        playSound(false)
      })
      .finally(() => setTestPrinting(false))
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
        <h2 className="text-xl font-bold text-gray-800 dark:text-gray-100 mb-3">Receiving</h2>

        <div className="inline-flex rounded-lg border border-gray-300 dark:border-gray-600 p-0.5 mb-4 bg-gray-50 dark:bg-gray-800">
          <button
            type="button"
            onClick={() => setMode('receiving')}
            className={`px-4 py-1.5 text-sm rounded ${
              mode === 'receiving'
                ? 'bg-brand text-white'
                : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
            }`}
          >
            Bahan Masuk
          </button>
          <button
            type="button"
            onClick={() => setMode('defect')}
            className={`px-4 py-1.5 text-sm rounded ${
              mode === 'defect'
                ? 'bg-red-600 text-white'
                : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
            }`}
          >
            Defect / Reject
          </button>
        </div>

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

          {mode === 'defect' && (
            <>
              <div className="flex flex-col gap-1.5 -mt-2">
                <label className="text-xs uppercase tracking-wider text-gray-500 dark:text-gray-400">Sumber Defect</label>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setDefectSubmode('linked')}
                    className={`flex-1 px-3 py-2.5 rounded text-sm border ${
                      defectSubmode === 'linked'
                        ? 'border-red-600 bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-300 font-medium'
                        : 'border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700'
                    }`}
                  >
                    Dari BHN existing
                  </button>
                  <button
                    type="button"
                    onClick={() => setDefectSubmode('standalone')}
                    className={`flex-1 px-3 py-2.5 rounded text-sm border ${
                      defectSubmode === 'standalone'
                        ? 'border-red-600 bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-300 font-medium'
                        : 'border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700'
                    }`}
                  >
                    Reject sebelum cetak
                  </button>
                </div>
              </div>

              {defectSubmode === 'linked' && (
                <BhnPicker
                  value={defectItemId}
                  onChange={setDefectItemId}
                  onPickedItem={handlePickBhn}
                  allowOldBhn={allowOldBhn}
                  onAllowOldBhnChange={setAllowOldBhn}
                />
              )}

              {defectSubmode === 'linked' && defectSourceItem && weight && Number(weight) > 0 && (
                <div className="text-xs text-blue-700 dark:text-blue-300 bg-blue-50 dark:bg-blue-900/20 px-3 py-2 rounded">
                  Sisa setelah defect ini: <span className="font-semibold tabular-nums">
                    {Math.max(0, defectSourceItem.available_grams - (unit === 'kg' ? Number(weight) * 1000 : Number(weight)))}g
                  </span> dari {defectSourceItem.available_grams}g available
                </div>
              )}

              <div>
                <label className="block text-sm text-gray-600 dark:text-gray-300 mb-1">
                  Alasan Defect <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={defectReason}
                  onChange={(e) => setDefectReason(e.target.value)}
                  placeholder="Mis. Kemasan rusak, expired, bau busuk..."
                  className={INPUT}
                  required={mode === 'defect'}
                />
              </div>
              <div>
                <label className="block text-sm text-gray-600 dark:text-gray-300 mb-1">Foto Bukti</label>
                <input
                  type="file"
                  accept="image/jpeg,image/jpg,image/png,image/webp"
                  onChange={onPickPhoto}
                  className="block w-full text-sm text-gray-700 dark:text-gray-300 file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:bg-gray-100 dark:file:bg-gray-700 file:text-gray-700 dark:file:text-gray-200 hover:file:bg-gray-200 dark:hover:file:bg-gray-600"
                />
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">JPG/PNG/WebP, maks 5MB. Optional tapi disarankan.</p>
                {photoPreview && (
                  <img src={photoPreview} alt="preview" className="mt-2 max-h-40 rounded border border-gray-200 dark:border-gray-700" />
                )}
              </div>
            </>
          )}

          <div className="flex gap-2">
            <button
              type="submit"
              className={`flex-1 py-2 text-white rounded text-sm font-medium ${
                mode === 'defect'
                  ? 'bg-red-600 hover:bg-red-700'
                  : 'bg-brand hover:bg-brand-dark'
              }`}
            >
              {mode === 'defect' ? 'Catat Defect' : 'Submit'}
            </button>
            {mode === 'receiving' && (
              <button
                type="button"
                onClick={handleTestPrint}
                disabled={testPrinting}
                title="Cetak label sample untuk cek printer. Tidak masuk database."
                className="px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-200 rounded text-sm font-medium hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50"
              >
                {testPrinting ? 'Mencetak...' : 'Test Print'}
              </button>
            )}
          </div>
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

      {/* Defect Items Table */}
      <div className={CARD}>
        <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-red-700 dark:text-red-400">
            Defect / Bahan Ditolak {defectTotal > 0 ? `(${defectTotal})` : ''}
          </h3>
          <span className="text-xs text-gray-500 dark:text-gray-400">Filter: tanggal & cari di atas</span>
        </div>
        <div className="p-4 overflow-x-auto">
          {defectLoading ? (
            <div className="text-center text-sm text-gray-500 py-6">Memuat…</div>
          ) : defects.length === 0 ? (
            <div className="text-center text-sm text-gray-400 py-6">Tidak ada defect untuk filter ini.</div>
          ) : (
            <table className="w-full text-sm">
              <thead className="text-left text-xs uppercase text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
                <tr>
                  <th className="py-2 pr-3">ID</th>
                  <th className="py-2 pr-3">Nama</th>
                  <th className="py-2 pr-3">Berat</th>
                  <th className="py-2 pr-3">Dari BHN</th>
                  <th className="py-2 pr-3">Alasan</th>
                  <th className="py-2 pr-3">Foto</th>
                  <th className="py-2 pr-3">Waktu</th>
                  <th className="py-2 pr-3"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                {defects.map((d) => (
                  <tr key={d.id} className="text-gray-900 dark:text-gray-100">
                    <td className="py-2 pr-3 font-mono text-xs">{d.id}</td>
                    <td className="py-2 pr-3">{d.name}</td>
                    <td className="py-2 pr-3 tabular-nums">{d.weight_grams}{d.unit === 'kg' ? 'g' : d.unit}</td>
                    <td className="py-2 pr-3">
                      {d.item_id ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-300 rounded text-xs font-mono"
                          title={d.source_item_name || ''}>
                          {d.item_id}
                        </span>
                      ) : (
                        <span className="text-xs text-gray-400">—</span>
                      )}
                    </td>
                    <td className="py-2 pr-3 text-red-700 dark:text-red-400">{d.defect_reason}</td>
                    <td className="py-2 pr-3">
                      {d.photo_path ? (
                        <button
                          onClick={() => setPhotoView(d.id)}
                          className="text-xs text-blue-600 dark:text-blue-400 underline hover:opacity-80"
                        >
                          Lihat
                        </button>
                      ) : (
                        <span className="text-xs text-gray-400">—</span>
                      )}
                    </td>
                    <td className="py-2 pr-3 text-xs text-gray-500 dark:text-gray-400 tabular-nums">{formatDateTime(d.created_at)}</td>
                    <td className="py-2 pr-3">
                      <button
                        onClick={() => setDefectDeleteId(d.id)}
                        className="px-2 py-1 text-xs bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 rounded hover:bg-red-200 dark:hover:bg-red-900/50"
                      >
                        Hapus
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <Pagination page={defectPage} totalPages={defectTotalPages} onPageChange={setDefectPage} />
        </div>
      </div>

      {/* Photo viewer */}
      {photoView && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50" onClick={() => setPhotoView(null)}>
          <img
            src={defectPhotoUrl(photoView)}
            alt="defect"
            className="max-h-[90vh] max-w-[90vw] rounded border border-gray-700"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}

      {/* Defect delete confirm */}
      {defectDeleteId && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setDefectDeleteId(null)}>
          <div className={`${CARD} p-6 w-full max-w-sm mx-4`} onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-bold text-gray-800 dark:text-gray-100 mb-2">Hapus Defect?</h3>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-6">
              <span className="font-mono font-medium">{defectDeleteId}</span> akan dihapus permanen, termasuk foto-nya.
            </p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setDefectDeleteId(null)}
                className="px-4 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700">
                Batal
              </button>
              <button onClick={handleDefectDelete} disabled={defectDeleteLoading}
                className="px-4 py-2 text-sm bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50">
                {defectDeleteLoading ? 'Menghapus...' : 'Hapus'}
              </button>
            </div>
          </div>
        </div>
      )}

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
