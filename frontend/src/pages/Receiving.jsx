import { useState, useRef } from 'react'
import { createItem } from '../api/items'

const CHECKLIST_ITEMS = [
  { key: 'packaging_ok', label: 'Packaging OK' },
  { key: 'expiry_ok', label: 'Expiry OK' },
  { key: 'temperature_ok', label: 'Temperature OK' },
  { key: 'cleanliness_ok', label: 'Cleanliness OK' },
]

const INPUT = 'w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-accent'

export default function Receiving() {
  const [name, setName] = useState('')
  const [weight, setWeight] = useState('')
  const [unit, setUnit] = useState('g')
  const [checklist, setChecklist] = useState({})
  const [notes, setNotes] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const nameRef = useRef(null)

  const playSound = (ok) => {
    try {
      new Audio(ok ? '/SUCCESS.mp3' : '/FAILED.mp3').play()
    } catch {}
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!name.trim() || !weight || Number(weight) <= 0) {
      setResult({ ok: false, message: 'Name and weight are required' })
      playSound(false)
      return
    }
    setLoading(true)
    setResult(null)
    try {
      const res = await createItem({
        name: name.trim(),
        weight: Number(weight),
        unit,
        checklist,
        notes: notes.trim() || undefined,
      })
      setResult({ ok: true, message: `Created: ${res.data.id}`, data: res.data })
      playSound(true)
      setName('')
      setWeight('')
      setChecklist({})
      setNotes('')
      nameRef.current?.focus()
    } catch (err) {
      setResult({ ok: false, message: err.response?.data?.detail || 'Failed to create item' })
      playSound(false)
    } finally {
      setLoading(false)
    }
  }

  return (
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

      <form onSubmit={handleSubmit} className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 space-y-4">
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
          disabled={loading}
          className="w-full py-2 bg-brand text-white rounded text-sm font-medium hover:bg-brand-dark disabled:opacity-50"
        >
          {loading ? 'Saving...' : 'Submit'}
        </button>
      </form>
    </div>
  )
}
