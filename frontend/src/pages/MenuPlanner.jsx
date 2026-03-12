import { useState, useEffect, useRef } from 'react'
import { optimizeMenu, getPriceStatus, triggerScrape, listFoods, getScrapeIsRunning, getAkgPresets } from '../api/menu'

// ── Shared styles ────────────────────────────────────────────────────────────
const CARD = 'bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700'
const INPUT = 'rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent'
const BTN_PRIMARY = 'px-5 py-2 bg-brand hover:opacity-90 text-white rounded-lg font-semibold text-sm disabled:opacity-40 transition-opacity'
const BTN_SECONDARY = 'px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 rounded-lg text-sm disabled:opacity-40 transition-colors'

const TOTAL_TKPI = 1145

const CAT_LABELS = {
  staple: 'Makanan Pokok',
  animal: 'Lauk Hewani',
  plant: 'Lauk Nabati',
  vegetable: 'Sayuran',
  fruit: 'Buah',
  other: 'Lainnya',
}

const CAT_COLORS = {
  staple:    'bg-amber-100  dark:bg-amber-900/40  text-amber-800  dark:text-amber-200',
  animal:    'bg-red-100    dark:bg-red-900/40    text-red-800    dark:text-red-200',
  plant:     'bg-green-100  dark:bg-green-900/40  text-green-800  dark:text-green-200',
  vegetable: 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-800 dark:text-emerald-200',
  fruit:     'bg-orange-100 dark:bg-orange-900/40 text-orange-800 dark:text-orange-200',
  other:     'bg-gray-100   dark:bg-gray-700     text-gray-700   dark:text-gray-300',
}

const CAT_ORDER = ['staple', 'animal', 'plant', 'vegetable', 'fruit', 'other']

function rp(n) {
  return 'Rp ' + Math.round(n).toLocaleString('id-ID')
}

// ── Nutrition bar ─────────────────────────────────────────────────────────────
function NutrBar({ label, value, target, unit, isMax }) {
  const pct = Math.min(100, (value / target) * 100)
  const ok  = isMax ? value <= target : value >= target
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-14 text-gray-400 dark:text-gray-500 shrink-0">{label}</span>
      <div className="flex-1 h-1.5 bg-gray-200 dark:bg-gray-600 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${ok ? 'bg-accent' : 'bg-red-400'}`} style={{ width: `${pct}%` }} />
      </div>
      <span className={`w-16 text-right tabular-nums shrink-0 ${ok ? 'text-gray-500 dark:text-gray-400' : 'text-red-500 font-semibold'}`}>
        {Number(value).toFixed(1)}{unit}
      </span>
    </div>
  )
}

// ── Day card ─────────────────────────────────────────────────────────────────
function DayCard({ day, constraints }) {
  const c = constraints || {}
  if (!day.feasible) {
    return (
      <div className={`${CARD} flex flex-col`}>
        <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
          <span className="font-bold text-sm text-gray-800 dark:text-gray-100">{day.label}</span>
        </div>
        <div className="flex-1 flex items-center justify-center p-6 text-gray-400 text-sm">Tidak ada solusi optimal</div>
      </div>
    )
  }
  const grouped = {}
  CAT_ORDER.forEach((cat) => {
    const items = day.items.filter((it) => it.category === cat)
    if (items.length) grouped[cat] = items
  })
  return (
    <div className={`${CARD} flex flex-col`}>
      <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
        <span className="font-bold text-sm text-gray-800 dark:text-gray-100">{day.label}</span>
        <span className="text-xs font-semibold text-accent">{rp(day.cost_per_serving)}/porsi</span>
      </div>
      <div className="flex-1 p-3 space-y-3">
        {CAT_ORDER.filter((cat) => grouped[cat]).map((cat) => (
          <div key={cat}>
            <div className={`text-[10px] px-1.5 py-0.5 rounded font-semibold inline-block mb-1 ${CAT_COLORS[cat]}`}>{CAT_LABELS[cat]}</div>
            {grouped[cat].map((item, i) => (
              <div key={i} className="flex items-baseline justify-between gap-1 text-sm py-0.5">
                <span className="text-gray-700 dark:text-gray-300 leading-tight">{item.name}</span>
                <span className="text-xs text-gray-400 whitespace-nowrap shrink-0">{Math.round(item.grams)}g</span>
              </div>
            ))}
          </div>
        ))}
      </div>
      <div className="px-3 pb-3 pt-2 border-t border-gray-100 dark:border-gray-700 space-y-1.5">
        <NutrBar label="Energi"  value={day.nutrition.energy}  target={c.min_energy  || 600} unit=" kkal" />
        <NutrBar label="Protein" value={day.nutrition.protein} target={c.min_protein || 15}  unit="g" />
        <NutrBar label="Lemak"   value={day.nutrition.fat}     target={c.max_fat     || 25}  unit="g" isMax />
        <NutrBar label="Karbo"   value={day.nutrition.carbs}   target={c.min_carbs   || 80}  unit="g" />
        <NutrBar label="Serat"   value={day.nutrition.fiber}   target={c.min_fiber   || 4}   unit="g" />
      </div>
    </div>
  )
}

// ── Scrape progress bar ───────────────────────────────────────────────────────
function ScrapeProgress({ count, target, active }) {
  const pct = Math.min(100, Math.round((count / target) * 100))
  return (
    <div className="mt-3">
      <div className="flex items-center justify-between text-xs mb-1">
        <span className="text-gray-600 dark:text-gray-400">
          {active ? (
            <span className="flex items-center gap-1.5">
              <span className="inline-block w-2 h-2 rounded-full bg-accent animate-pulse" />
              Sedang scraping... {count} / {target} bahan
            </span>
          ) : (
            <span>{count} / {target} bahan sudah punya harga</span>
          )}
        </span>
        <span className="font-semibold text-gray-700 dark:text-gray-300">{pct}%</span>
      </div>
      <div className="w-full h-2.5 bg-gray-200 dark:bg-gray-600 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${active ? 'bg-accent' : pct === 100 ? 'bg-green-500' : 'bg-accent'}`}
          style={{ width: `${Math.max(pct, count > 0 ? 1 : 0)}%` }}
        />
      </div>
    </div>
  )
}

// ── Price scrape status banner ────────────────────────────────────────────────
function PriceStatusBanner({ onCountChange }) {
  const [count, setCount]       = useState(0)
  const [loading, setLoading]   = useState(true)
  const [scraping, setScraping] = useState(false)
  const [msg, setMsg]           = useState(null)
  const [lastAt, setLastAt]     = useState(null)
  const pollRef                 = useRef(null)
  const prevCountRef            = useRef(0)

  const fetchStatus = () => {
    Promise.all([getPriceStatus(), getScrapeIsRunning()])
      .then(([statusRes, runningRes]) => {
        const n = statusRes.data?.count || 0
        setCount(n)
        if (onCountChange) onCountChange(n)
        const newest = statusRes.data?.prices?.[0]?.scraped_at
        if (newest) setLastAt(newest)
        prevCountRef.current = n
        const stillRunning = runningRes.data?.running ?? false
        if (!stillRunning) {
          setScraping(false)
          clearInterval(pollRef.current)
          pollRef.current = null
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchStatus()
    return () => clearInterval(pollRef.current)
  }, [])

  const startPolling = () => {
    clearInterval(pollRef.current)
    pollRef.current = setInterval(fetchStatus, 5000)
  }

  const handleScrape = (maxItems) => {
    setScraping(true)
    setMsg(null)
    triggerScrape(maxItems)
      .then((r) => { setMsg(r.data.message); startPolling() })
      .catch((e) => { setMsg(e.response?.data?.detail || 'Gagal memulai scrape.'); setScraping(false) })
  }

  if (loading) return null

  return (
    <div className={`${CARD} p-4 mb-6 ${count === 0 ? 'border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-900/20' : ''}`}>
      <div className="flex flex-wrap items-start gap-4">
        <div className="flex-1 min-w-0">
          {count === 0 ? (
            <>
              <div className="font-semibold text-amber-800 dark:text-amber-300 text-sm mb-1">
                ⚠ Harga bahan makanan belum tersedia
              </div>
              <p className="text-xs text-amber-700 dark:text-amber-400">
                Menu optimizer butuh data harga dari Sayurbox. Klik <strong>"Scrape 50 Item"</strong> untuk
                test cepat (~7 menit), atau <strong>"Scrape Semua"</strong> untuk data lengkap (~3-4 jam, berjalan di background).
              </p>
            </>
          ) : (
            <div className="text-sm text-gray-700 dark:text-gray-300">
              <span className="font-semibold">{count} bahan</span> sudah ada harga pasar
              {lastAt && <span className="ml-2 text-xs text-gray-400">· diperbarui {new Date(lastAt).toLocaleDateString('id-ID')}</span>}
              {count < TOTAL_TKPI && <span className="ml-2 text-xs text-amber-600 dark:text-amber-400">· {TOTAL_TKPI - count} bahan belum ada harga (tidak masuk optimizer)</span>}
            </div>
          )}
          <ScrapeProgress count={count} target={TOTAL_TKPI} active={scraping} />
          {msg && (
            <p className={`text-xs mt-2 ${msg.toLowerCase().includes('gagal') ? 'text-red-600 dark:text-red-400' : 'text-green-700 dark:text-green-400'}`}>
              {msg}
            </p>
          )}
        </div>
        <div className="flex flex-col gap-2 shrink-0">
          <button onClick={() => handleScrape(50)} disabled={scraping} className={BTN_SECONDARY}>
            {scraping ? (
              <span className="flex items-center gap-1.5">
                <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
                </svg>
                Berjalan...
              </span>
            ) : 'Scrape 50 Item'}
          </button>
          <button onClick={() => handleScrape(0)} disabled={scraping} className={BTN_PRIMARY}>
            {scraping ? 'Berjalan...' : 'Scrape Semua'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Food table ────────────────────────────────────────────────────────────────
const TABLE_CATS = ['all', ...CAT_ORDER]

function FoodTable({ priceCount, excludedFoods, onExcludedChange }) {
  const [foods, setFoods]           = useState(null)
  const [loading, setLoading]       = useState(false)
  const [catFilter, setCatFilter]   = useState('all')
  const [search, setSearch]         = useState('')
  const [onlyPriced, setOnlyPriced] = useState(false)
  const [page, setPage]             = useState(1)
  const PAGE_SIZE = 50

  const toggleExclude = (code) => {
    const next = new Set(excludedFoods)
    if (next.has(code)) next.delete(code)
    else next.add(code)
    onExcludedChange(next)
  }

  const allExcluded = excludedFoods.size > 0

  const load = () => {
    setLoading(true)
    listFoods()
      .then((r) => setFoods(r.data))
      .catch(() => setFoods(null))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    if (priceCount > 0 && foods === null) load()
  }, [priceCount])

  const allItems = foods ? Object.values(foods.categories).flat() : []

  const filtered = allItems.filter((f) => {
    if (catFilter !== 'all' && f.category !== catFilter) return false
    if (onlyPriced && !f.has_price) return false
    if (search && !f.name.toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const pageItems  = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)
  const resetPage  = () => setPage(1)

  if (priceCount === 0 && !foods) return null

  return (
    <div className={`${CARD} mb-6`}>
      <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-gray-800 dark:text-gray-100">Daftar Bahan Makanan TKPI 2020</h3>
          {foods && (
            <p className="text-xs text-gray-400 mt-0.5">
              {foods.total} bahan · <span className="text-accent">{foods.with_price} punya harga</span> · {foods.without_price} belum
            </p>
          )}
        </div>
        <div className="flex gap-2">
          {!foods && <button onClick={load} disabled={loading} className={BTN_SECONDARY}>{loading ? 'Memuat...' : 'Tampilkan Tabel'}</button>}
          {foods && <button onClick={load} disabled={loading} className={BTN_SECONDARY + ' text-xs'}>{loading ? 'Memuat...' : '↻ Refresh'}</button>}
        </div>
      </div>

      {loading && <div className="p-8 text-center text-sm text-gray-400">Memuat data bahan makanan...</div>}

      {foods && (
        <>
          <div className="px-4 py-3 border-b border-gray-100 dark:border-gray-700 flex flex-wrap gap-2 items-center">
            <input type="text" placeholder="Cari nama bahan..." value={search}
              onChange={(e) => { setSearch(e.target.value); resetPage() }}
              className={INPUT + ' w-48'} />
            <select value={catFilter} onChange={(e) => { setCatFilter(e.target.value); resetPage() }} className={INPUT}>
              {TABLE_CATS.map((c) => (
                <option key={c} value={c}>{c === 'all' ? 'Semua Kategori' : CAT_LABELS[c]}</option>
              ))}
            </select>
            <label className="flex items-center gap-1.5 text-xs text-gray-600 dark:text-gray-400 cursor-pointer select-none">
              <input type="checkbox" checked={onlyPriced} onChange={(e) => { setOnlyPriced(e.target.checked); resetPage() }} className="rounded" />
              Hanya yang punya harga
            </label>
            {allExcluded && (
              <button onClick={() => onExcludedChange(new Set())}
                className="text-xs text-red-500 hover:underline ml-1">
                Reset {excludedFoods.size} exclude
              </button>
            )}
            <span className="ml-auto text-xs text-gray-400">{filtered.length} bahan</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-gray-100 dark:border-gray-700 bg-gray-50 dark:bg-gray-700/50">
                  <th className="px-3 py-2.5 w-8 text-center" title="Ikutkan dalam optimizer"><span className="text-[10px] text-gray-400 font-semibold">Opt</span></th>
                  <th className="text-left px-3 py-2.5 text-gray-500 font-semibold w-20">Kode</th>
                  <th className="text-left px-3 py-2.5 text-gray-500 font-semibold">Nama Bahan</th>
                  <th className="text-left px-3 py-2.5 text-gray-500 font-semibold w-28">Kategori</th>
                  <th className="text-right px-3 py-2.5 text-gray-500 font-semibold">Energi (kkal)</th>
                  <th className="text-right px-3 py-2.5 text-gray-500 font-semibold">Protein (g)</th>
                  <th className="text-right px-3 py-2.5 text-gray-500 font-semibold">Harga/100g</th>
                  <th className="text-center px-3 py-2.5 text-gray-500 font-semibold w-16">Siap</th>
                </tr>
              </thead>
              <tbody>
                {pageItems.length === 0 && (
                  <tr><td colSpan={8} className="text-center py-8 text-gray-400">Tidak ada data</td></tr>
                )}
                {pageItems.map((f) => {
                  const excluded = excludedFoods.has(f.code)
                  return (
                  <tr key={f.code} className={`border-b border-gray-50 dark:border-gray-700/50 hover:bg-gray-50 dark:hover:bg-gray-700/30 transition-colors ${excluded ? 'opacity-40' : ''}`}>
                    <td className="px-3 py-2 text-center">
                      <input type="checkbox" checked={!excluded} onChange={() => toggleExclude(f.code)}
                        className="rounded cursor-pointer"
                        title={excluded ? 'Ikutkan dalam optimizer' : 'Exclude dari optimizer'} />
                    </td>
                    <td className="px-3 py-2 font-mono text-gray-400 text-[11px]">{f.code}</td>
                    <td className="px-3 py-2 text-gray-800 dark:text-gray-200 max-w-xs leading-snug">{f.name}</td>
                    <td className="px-3 py-2">
                      <span className={`text-[10px] px-1.5 py-0.5 rounded font-semibold ${CAT_COLORS[f.category] || CAT_COLORS.other}`}>
                        {CAT_LABELS[f.category] || f.category}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums text-gray-600 dark:text-gray-400">{f.energy.toFixed(0)}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-gray-600 dark:text-gray-400">{f.protein.toFixed(1)}</td>
                    <td className="px-3 py-2 text-right tabular-nums">
                      {f.has_price ? <span className="text-accent font-semibold">{rp(f.price)}</span> : <span className="text-gray-300 dark:text-gray-600">—</span>}
                    </td>
                    <td className="px-3 py-2 text-center">
                      {f.has_price ? <span className="text-green-500 font-bold">✓</span> : <span className="text-gray-300 dark:text-gray-600">—</span>}
                    </td>
                  </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div className="px-4 py-3 border-t border-gray-100 dark:border-gray-700 flex items-center justify-between">
              <span className="text-xs text-gray-400">Hal {page} / {totalPages} · {filtered.length} bahan</span>
              <div className="flex gap-1">
                <button onClick={() => setPage(1)} disabled={page === 1} className={BTN_SECONDARY + ' !px-2 !py-1'}>«</button>
                <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} className={BTN_SECONDARY + ' !px-2 !py-1'}>‹</button>
                {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                  const p = Math.max(1, Math.min(totalPages - 4, page - 2)) + i
                  return (
                    <button key={p} onClick={() => setPage(p)}
                      className={p === page ? 'px-2 py-1 rounded bg-brand text-white text-xs font-semibold' : BTN_SECONDARY + ' !px-2 !py-1'}>
                      {p}
                    </button>
                  )
                })}
                <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages} className={BTN_SECONDARY + ' !px-2 !py-1'}>›</button>
                <button onClick={() => setPage(totalPages)} disabled={page === totalPages} className={BTN_SECONDARY + ' !px-2 !py-1'}>»</button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}

const DEFAULT_CONSTRAINTS = {
  min_energy: 600, min_protein: 15, max_fat: 25,
  min_carbs: 80, min_fiber: 4, min_iron: 3, min_vitc: 15,
}

function NumField({ label, value, onChange, min, max, unit, disabled, w = 90 }) {
  return (
    <div>
      <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">
        {label}{unit && <span className="text-gray-400 ml-1">({unit})</span>}
      </label>
      <input type="number" min={min} max={max} value={value} disabled={disabled}
        onChange={(e) => onChange(+e.target.value || min)}
        className={INPUT + (disabled ? ' cursor-not-allowed' : '')} style={{ width: w }} />
    </div>
  )
}

// ── Age group presets (must match backend AKG_PRESETS keys) ──────────────────
const AGE_GROUP_KEYS = [
  'TK (4-6 tahun)',
  'SD (7-9 tahun)',
  'SD (10-12 tahun)',
  'SMP (13-15 tahun)',
  'SMA (16-18 tahun)',
]

// ── Group result block ────────────────────────────────────────────────────────
function GroupResult({ group, numDays }) {
  const [open, setOpen] = useState(false)
  const c = group.constraints_used || {}
  const feasible = group.week.filter((d) => d.feasible)
  return (
    <div className={`${CARD} mb-4 overflow-hidden`}>
      {/* Header — always visible */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full px-4 py-3 flex flex-wrap items-center gap-3 hover:bg-gray-50 dark:hover:bg-gray-700/30 transition-colors text-left"
      >
        <div className="flex-1 min-w-0">
          <span className="font-bold text-sm text-gray-800 dark:text-gray-100">{group.label}</span>
          <span className="ml-2 text-xs text-gray-400">{group.num_students} siswa</span>
        </div>
        <div className="flex gap-3 flex-wrap">
          {[
            { label: 'Per Siswa / Hari',      value: rp(feasible.length ? group.weekly_per_student / feasible.length : 0) },
            { label: `Total ${numDays} Hari`, value: rp(group.weekly_total) },
            { label: 'Rata Energi',           value: (group.avg_nutrition?.energy || 0) + ' kkal' },
          ].map((s) => (
            <div key={s.label} className="text-center">
              <div className="text-[10px] text-gray-400 uppercase tracking-wide">{s.label}</div>
              <div className="text-sm font-bold text-brand dark:text-accent">{s.value}</div>
            </div>
          ))}
        </div>
        <span className="text-gray-400 text-xs ml-2">{open ? '▲' : '▼'}</span>
      </button>

      {/* Collapsible content */}
      {open && (
        <div className="px-4 pb-4 border-t border-gray-100 dark:border-gray-700 pt-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
            {group.week.map((day) => <DayCard key={day.day} day={day} constraints={c} />)}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function MenuPlanner() {
  const [numDays, setNumDays]         = useState(5)
  const [budget, setBudget]           = useState(0)
  const [budgetMin, setBudgetMin]     = useState(0)
  const [priceMin, setPriceMin]       = useState(0)
  const [priceMax, setPriceMax]       = useState(0)
  const [excludedFoods, setExcludedFoods] = useState(new Set())
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [result, setResult]           = useState(null)
  const [loading, setLoading]         = useState(false)
  const [error, setError]             = useState(null)
  const [priceCount, setPriceCount]   = useState(0)
  const [akgPresets, setAkgPresets]   = useState({})

  // Multi-group state: array of { label, num_students, constraints, showAkg }
  const [groups, setGroups] = useState([
    { label: 'SD (7-9 tahun)', num_students: 100, constraints: { ...DEFAULT_CONSTRAINTS }, showAkg: false },
  ])

  useEffect(() => {
    getAkgPresets().then((r) => {
      setAkgPresets(r.data)
      // apply correct preset for default group
      setGroups((prev) => prev.map((g) => ({
        ...g,
        constraints: { ...(r.data[g.label] || DEFAULT_CONSTRAINTS) },
      })))
    }).catch(() => {})
  }, [])

  const setGroup = (idx, patch) =>
    setGroups((prev) => prev.map((g, i) => i === idx ? { ...g, ...patch } : g))

  const setGroupConstraint = (idx, key, val) =>
    setGroup(idx, { constraints: { ...groups[idx].constraints, [key]: val } })

  const addGroup = () =>
    setGroups((prev) => [
      ...prev,
      { label: AGE_GROUP_KEYS[prev.length % AGE_GROUP_KEYS.length], num_students: 50, constraints: { ...DEFAULT_CONSTRAINTS }, showAkg: false },
    ])

  const removeGroup = (idx) =>
    setGroups((prev) => prev.filter((_, i) => i !== idx))

  const applyPreset = (idx, label) => {
    const preset = akgPresets[label] || DEFAULT_CONSTRAINTS
    setGroups((prev) => prev.map((g, i) => i === idx ? { ...g, label, constraints: { ...preset } } : g))
  }

  const handleOptimize = () => {
    setLoading(true)
    setError(null)
    const payload = {
      num_days: numDays,
      groups: groups.map((g) => {
        const c = { ...g.constraints }
        if (budget > 0) c.max_cost = budget
        return { label: g.label, num_students: g.num_students, constraints: c }
      }),
    }
    if (budgetMin > 0) payload.budget_min = budgetMin
    if (priceMin > 0) payload.price_min = priceMin
    if (priceMax > 0) payload.price_max = priceMax
    if (excludedFoods.size > 0) payload.excluded_foods = [...excludedFoods]
    optimizeMenu(payload)
      .then((res) => setResult(res.data))
      .catch((err) => {
        const detail = err.response?.data?.detail
        setError(typeof detail === 'string' ? detail : 'Gagal mengoptimasi menu.')
      })
      .finally(() => setLoading(false))
  }

  const disabled = priceCount === 0
  const totalStudents = groups.reduce((s, g) => s + g.num_students, 0)

  return (
    <div>
      <h2 className="text-xl font-bold text-gray-800 dark:text-gray-100 mb-1">Menu Planner</h2>
      <p className="text-sm text-gray-500 dark:text-gray-400 mb-6">Optimasi menu makan siang MBG — minimasi biaya, penuhi AKG per kelompok umur.</p>

      <PriceStatusBanner onCountChange={setPriceCount} />

      <div className={`${CARD} p-4 mb-6 ${disabled ? 'opacity-50' : ''}`}>
        {/* Global params */}
        <div className="flex flex-wrap items-end gap-4 mb-4">
          <NumField label="Jumlah Hari" value={numDays} onChange={(v) => setNumDays(Math.max(1, Math.min(7, v)))} min={1} max={7} disabled={disabled} w={80} />
          <NumField label="Budget Min/Porsi" value={budgetMin} onChange={(v) => setBudgetMin(Math.max(0, v))} min={0} unit="Rp, 0=bebas" disabled={disabled} w={130} />
          <NumField label="Budget Maks/Porsi" value={budget} onChange={(v) => setBudget(Math.max(0, v))} min={0} unit="Rp, 0=bebas" disabled={disabled} w={130} />
          <NumField label="Harga Min/100g" value={priceMin} onChange={(v) => setPriceMin(Math.max(0, v))} min={0} unit="Rp, 0=bebas" disabled={disabled} w={130} />
          <NumField label="Harga Maks/100g" value={priceMax} onChange={(v) => setPriceMax(Math.max(0, v))} min={0} unit="Rp, 0=bebas" disabled={disabled} w={130} />
          <div className="flex items-end gap-2">
            <button onClick={handleOptimize} disabled={loading || disabled} className={BTN_PRIMARY}>
              {loading ? (
                <span className="flex items-center gap-2">
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
                  </svg>
                  Mengoptimasi...
                </span>
              ) : 'Optimasi Menu'}
            </button>
          </div>
        </div>

        {/* Age groups */}
        <div className="border-t border-gray-100 dark:border-gray-700 pt-4">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">
              Kelompok Umur · {totalStudents} siswa total
            </span>
            <button onClick={addGroup} disabled={disabled || groups.length >= 5} className="text-xs text-accent hover:underline disabled:opacity-40">
              + Tambah Kelompok
            </button>
          </div>
          <div className="space-y-3">
            {groups.map((g, idx) => (
              <div key={idx} className="border border-gray-200 dark:border-gray-600 rounded-lg p-3">
                <div className="flex flex-wrap items-end gap-3 mb-1">
                  <div>
                    <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Kelompok Umur</label>
                    <select
                      value={g.label}
                      onChange={(e) => applyPreset(idx, e.target.value)}
                      disabled={disabled}
                      className={INPUT}
                    >
                      {AGE_GROUP_KEYS.map((k) => <option key={k} value={k}>{k}</option>)}
                    </select>
                  </div>
                  <NumField label="Jumlah Siswa" value={g.num_students}
                    onChange={(v) => setGroup(idx, { num_students: Math.max(1, v) })}
                    min={1} disabled={disabled} w={100} />
                  <div className="flex items-end gap-2 ml-auto">
                    <button
                      onClick={() => setGroup(idx, { showAkg: !g.showAkg })}
                      disabled={disabled}
                      className={BTN_SECONDARY + ' text-xs !py-1.5'}>
                      {g.showAkg ? 'Sembunyikan AKG ▲' : 'Atur AKG ▼'}
                    </button>
                    {groups.length > 1 && (
                      <button onClick={() => removeGroup(idx)} className="text-xs text-red-400 hover:underline">Hapus</button>
                    )}
                  </div>
                </div>
                {g.showAkg && (
                  <div className="mt-3 pt-3 border-t border-gray-100 dark:border-gray-700">
                    <div className="flex flex-wrap gap-3">
                      <NumField label="Min Energi"  value={g.constraints.min_energy}  onChange={(v) => setGroupConstraint(idx, 'min_energy', v)}  min={0} unit="kkal" disabled={disabled} />
                      <NumField label="Min Protein" value={g.constraints.min_protein} onChange={(v) => setGroupConstraint(idx, 'min_protein', v)} min={0} unit="g"    disabled={disabled} />
                      <NumField label="Maks Lemak"  value={g.constraints.max_fat}     onChange={(v) => setGroupConstraint(idx, 'max_fat', v)}     min={0} unit="g"    disabled={disabled} />
                      <NumField label="Min Karbo"   value={g.constraints.min_carbs}   onChange={(v) => setGroupConstraint(idx, 'min_carbs', v)}   min={0} unit="g"    disabled={disabled} />
                      <NumField label="Min Serat"   value={g.constraints.min_fiber}   onChange={(v) => setGroupConstraint(idx, 'min_fiber', v)}   min={0} unit="g"    disabled={disabled} />
                      <NumField label="Min Besi"    value={g.constraints.min_iron}    onChange={(v) => setGroupConstraint(idx, 'min_iron', v)}    min={0} unit="mg"   disabled={disabled} />
                      <NumField label="Min Vit C"   value={g.constraints.min_vitc}    onChange={(v) => setGroupConstraint(idx, 'min_vitc', v)}    min={0} unit="mg"   disabled={disabled} />
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {disabled
          ? <p className="text-xs text-red-500 dark:text-red-400 mt-3">✕ Tidak bisa dijalankan — scrape harga dulu di atas.</p>
          : <p className="text-xs text-gray-400 dark:text-gray-500 mt-3">LP memilih dari <strong>{priceCount} bahan</strong> yang sudah ada harga, minimasi biaya per kelompok umur.</p>
        }
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-xl p-4 mb-6 text-red-700 dark:text-red-300 text-sm">{error}</div>
      )}

      {result?.mode === 'multi_group' && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-6">
            {[
              { label: 'Total Siswa',           value: result.total_students + ' siswa' },
              { label: `Grand Total ${numDays} Hari`, value: rp(result.grand_total) },
              { label: 'Per Siswa / Hari (avg)', value: rp(result.grand_total / result.total_students / numDays) },
            ].map((s) => (
              <div key={s.label} className={`${CARD} p-4 text-center`}>
                <div className="text-[11px] text-gray-400 uppercase tracking-wide mb-1">{s.label}</div>
                <div className="text-base font-bold text-brand dark:text-accent">{s.value}</div>
              </div>
            ))}
          </div>
          {result.groups.map((g) => <GroupResult key={g.label} group={g} numDays={numDays} />)}
        </>
      )}

      {!result && !loading && priceCount > 0 && (
        <div className={`${CARD} p-12 text-center text-gray-400 dark:text-gray-500 mb-6`}>
          <div className="text-4xl mb-3">🍽</div>
          <div className="text-sm">Klik "Optimasi Menu" untuk membuat rencana makan mingguan</div>
          <div className="text-xs mt-1">LP akan memilih bahan dari TKPI 2020 yang memenuhi AKG per kelompok umur</div>
        </div>
      )}

      <FoodTable priceCount={priceCount} excludedFoods={excludedFoods} onExcludedChange={setExcludedFoods} />
    </div>
  )
}
