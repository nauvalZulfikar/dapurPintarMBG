import { useState, useEffect, useRef } from 'react'
import { Html5Qrcode } from 'html5-qrcode'
import { getItemsForDefect } from '../api/items'

function todayISO() { return new Date().toISOString().slice(0, 10) }
function ymd(d) { return d.toISOString().slice(0, 10) }
function daysAgo(n) {
  const d = new Date(); d.setDate(d.getDate() - n); return ymd(d)
}

// Source-BHN picker for defect form. Combo: camera scan + typeahead + dropdown.
// - Default scope: BHN diterima hari ini (sesuai SOP MBG: ≤1 hari)
// - Toggle: "Tampilkan bahan lama (>1 hari)" untuk override (max 7 hari ke belakang)
// - Already-fully-defected BHN auto-hidden
export default function BhnPicker({ value, onChange, onPickedItem, allowOldBhn, onAllowOldBhnChange }) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)
  const [query, setQuery] = useState('')
  const [showDropdown, setShowDropdown] = useState(false)
  const [scanning, setScanning] = useState(false)
  const [scanError, setScanError] = useState('')
  const inputRef = useRef(null)
  const scannerDivRef = useRef(null)
  const scannerRef = useRef(null)

  const loadItems = async () => {
    setLoading(true)
    try {
      const r = allowOldBhn
        ? await getItemsForDefect()
        : await getItemsForDefect({ date: todayISO() })
      const filtered = (r.data.items || []).filter(it => (it.available_grams ?? 0) > 0)
      // If override on, scope to last 7 days client-side
      const cutoff = daysAgo(7)
      const final = allowOldBhn
        ? filtered.filter(it => (it.created_date_receiving || todayISO()) >= cutoff)
        : filtered
      setItems(final)
    } catch (e) {
      console.error('load BHN failed', e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadItems() /* eslint-disable-next-line */ }, [allowOldBhn])

  const filtered = query.trim()
    ? items.filter(it =>
        it.id.toLowerCase().includes(query.toLowerCase()) ||
        (it.name || '').toLowerCase().includes(query.toLowerCase()))
    : items

  const pick = (it) => {
    onChange(it.id)
    onPickedItem(it)
    setQuery(`${it.id} — ${it.name}`)
    setShowDropdown(false)
    stopScan()
  }

  const clearPick = () => {
    onChange('')
    onPickedItem(null)
    setQuery('')
    inputRef.current?.focus()
  }

  // ── Camera scan via html5-qrcode ──────────────────────────────────────────
  const startScan = async () => {
    setScanError('')
    setScanning(true)
    setTimeout(async () => {
      try {
        const div = scannerDivRef.current
        if (!div) return
        const qr = new Html5Qrcode(div.id)
        scannerRef.current = qr
        await qr.start(
          { facingMode: 'environment' },
          { fps: 10, qrbox: { width: 280, height: 140 } },
          (decoded) => {
            const code = String(decoded || '').trim().toUpperCase()
            // Find matching BHN in current loaded set
            const match = items.find(it => it.id.toUpperCase() === code)
            if (match) {
              pick(match)
            } else {
              setScanError(`BHN "${code}" tidak ditemukan dalam daftar bahan available.`)
              stopScan()
            }
          },
          () => {} // ignore frame-level decode errors
        )
      } catch (e) {
        setScanError('Tidak bisa akses kamera. Pastikan permission diberikan.')
        setScanning(false)
      }
    }, 50)
  }

  const stopScan = async () => {
    setScanning(false)
    const qr = scannerRef.current
    if (qr) {
      try { await qr.stop(); qr.clear() } catch { /* ignore */ }
      scannerRef.current = null
    }
  }

  useEffect(() => () => { stopScan() /* unmount cleanup */ /* eslint-disable-next-line */ }, [])

  return (
    <div className="space-y-2">
      <label className="block text-sm text-gray-600 dark:text-gray-300">
        Bahan Asal (BHN) <span className="text-red-500">*</span>
      </label>

      {value ? (
        <div className="flex items-center gap-2 px-3 py-2 bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-700 rounded">
          <span className="font-mono text-sm font-medium text-blue-900 dark:text-blue-300">{value}</span>
          <button type="button" onClick={clearPick}
            className="ml-auto text-xs text-gray-500 hover:text-red-600 dark:text-gray-400 dark:hover:text-red-400 underline">
            Ganti
          </button>
        </div>
      ) : (
        <>
          <div className="flex gap-2">
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => { setQuery(e.target.value); setShowDropdown(true) }}
              onFocus={() => setShowDropdown(true)}
              placeholder="Scan barcode atau ketik nama bahan..."
              className="flex-1 px-3 py-3 text-base border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-accent"
              autoComplete="off"
            />
            <button
              type="button"
              onClick={scanning ? stopScan : startScan}
              className={`px-4 py-3 rounded text-white text-sm font-medium ${
                scanning ? 'bg-red-600 hover:bg-red-700' : 'bg-blue-600 hover:bg-blue-700'
              }`}
            >
              {scanning ? '✕ Stop' : '📷 Scan'}
            </button>
          </div>

          {scanning && (
            <div className="rounded border border-gray-300 dark:border-gray-600 p-2 bg-gray-900">
              <div id="bhn-scanner-region" ref={scannerDivRef} />
              <p className="text-xs text-gray-300 mt-1">Arahkan kamera ke barcode label BHN.</p>
            </div>
          )}

          {scanError && (
            <div className="text-xs text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 px-2 py-1 rounded">{scanError}</div>
          )}

          {showDropdown && !scanning && (
            <div className="border border-gray-300 dark:border-gray-600 rounded max-h-60 overflow-y-auto bg-white dark:bg-gray-800">
              {loading ? (
                <div className="p-3 text-sm text-gray-500">Memuat...</div>
              ) : filtered.length === 0 ? (
                <div className="p-3 text-sm text-gray-400">Tidak ada bahan available.</div>
              ) : filtered.slice(0, 20).map((it) => (
                <button
                  key={it.id}
                  type="button"
                  onClick={() => pick(it)}
                  className="w-full text-left px-3 py-2.5 hover:bg-blue-50 dark:hover:bg-blue-900/30 border-b border-gray-100 dark:border-gray-700 last:border-0"
                >
                  <div className="flex items-baseline justify-between gap-2">
                    <div className="min-w-0">
                      <div className="text-sm text-gray-900 dark:text-gray-100 truncate">{it.name}</div>
                      <div className="text-xs font-mono text-gray-500 dark:text-gray-400">{it.id}</div>
                    </div>
                    <div className="text-xs text-right tabular-nums whitespace-nowrap">
                      <div className="text-blue-700 dark:text-blue-400 font-medium">
                        {it.available_grams}g available
                      </div>
                      <div className="text-gray-400">dari {it.weight_grams}g</div>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </>
      )}

      <label className="flex items-center gap-2 text-xs text-gray-600 dark:text-gray-400 mt-1">
        <input
          type="checkbox"
          checked={allowOldBhn}
          onChange={(e) => onAllowOldBhnChange(e.target.checked)}
          className="rounded"
        />
        Tampilkan bahan lama (&gt;1 hari) — perlu konfirmasi tambahan
      </label>
    </div>
  )
}
