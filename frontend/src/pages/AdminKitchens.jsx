import { useEffect, useState } from 'react'
import { listKitchens, createKitchen, patchKitchen, deleteKitchen, rotateScannerKey, rotatePrintKey } from '../api/admin'

const EMPTY = {
  slug: '', name: '', printer_name: '', printer_lang: 'ZPL',
  label_title: '', scanner_key: '', cloud_print_key: '',
  address: '', timezone: 'Asia/Jakarta', active: true,
}

export default function AdminKitchens() {
  const [kitchens, setKitchens] = useState([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(null)   // kitchen object, or `EMPTY` for new
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const refresh = () => {
    setLoading(true)
    listKitchens()
      .then(r => setKitchens(r.data.kitchens))
      .catch(e => setError(e.response?.data?.detail || e.message))
      .finally(() => setLoading(false))
  }
  useEffect(refresh, [])

  const onSave = async () => {
    setSaving(true); setError('')
    try {
      if (editing.id) {
        const { id, created_at, ...patch } = editing
        await patchKitchen(id, patch)
      } else {
        await createKitchen(editing)
      }
      setEditing(null)
      refresh()
    } catch (e) {
      setError(e.response?.data?.detail || e.message)
    } finally {
      setSaving(false)
    }
  }

  const onDelete = async (k) => {
    if (!confirm(`Deactivate kitchen "${k.name}"?`)) return
    await deleteKitchen(k.id)
    refresh()
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-900 dark:text-white">Kitchens</h1>
        <button
          onClick={() => setEditing({ ...EMPTY })}
          className="px-3 py-1.5 bg-brand text-white rounded hover:bg-brand/90 text-sm"
        >+ New kitchen</button>
      </div>

      {error && <div className="bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 px-3 py-2 rounded text-sm">{error}</div>}

      <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 dark:bg-gray-700/50 text-left text-xs uppercase tracking-wider text-gray-500 dark:text-gray-400">
            <tr>
              <th className="px-3 py-2">ID</th>
              <th className="px-3 py-2">Slug</th>
              <th className="px-3 py-2">Name</th>
              <th className="px-3 py-2">Printer</th>
              <th className="px-3 py-2">Lang</th>
              <th className="px-3 py-2">Active</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
            {loading ? (
              <tr><td colSpan={7} className="px-3 py-6 text-center text-gray-500 dark:text-gray-400">Loading…</td></tr>
            ) : kitchens.length === 0 ? (
              <tr><td colSpan={7} className="px-3 py-6 text-center text-gray-500 dark:text-gray-400">No kitchens</td></tr>
            ) : kitchens.map(k => (
              <tr key={k.id} className="text-gray-900 dark:text-gray-100">
                <td className="px-3 py-2">{k.id}</td>
                <td className="px-3 py-2 font-mono text-xs">{k.slug}</td>
                <td className="px-3 py-2">{k.name}</td>
                <td className="px-3 py-2 text-xs">{k.printer_name || '—'}</td>
                <td className="px-3 py-2 text-xs">{k.printer_lang}</td>
                <td className="px-3 py-2">
                  <span className={`inline-block px-2 py-0.5 rounded text-xs ${k.active ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' : 'bg-gray-200 text-gray-600 dark:bg-gray-700 dark:text-gray-400'}`}>
                    {k.active ? 'active' : 'inactive'}
                  </span>
                </td>
                <td className="px-3 py-2 text-right whitespace-nowrap">
                  <button onClick={() => setEditing({ ...k })} className="text-brand hover:underline text-xs mr-3">Edit</button>
                  {k.active && (
                    <button onClick={() => onDelete(k)} className="text-red-600 hover:underline text-xs">Deactivate</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {editing && (
        <Modal onClose={() => !saving && setEditing(null)}>
          <h2 className="text-lg font-semibold mb-3 text-gray-900 dark:text-white">
            {editing.id ? `Edit kitchen #${editing.id}` : 'New kitchen'}
          </h2>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Slug" value={editing.slug} onChange={v => setEditing(p => ({ ...p, slug: v }))} disabled={!!editing.id} />
            <Field label="Name" value={editing.name} onChange={v => setEditing(p => ({ ...p, name: v }))} />
            <Field label="Label title (sidebar)" value={editing.label_title || ''} onChange={v => setEditing(p => ({ ...p, label_title: v }))} />
            <Field label="Timezone" value={editing.timezone || ''} onChange={v => setEditing(p => ({ ...p, timezone: v }))} />
            <Field label="Printer name" value={editing.printer_name || ''} onChange={v => setEditing(p => ({ ...p, printer_name: v }))} />
            <div>
              <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Printer lang</label>
              <select
                value={editing.printer_lang || 'ZPL'}
                onChange={e => setEditing(p => ({ ...p, printer_lang: e.target.value }))}
                className="w-full px-2 py-1.5 bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded text-sm text-gray-900 dark:text-white"
              >
                <option value="ZPL">ZPL</option>
                <option value="TSPL">TSPL</option>
              </select>
            </div>
            <KeyField
              label="Scanner key"
              value={editing.scanner_key || ''}
              onRotate={editing.id ? async () => {
                if (!confirm('Rotate scanner key? Existing scanner devices must be reconfigured.')) return
                const r = await rotateScannerKey(editing.id)
                setEditing(p => ({ ...p, scanner_key: r.data.scanner_key }))
              } : null}
            />
            <KeyField
              label="Cloud print key"
              value={editing.cloud_print_key || ''}
              onRotate={editing.id ? async () => {
                if (!confirm('Rotate cloud print key? Print server will need re-auth.')) return
                const r = await rotatePrintKey(editing.id)
                setEditing(p => ({ ...p, cloud_print_key: r.data.cloud_print_key }))
              } : null}
            />
            <Field label="Address" value={editing.address || ''} onChange={v => setEditing(p => ({ ...p, address: v }))} full />
            <label className="col-span-2 flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300 mt-2">
              <input
                type="checkbox"
                checked={!!editing.active}
                onChange={e => setEditing(p => ({ ...p, active: e.target.checked }))}
              />
              Active
            </label>
          </div>
          <div className="mt-4 flex justify-end gap-2">
            <button onClick={() => setEditing(null)} disabled={saving} className="px-3 py-1.5 text-sm text-gray-600 dark:text-gray-300">Cancel</button>
            <button onClick={onSave} disabled={saving} className="px-3 py-1.5 text-sm bg-brand text-white rounded hover:bg-brand/90 disabled:opacity-50">
              {saving ? 'Saving…' : 'Save'}
            </button>
          </div>
        </Modal>
      )}
    </div>
  )
}

function Field({ label, value, onChange, disabled, mono, full }) {
  return (
    <div className={full ? 'col-span-2' : ''}>
      <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">{label}</label>
      <input
        value={value}
        onChange={e => onChange(e.target.value)}
        disabled={disabled}
        className={`w-full px-2 py-1.5 bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded text-sm text-gray-900 dark:text-white disabled:bg-gray-100 dark:disabled:bg-gray-800 ${mono ? 'font-mono' : ''}`}
      />
    </div>
  )
}

function KeyField({ label, value, onRotate }) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <label className="block text-xs text-gray-500 dark:text-gray-400">{label}</label>
        {onRotate && (
          <button onClick={onRotate}
            className="text-xs text-brand hover:underline">
            Rotate
          </button>
        )}
      </div>
      <input
        value={value}
        readOnly
        placeholder={onRotate ? 'auto-generated — click Rotate to refresh' : 'auto-generated on save'}
        className="w-full px-2 py-1.5 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded text-sm text-gray-700 dark:text-gray-200 font-mono"
      />
    </div>
  )
}

function Modal({ children, onClose }) {
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50" onClick={onClose}>
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl p-5 w-full max-w-2xl" onClick={e => e.stopPropagation()}>
        {children}
      </div>
    </div>
  )
}
