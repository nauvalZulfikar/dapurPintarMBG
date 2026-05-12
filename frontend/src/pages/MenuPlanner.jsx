import { useState, useEffect, useRef } from 'react'
import { optimizeMenu, getPriceStatus, triggerScrape, listFoods, getScrapeIsRunning, getAkgPresets, overridePrice, getPriceHistory, setNutritionOverride, getSubstitutes, saveMenu, listSavedMenus, getSavedMenu, deleteSavedMenu } from '../api/menu'
import { useAuth } from '../hooks/useAuth'
import { useLocation } from 'react-router-dom'

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

// ── Substitutes popover ───────────────────────────────────────────────────────
function SubstitutesPopover({ item, onSelect, onClose }) {
  const [subs, setSubs]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState('')

  useEffect(() => {
    let cancelled = false
    getSubstitutes(item.name)
      .then((r) => { if (!cancelled) setSubs(r.data.substitutes || []) })
      .catch((e) => { if (!cancelled) setError(e.response?.data?.detail || e.message) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [item.name])

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center" onClick={onClose}>
      <div
        onClick={(e) => e.stopPropagation()}
        className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-md max-h-[80vh] overflow-y-auto p-4"
        data-testid="substitutes-modal"
      >
        <div className="flex items-start justify-between mb-3">
          <div>
            <h3 className="font-semibold text-gray-900 dark:text-white">Substitusi Bahan</h3>
            <p className="text-xs text-gray-500 dark:text-gray-400">{item.name}</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 ml-2 text-lg leading-none">×</button>
        </div>
        {loading && <div className="text-sm text-gray-500 dark:text-gray-400 py-6 text-center">Memuat alternatif…</div>}
        {error && <div className="text-sm text-red-500 dark:text-red-400 py-4 text-center">{error}</div>}
        {!loading && !error && (subs?.length === 0
          ? <div className="text-sm text-gray-500 dark:text-gray-400 py-6 text-center">Tidak ditemukan alternatif serupa.</div>
          : <div className="space-y-2">
              {subs.map((s, i) => (
                <button
                  key={i}
                  data-testid={`substitute-option-${i}`}
                  onClick={() => { onSelect(s); onClose() }}
                  className="w-full text-left border border-gray-200 dark:border-gray-700 rounded-lg p-3 hover:bg-gray-50 dark:hover:bg-gray-700/40 transition-colors"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="font-medium text-sm text-gray-800 dark:text-gray-100 leading-snug">{s.name}</div>
                      <div className="text-[10px] text-gray-400 dark:text-gray-500 mt-0.5 capitalize">{s.category}</div>
                    </div>
                    <span className="text-xs font-semibold text-brand dark:text-accent shrink-0">sim {s.similarity.toFixed(2)}</span>
                  </div>
                  <div className="mt-1.5 flex gap-3 text-xs text-gray-500 dark:text-gray-400">
                    <span>⚡ {s.nutrition.energy.toFixed(0)} kkal</span>
                    <span>🥩 {s.nutrition.protein.toFixed(1)}g protein</span>
                  </div>
                </button>
              ))}
            </div>
        )}
      </div>
    </div>
  )
}

// ── Day card ─────────────────────────────────────────────────────────────────
function DayCard({ day, constraints, onSubstitute }) {
  const { hasPermission } = useAuth()
  const canSub = hasPermission('menu.view')
  const [subItem, setSubItem] = useState(null)
  const c = constraints || {}
  if (!day.feasible) {
    return (
      <div className={`${CARD} flex flex-col`}>
        <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
          <span className="font-bold text-sm text-gray-800 dark:text-gray-100">{day.label}</span>
        </div>
        <div className="flex-1 flex items-center justify-center p-6 text-gray-400 dark:text-gray-500 text-sm">Tidak ada solusi optimal</div>
      </div>
    )
  }
  const grouped = {}
  CAT_ORDER.forEach((cat) => {
    const items = day.items
      .map((it, idx) => ({ ...it, _idx: idx }))
      .filter((it) => it.category === cat)
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
                <span className="flex items-center gap-1 shrink-0">
                  <span className="text-xs text-gray-400 dark:text-gray-500 whitespace-nowrap">{Math.round(item.grams)}g</span>
                  {canSub && (
                    <button
                      data-testid={`sub-btn-${day.day}-${i}`}
                      onClick={() => setSubItem({ ...item, _idx: item._idx })}
                      className="text-[10px] text-brand hover:text-brand/80 dark:text-accent dark:hover:text-accent/80 font-medium leading-none px-1 py-0.5 rounded border border-brand/30 dark:border-accent/30 hover:bg-brand/5 dark:hover:bg-accent/10 transition-colors"
                      title="Cari substitusi"
                    >
                      Sub
                    </button>
                  )}
                </span>
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
      {subItem && (
        <SubstitutesPopover
          item={subItem}
          onSelect={(sub) => onSubstitute && onSubstitute(day.day, subItem, sub, subItem._idx)}
          onClose={() => setSubItem(null)}
        />
      )}
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
              {lastAt && <span className="ml-2 text-xs text-gray-400 dark:text-gray-500">· diperbarui {new Date(lastAt).toLocaleDateString('id-ID')}</span>}
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
              {foods.total} bahan · <span className="text-accent">{foods.with_price} punya harga</span> · {foods.without_price} belum
            </p>
          )}
        </div>
        <div className="flex gap-2">
          {!foods && <button onClick={load} disabled={loading} className={BTN_SECONDARY}>{loading ? 'Memuat...' : 'Tampilkan Tabel'}</button>}
          {foods && <button onClick={load} disabled={loading} className={BTN_SECONDARY + ' text-xs'}>{loading ? 'Memuat...' : '↻ Refresh'}</button>}
        </div>
      </div>

      {loading && <div className="p-8 text-center text-sm text-gray-400 dark:text-gray-500">Memuat data bahan makanan...</div>}

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
            <span className="ml-auto text-xs text-gray-400 dark:text-gray-500">{filtered.length} bahan</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-gray-100 dark:border-gray-700 bg-gray-50 dark:bg-gray-700/50">
                  <th className="px-3 py-2.5 w-8 text-center" title="Ikutkan dalam optimizer"><span className="text-[10px] text-gray-400 dark:text-gray-500 font-semibold">Opt</span></th>
                  <th className="text-left px-3 py-2.5 text-gray-500 dark:text-gray-400 font-semibold w-20">Kode</th>
                  <th className="text-left px-3 py-2.5 text-gray-500 dark:text-gray-400 font-semibold">Nama Bahan</th>
                  <th className="text-left px-3 py-2.5 text-gray-500 dark:text-gray-400 font-semibold w-28">Kategori</th>
                  <th className="text-right px-3 py-2.5 text-gray-500 dark:text-gray-400 font-semibold">Energi (kkal)</th>
                  <th className="text-right px-3 py-2.5 text-gray-500 dark:text-gray-400 font-semibold">Protein (g)</th>
                  <th className="text-right px-3 py-2.5 text-gray-500 dark:text-gray-400 font-semibold">Harga/100g</th>
                  <th className="text-center px-3 py-2.5 text-gray-500 dark:text-gray-400 font-semibold w-16">Siap</th>
                </tr>
              </thead>
              <tbody>
                {pageItems.length === 0 && (
                  <tr><td colSpan={8} className="text-center py-8 text-gray-400 dark:text-gray-500">Tidak ada data</td></tr>
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
                    <td className="px-3 py-2 font-mono text-gray-400 dark:text-gray-500 text-[11px]">{f.code}</td>
                    <td className="px-3 py-2 text-gray-800 dark:text-gray-200 max-w-xs leading-snug">
                      {f.name}
                      {f.has_nutrition_override && (
                        <span title="Nutrition overridden" className="ml-1 text-[9px] text-amber-600 dark:text-amber-400">●</span>
                      )}
                    </td>
                    <td className="px-3 py-2">
                      <span className={`text-[10px] px-1.5 py-0.5 rounded font-semibold ${CAT_COLORS[f.category] || CAT_COLORS.other}`}>
                        {CAT_LABELS[f.category] || f.category}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums text-gray-600 dark:text-gray-400">
                      <NutritionCell food={f} field="energy" onSaved={load} />
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums text-gray-600 dark:text-gray-400">
                      <NutritionCell food={f} field="protein" onSaved={load} />
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">
                      <PriceCell food={f} onSaved={load} />
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
              <span className="text-xs text-gray-400 dark:text-gray-500">Hal {page} / {totalPages} · {filtered.length} bahan</span>
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
        {label}{unit && <span className="text-gray-400 dark:text-gray-500 ml-1">({unit})</span>}
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
function GroupResult({ group, numDays, onSubstitute }) {
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
          <span className="ml-2 text-xs text-gray-400 dark:text-gray-500">{group.num_students} siswa</span>
        </div>
        <div className="flex gap-3 flex-wrap">
          {[
            { label: 'Per Siswa / Hari',      value: rp(feasible.length ? group.weekly_per_student / feasible.length : 0) },
            { label: `Total ${numDays} Hari`, value: rp(group.weekly_total) },
            { label: 'Rata Energi',           value: (group.avg_nutrition?.energy || 0) + ' kkal' },
          ].map((s) => (
            <div key={s.label} className="text-center">
              <div className="text-[10px] text-gray-400 dark:text-gray-500 uppercase tracking-wide">{s.label}</div>
              <div className="text-sm font-bold text-brand dark:text-accent">{s.value}</div>
            </div>
          ))}
        </div>
        <span className="text-gray-400 dark:text-gray-500 text-xs ml-2">{open ? '▲' : '▼'}</span>
      </button>

      {/* Collapsible content */}
      {open && (
        <div className="px-4 pb-4 border-t border-gray-100 dark:border-gray-700 pt-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
            {group.week.map((day) => (
              <DayCard
                key={day.day}
                day={day}
                constraints={c}
                onSubstitute={onSubstitute ? (dayNum, oldItem, sub, idx) => onSubstitute(group.label, dayNum, oldItem, sub, idx) : undefined}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Save menu modal ───────────────────────────────────────────────────────────
function SaveMenuModal({ onSave, onClose, saving }) {
  const [name, setName] = useState('')
  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center" onClick={onClose}>
      <div
        onClick={(e) => e.stopPropagation()}
        className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-sm p-5"
        data-testid="save-menu-modal"
      >
        <h3 className="font-semibold text-gray-900 dark:text-white mb-3">Simpan Menu</h3>
        <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Nama menu</label>
        <input
          autoFocus
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && name.trim()) onSave(name.trim()) }}
          placeholder="Contoh: Menu Minggu 1 April"
          data-testid="save-menu-name-input"
          className="w-full rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent mb-4"
        />
        <div className="flex justify-end gap-2">
          <button onClick={onClose} className="px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 rounded text-sm">
            Batal
          </button>
          <button
            onClick={() => name.trim() && onSave(name.trim())}
            disabled={!name.trim() || saving}
            data-testid="save-menu-confirm"
            className="px-5 py-2 bg-brand hover:opacity-90 text-white rounded font-semibold text-sm disabled:opacity-40"
          >
            {saving ? 'Menyimpan…' : 'Simpan'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function MenuPlanner() {
  const location = useLocation()
  const { hasPermission } = useAuth()
  const canSaveMenu = hasPermission('menu.save')

  const [numDays, setNumDays]         = useState(5)
  const [budget, setBudget]           = useState(0)
  const [budgetMin, setBudgetMin]     = useState(0)
  const [priceMin, setPriceMin]       = useState(0)
  const [priceMax, setPriceMax]       = useState(0)
  const [excludedFoods, setExcludedFoods] = useState(new Set())
  const [result, setResult]           = useState(null)
  const [lastPayload, setLastPayload] = useState(null)
  const [loading, setLoading]         = useState(false)
  const [error, setError]             = useState(null)
  const [priceCount, setPriceCount]   = useState(0)
  const [akgPresets, setAkgPresets]   = useState({})
  const [showSaveModal, setShowSaveModal] = useState(false)
  const [saving, setSaving]           = useState(false)
  const [saveMsg, setSaveMsg]         = useState(null)

  // Saved-menus library (was previously a separate page)
  const [showLibrary, setShowLibrary] = useState(false)
  const [libraryMenus, setLibraryMenus] = useState([])
  const [libraryLoading, setLibraryLoading] = useState(false)
  const [libraryError, setLibraryError] = useState('')
  const [libraryLoadingId, setLibraryLoadingId] = useState(null)
  const [libraryDeletingId, setLibraryDeletingId] = useState(null)
  const [libraryConfirmId, setLibraryConfirmId] = useState(null)

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

  // Load saved menu payload into the planner state (used by router-state restore
  // and by the inline library modal).
  const applyLoadedPayload = (loaded) => {
    const req = loaded?.payload?.request
    if (!req) return
    if (req.num_days) setNumDays(req.num_days)
    if (req.budget_min) setBudgetMin(req.budget_min)
    const maxCost = req.groups?.find?.((g) => g?.constraints?.max_cost)?.constraints?.max_cost
    if (maxCost) setBudget(maxCost)
    if (req.price_min) setPriceMin(req.price_min)
    if (req.price_max) setPriceMax(req.price_max)
    if (req.excluded_foods) setExcludedFoods(new Set(req.excluded_foods))
    if (req.groups) {
      setGroups(req.groups.map((g) => ({
        label: g.label,
        num_students: g.num_students,
        constraints: g.constraints || { ...DEFAULT_CONSTRAINTS },
        showAkg: false,
      })))
    }
  }

  useEffect(() => {
    if (location.state?.loadPayload) applyLoadedPayload(location.state.loadPayload)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.state])

  const openLibrary = async () => {
    setShowLibrary(true)
    setLibraryError('')
    setLibraryLoading(true)
    try {
      const r = await listSavedMenus()
      setLibraryMenus(r.data.menus || [])
    } catch (e) {
      setLibraryError(e.response?.data?.detail || e.message)
    } finally {
      setLibraryLoading(false)
    }
  }

  const handleLibraryLoad = async (id) => {
    setLibraryLoadingId(id)
    try {
      const r = await getSavedMenu(id)
      applyLoadedPayload(r.data)
      setShowLibrary(false)
    } catch (e) {
      setLibraryError(e.response?.data?.detail || e.message)
    } finally {
      setLibraryLoadingId(null)
    }
  }

  const handleLibraryDelete = async (id) => {
    setLibraryDeletingId(id)
    try {
      await deleteSavedMenu(id)
      setLibraryMenus((prev) => prev.filter((m) => m.id !== id))
    } catch (e) {
      setLibraryError(e.response?.data?.detail || e.message)
    } finally {
      setLibraryDeletingId(null)
      setLibraryConfirmId(null)
    }
  }

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
    setSaveMsg(null)
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
    setLastPayload(payload)
    optimizeMenu(payload)
      .then((res) => setResult(res.data))
      .catch((err) => {
        const detail = err.response?.data?.detail
        setError(typeof detail === 'string' ? detail : 'Gagal mengoptimasi menu.')
      })
      .finally(() => setLoading(false))
  }

  const handleSaveMenu = async (name) => {
    setSaving(true)
    try {
      await saveMenu({ name, payload: { request: lastPayload, result } })
      setShowSaveModal(false)
      setSaveMsg(`Menu "${name}" berhasil disimpan.`)
    } catch (e) {
      setSaveMsg(e.response?.data?.detail || 'Gagal menyimpan menu.')
    } finally {
      setSaving(false)
    }
  }

  const handleSubstitute = (groupLabel, dayNum, oldItem, sub, idx) => {
    if (!result?.groups) return
    setResult((prev) => ({
      ...prev,
      groups: prev.groups.map((g) => {
        if (g.label !== groupLabel) return g
        return {
          ...g,
          week: g.week.map((day) => {
            if (day.day !== dayNum) return day
            const newItems = day.items.slice()
            if (typeof idx === 'number' && idx >= 0 && idx < newItems.length) {
              const it = newItems[idx]
              newItems[idx] = {
                ...it,
                code: sub.code,
                name: sub.name,
                category: sub.category,
                nutrition: sub.nutrition,
              }
            }
            return { ...day, items: newItems }
          }),
        }
      }),
    }))
  }

  const disabled = priceCount === 0
  const totalStudents = groups.reduce((s, g) => s + g.num_students, 0)

  return (
    <div>
      <div className="flex items-start justify-between mb-1">
        <h2 className="text-xl font-bold text-gray-800 dark:text-gray-100">Menu Planner</h2>
        {canSaveMenu && (
          <button
            onClick={openLibrary}
            className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-200 rounded hover:bg-gray-100 dark:hover:bg-gray-700"
          >
            📁 Buka Tersimpan
          </button>
        )}
      </div>
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
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-4">
            {[
              { label: 'Total Siswa',           value: result.total_students + ' siswa' },
              { label: `Grand Total ${numDays} Hari`, value: rp(result.grand_total) },
              { label: 'Per Siswa / Hari (avg)', value: rp(result.grand_total / result.total_students / numDays) },
            ].map((s) => (
              <div key={s.label} className={`${CARD} p-4 text-center`}>
                <div className="text-[11px] text-gray-400 dark:text-gray-500 uppercase tracking-wide mb-1">{s.label}</div>
                <div className="text-base font-bold text-brand dark:text-accent">{s.value}</div>
              </div>
            ))}
          </div>

          {canSaveMenu && (
            <div className="flex items-center gap-3 mb-6">
              <button
                data-testid="save-menu-btn"
                onClick={() => setShowSaveModal(true)}
                className={BTN_SECONDARY}
              >
                💾 Simpan Menu
              </button>
              {saveMsg && (
                <span className={`text-xs ${saveMsg.includes('berhasil') ? 'text-green-600 dark:text-green-400' : 'text-red-500 dark:text-red-400'}`}>
                  {saveMsg}
                </span>
              )}
            </div>
          )}

          {result.groups.map((g) => (
            <GroupResult key={g.label} group={g} numDays={numDays} onSubstitute={handleSubstitute} />
          ))}
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

      {showSaveModal && (
        <SaveMenuModal
          onSave={handleSaveMenu}
          onClose={() => setShowSaveModal(false)}
          saving={saving}
        />
      )}

      {showLibrary && (
        <SavedMenusLibraryModal
          menus={libraryMenus}
          loading={libraryLoading}
          error={libraryError}
          loadingId={libraryLoadingId}
          deletingId={libraryDeletingId}
          confirmId={libraryConfirmId}
          onSelectConfirm={setLibraryConfirmId}
          onClose={() => setShowLibrary(false)}
          onLoad={handleLibraryLoad}
          onDelete={handleLibraryDelete}
          onRefresh={openLibrary}
        />
      )}
    </div>
  )
}

function SavedMenusLibraryModal({
  menus, loading, error, loadingId, deletingId, confirmId,
  onSelectConfirm, onClose, onLoad, onDelete, onRefresh,
}) {
  const fmt = (iso) => {
    if (!iso) return '—'
    try {
      return new Date(iso).toLocaleString('id-ID', {
        day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
      })
    } catch { return iso.slice(0, 16).replace('T', ' ') }
  }
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 w-full max-w-3xl mx-4 max-h-[80vh] overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-5 py-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
          <div>
            <h3 className="font-semibold text-gray-900 dark:text-white">Menu Tersimpan</h3>
            <p className="text-xs text-gray-500 dark:text-gray-400">Klik "Muat" untuk membuka di optimizer ini.</p>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={onRefresh} disabled={loading} className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50">
              {loading ? 'Memuat…' : '↻'}
            </button>
            <button onClick={onClose} className="px-3 py-1.5 text-sm text-gray-500 hover:text-gray-700 dark:hover:text-gray-200">✕</button>
          </div>
        </div>
        {error && (
          <div className="px-5 py-2 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 text-sm">{error}</div>
        )}
        <div className="overflow-y-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 dark:bg-gray-700/50 text-left text-xs uppercase text-gray-500 dark:text-gray-400 sticky top-0">
              <tr>
                <th className="px-4 py-2.5">Nama Menu</th>
                <th className="px-4 py-2.5">Dibuat Oleh</th>
                <th className="px-4 py-2.5">Tanggal</th>
                <th className="px-4 py-2.5 text-center">Aksi</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
              {loading ? (
                <tr><td colSpan={4} className="px-4 py-8 text-center text-gray-500 dark:text-gray-400">Memuat…</td></tr>
              ) : menus.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-4 py-10 text-center text-gray-400 dark:text-gray-500">
                    <div className="text-2xl mb-2">📭</div>
                    <div>Belum ada menu tersimpan.</div>
                    <div className="text-xs mt-1">Optimasi menu, lalu klik "Simpan Menu".</div>
                  </td>
                </tr>
              ) : menus.map((m) => (
                <tr key={m.id} data-testid={`saved-menu-row-${m.id}`} className="text-gray-900 dark:text-gray-100 hover:bg-gray-50 dark:hover:bg-gray-700/30">
                  <td className="px-4 py-3 font-medium">{m.name}</td>
                  <td className="px-4 py-3 text-gray-500 dark:text-gray-400">{m.created_by_username}</td>
                  <td className="px-4 py-3 text-gray-500 dark:text-gray-400 tabular-nums text-xs">{fmt(m.created_at)}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2 justify-center">
                      <button
                        data-testid={`load-menu-${m.id}`}
                        onClick={() => onLoad(m.id)}
                        disabled={loadingId === m.id}
                        className="px-4 py-1.5 bg-brand hover:opacity-90 text-white rounded text-sm font-medium disabled:opacity-40 transition-opacity"
                      >
                        {loadingId === m.id ? 'Memuat…' : 'Muat'}
                      </button>
                      {confirmId === m.id ? (
                        <div className="flex items-center gap-1">
                          <span className="text-xs text-gray-500 dark:text-gray-400">Yakin hapus?</span>
                          <button
                            data-testid={`confirm-delete-${m.id}`}
                            onClick={() => onDelete(m.id)}
                            disabled={deletingId === m.id}
                            className="px-3 py-1.5 text-sm text-red-600 dark:text-red-400 border border-red-200 dark:border-red-800 rounded hover:bg-red-50 dark:hover:bg-red-900/20 disabled:opacity-40"
                          >
                            {deletingId === m.id ? 'Menghapus…' : 'Ya, Hapus'}
                          </button>
                          <button onClick={() => onSelectConfirm(null)} className="text-xs text-gray-500 hover:underline">Batal</button>
                        </div>
                      ) : (
                        <button
                          data-testid={`delete-menu-${m.id}`}
                          onClick={() => onSelectConfirm(m.id)}
                          className="px-3 py-1.5 text-sm text-red-600 dark:text-red-400 border border-red-200 dark:border-red-800 rounded hover:bg-red-50 dark:hover:bg-red-900/20"
                        >
                          Hapus
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}


// ── Manual price override cell (accountant/admin only) ───────────────────────
function PriceCell({ food, onSaved }) {
  const { hasPermission } = useAuth()
  const canEdit = hasPermission('prices.override')
  const [editing, setEditing] = useState(false)
  const [val, setVal] = useState('')
  const [busy, setBusy] = useState(false)

  if (!canEdit) {
    return food.has_price
      ? <span className="text-accent font-semibold">{rp(food.price)}</span>
      : <span className="text-gray-300 dark:text-gray-600">—</span>
  }

  const display = food.has_price
    ? <span className="text-accent font-semibold">{rp(food.price)}</span>
    : <span className="text-gray-400 dark:text-gray-500">—</span>

  const save = async () => {
    setBusy(true)
    try {
      const num = val === '' ? null : Math.round(Number(val))
      if (num !== null && (Number.isNaN(num) || num < 0)) {
        alert('Harga harus angka >= 0')
        return
      }
      await overridePrice(food.code, {
        price: num,
        manual_source: 'manual override',
        food_name: food.name,
      })
      setEditing(false)
      onSaved && onSaved()
    } catch (e) {
      alert(e.response?.data?.detail || e.message)
    } finally {
      setBusy(false)
    }
  }

  if (!editing) {
    return (
      <span className="inline-flex items-center gap-1.5 justify-end">
        {display}
        {hasPermission('prices.history') && (
          <PriceHistoryButton foodCode={food.code} foodName={food.name} />
        )}
        <button onClick={() => { setVal(food.has_price ? String(food.price) : ''); setEditing(true) }}
          className="text-[10px] text-brand hover:underline opacity-60 hover:opacity-100" title="Override harga (accountant/admin)">
          edit
        </button>
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 justify-end">
      <input
        type="number" min="0" step="100" autoFocus
        value={val} onChange={e => setVal(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter') save(); if (e.key === 'Escape') setEditing(false) }}
        className="w-20 px-1 py-0.5 text-right text-xs bg-white dark:bg-gray-700 border border-brand rounded text-gray-900 dark:text-white"
        placeholder="kosong=clear"
      />
      <button onClick={save} disabled={busy} className="text-[10px] text-green-600 hover:underline disabled:opacity-50">save</button>
      <button onClick={() => setEditing(false)} className="text-[10px] text-gray-500 hover:underline">x</button>
    </span>
  )
}


// ── Nutrition edit cell (ahli_gizi / admin) ──────────────────────────────────
function NutritionCell({ food, field, onSaved }) {
  const { hasPermission } = useAuth()
  const canEdit = hasPermission('foods.edit')
  const [editing, setEditing] = useState(false)
  const [val, setVal] = useState('')
  const current = field === 'protein' ? food.protein.toFixed(1) : food.energy.toFixed(0)
  if (!canEdit) return <span>{current}</span>

  const save = async () => {
    const num = Number(val)
    if (val === '' || Number.isNaN(num) || num < 0) {
      alert('Angka >= 0')
      return
    }
    try {
      await setNutritionOverride(food.code, { [field]: num })
      setEditing(false)
      onSaved && onSaved()
    } catch (e) {
      alert(e.response?.data?.detail || e.message)
    }
  }

  if (!editing) return (
    <span className="inline-flex items-center gap-1 justify-end">
      <span>{current}</span>
      <button onClick={() => { setVal(String(current)); setEditing(true) }}
        className="text-[9px] text-brand opacity-50 hover:opacity-100 hover:underline"
        title={`Override ${field} (ahli_gizi/admin)`}>
        ✎
      </button>
    </span>
  )
  return (
    <span className="inline-flex items-center gap-1 justify-end">
      <input
        type="number" step="0.1" autoFocus
        value={val} onChange={e => setVal(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter') save(); if (e.key === 'Escape') setEditing(false) }}
        className="w-14 px-1 py-0.5 text-right text-xs bg-white dark:bg-gray-700 border border-brand rounded text-gray-900 dark:text-white"
      />
      <button onClick={save} className="text-[10px] text-green-600 hover:underline">ok</button>
      <button onClick={() => setEditing(false)} className="text-[10px] text-gray-500 hover:underline">x</button>
    </span>
  )
}


// ── Price history popover (accountant / admin) ───────────────────────────────
function PriceHistoryButton({ foodCode, foodName }) {
  const [open, setOpen] = useState(false)
  const [rows, setRows] = useState(null)
  const [loading, setLoading] = useState(false)

  const openDrawer = async () => {
    setOpen(true); setLoading(true)
    try {
      const r = await getPriceHistory(foodCode)
      setRows(r.data.history || [])
    } catch {
      setRows([])
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <button onClick={openDrawer}
        className="text-[10px] text-gray-400 hover:text-brand opacity-60 hover:opacity-100"
        title="Lihat riwayat harga">
        hist
      </button>
      {open && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center" onClick={() => setOpen(false)}>
          <div onClick={e => e.stopPropagation()}
            className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-md max-h-[80vh] overflow-y-auto p-4">
            <div className="flex items-start justify-between mb-3">
              <div>
                <h3 className="font-semibold text-gray-900 dark:text-white">Riwayat Harga</h3>
                <p className="text-xs text-gray-500 dark:text-gray-400">{foodCode} — {foodName}</p>
              </div>
              <button onClick={() => setOpen(false)} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200">×</button>
            </div>
            {loading && <div className="text-sm text-gray-500 dark:text-gray-400 py-8 text-center">Memuat…</div>}
            {!loading && (rows?.length === 0
              ? <div className="text-sm text-gray-500 dark:text-gray-400 py-8 text-center">Belum ada perubahan harga yang tercatat.</div>
              : <table className="w-full text-xs">
                  <thead>
                    <tr className="text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
                      <th className="py-1.5 text-left">Waktu</th>
                      <th className="py-1.5 text-left">Source</th>
                      <th className="py-1.5 text-right">Harga</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows?.map((r, i) => (
                      <tr key={i} className="border-b border-gray-100 dark:border-gray-700/50">
                        <td className="py-1.5 text-gray-700 dark:text-gray-300">
                          {r.changed_at ? r.changed_at.slice(0, 19).replace('T', ' ') : '—'}
                        </td>
                        <td className="py-1.5">
                          <span className={`px-1.5 py-0.5 text-[10px] rounded ${
                            r.source === 'manual' ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400'
                            : r.source === 'manual_clear' ? 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300'
                            : 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
                          }`}>
                            {r.source || '—'}
                          </span>
                        </td>
                        <td className="py-1.5 text-right tabular-nums font-semibold text-gray-800 dark:text-gray-100">
                          {r.price !== null && r.price !== undefined ? `Rp${r.price.toLocaleString('id-ID')}` : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
            )}
          </div>
        </div>
      )}
    </>
  )
}
