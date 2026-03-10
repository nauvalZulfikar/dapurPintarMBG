import { useState, useEffect } from 'react'
import { optimizeMenu, getPriceStatus, triggerScrape } from '../api/menu'

// ── Shared styles ────────────────────────────────────────────────────────────
const CARD = 'bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700'
const INPUT = 'rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent'
const BTN_PRIMARY = 'px-5 py-2 bg-brand hover:opacity-90 text-white rounded-lg font-semibold text-sm disabled:opacity-40 transition-opacity'
const BTN_SECONDARY = 'px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 rounded-lg text-sm disabled:opacity-40 transition-colors'

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
        <div
          className={`h-full rounded-full ${ok ? 'bg-accent' : 'bg-red-400'}`}
          style={{ width: `${pct}%` }}
        />
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
        <div className="flex-1 flex items-center justify-center p-6 text-gray-400 text-sm">
          Tidak ada solusi optimal
        </div>
      </div>
    )
  }

  // Group items by category in display order
  const grouped = {}
  CAT_ORDER.forEach((cat) => {
    const items = day.items.filter((it) => it.category === cat)
    if (items.length) grouped[cat] = items
  })

  return (
    <div className={`${CARD} flex flex-col`}>
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
        <span className="font-bold text-sm text-gray-800 dark:text-gray-100">{day.label}</span>
        <span className="text-xs font-semibold text-accent">{rp(day.cost_per_serving)}/porsi</span>
      </div>

      {/* Food items grouped by category */}
      <div className="flex-1 p-3 space-y-3">
        {CAT_ORDER.filter((cat) => grouped[cat]).map((cat) => (
          <div key={cat}>
            <div className={`text-[10px] px-1.5 py-0.5 rounded font-semibold inline-block mb-1 ${CAT_COLORS[cat]}`}>
              {CAT_LABELS[cat]}
            </div>
            {grouped[cat].map((item, i) => (
              <div key={i} className="flex items-baseline justify-between gap-1 text-sm py-0.5">
                <span className="text-gray-700 dark:text-gray-300 leading-tight">{item.name}</span>
                <span className="text-xs text-gray-400 whitespace-nowrap shrink-0">{Math.round(item.grams)}g</span>
              </div>
            ))}
          </div>
        ))}
      </div>

      {/* Nutrition bars */}
      <div className="px-3 pb-3 pt-2 border-t border-gray-100 dark:border-gray-700 space-y-1.5">
        <NutrBar label="Energi"  value={day.nutrition.energy}  target={c.min_energy  || 600} unit=" kkal" />
        <NutrBar label="Protein" value={day.nutrition.protein} target={c.min_protein || 15}  unit="g"     />
        <NutrBar label="Lemak"   value={day.nutrition.fat}     target={c.max_fat     || 25}  unit="g"  isMax />
        <NutrBar label="Karbo"   value={day.nutrition.carbs}   target={c.min_carbs   || 80}  unit="g"     />
        <NutrBar label="Serat"   value={day.nutrition.fiber}   target={c.min_fiber   || 4}   unit="g"     />
      </div>
    </div>
  )
}

// ── Price scrape status banner ────────────────────────────────────────────────
function PriceStatusBanner({ onScrape }) {
  const [status, setStatus]   = useState(null)
  const [loading, setLoading] = useState(true)
  const [scraping, setScraping] = useState(false)
  const [msg, setMsg]         = useState(null)

  useEffect(() => {
    getPriceStatus()
      .then((r) => setStatus(r.data))
      .catch(() => setStatus(null))
      .finally(() => setLoading(false))
  }, [])

  const handleScrape = (maxItems) => {
    setScraping(true)
    setMsg(null)
    triggerScrape(maxItems)
      .then((r) => setMsg(r.data.message))
      .catch((e) => setMsg(e.response?.data?.detail || 'Gagal memulai scrape.'))
      .finally(() => setScraping(false))
  }

  if (loading) return null

  const count = status?.count || 0

  if (count === 0) {
    return (
      <div className={`${CARD} p-4 mb-6 border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-900/20`}>
        <div className="flex flex-wrap items-start gap-4">
          <div className="flex-1 min-w-0">
            <div className="font-semibold text-amber-800 dark:text-amber-300 text-sm mb-1">
              ⚠ Harga bahan makanan belum tersedia
            </div>
            <p className="text-xs text-amber-700 dark:text-amber-400">
              Menu optimizer butuh data harga dari Sayurbox. Klik "Scrape 50 Item" untuk test,
              atau "Scrape Semua" untuk data lengkap (~3-4 jam, berjalan di background).
            </p>
            {msg && <p className="text-xs mt-2 text-green-700 dark:text-green-400">{msg}</p>}
          </div>
          <div className="flex gap-2 shrink-0">
            <button onClick={() => handleScrape(50)} disabled={scraping} className={BTN_SECONDARY}>
              {scraping ? 'Memulai...' : 'Scrape 50 Item'}
            </button>
            <button onClick={() => handleScrape(0)} disabled={scraping} className={BTN_PRIMARY}>
              {scraping ? 'Memulai...' : 'Scrape Semua'}
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className={`${CARD} p-3 mb-6`}>
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="text-sm text-gray-600 dark:text-gray-400">
          ✓ <span className="font-semibold text-gray-800 dark:text-gray-200">{count} bahan</span> sudah ada harga pasar
          {status?.prices?.[0]?.scraped_at && (
            <span className="ml-2 text-xs text-gray-400">
              · diperbarui {new Date(status.prices[0].scraped_at).toLocaleDateString('id-ID')}
            </span>
          )}
        </div>
        <div className="flex gap-2">
          {msg && <span className="text-xs text-green-600 dark:text-green-400 self-center">{msg}</span>}
          <button onClick={() => handleScrape(0)} disabled={scraping} className={BTN_SECONDARY} title="Perbarui semua harga">
            {scraping ? 'Memulai...' : '↻ Perbarui Harga'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function MenuPlanner() {
  const [numDays, setNumDays]         = useState(5)
  const [numStudents, setNumStudents] = useState(100)
  const [result, setResult]           = useState(null)
  const [loading, setLoading]         = useState(false)
  const [error, setError]             = useState(null)

  const handleOptimize = () => {
    setLoading(true)
    setError(null)
    optimizeMenu({ num_days: numDays, num_students: numStudents })
      .then((res) => setResult(res.data))
      .catch((err) => {
        const detail = err.response?.data?.detail
        setError(typeof detail === 'string' ? detail : 'Gagal mengoptimasi menu. Pastikan data harga sudah di-scrape.')
      })
      .finally(() => setLoading(false))
  }

  const c = result?.constraints_used || {}
  const feasibleDays = result?.week.filter((d) => d.feasible) || []

  return (
    <div>
      <h2 className="text-xl font-bold text-gray-800 dark:text-gray-100 mb-1">Menu Planner</h2>
      <p className="text-sm text-gray-500 dark:text-gray-400 mb-6">
        Optimasi menu makan siang MBG — minimasi biaya, penuhi AKG anak SD.
      </p>

      {/* Price status */}
      <PriceStatusBanner />

      {/* Controls */}
      <div className={`${CARD} p-4 mb-6`}>
        <div className="flex flex-wrap items-end gap-4">
          <div>
            <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Jumlah Hari</label>
            <input
              type="number" min={1} max={7} value={numDays}
              onChange={(e) => setNumDays(Math.max(1, Math.min(7, +e.target.value || 5)))}
              className={INPUT} style={{ width: 80 }}
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Jumlah Siswa</label>
            <input
              type="number" min={1} value={numStudents}
              onChange={(e) => setNumStudents(Math.max(1, +e.target.value || 100))}
              className={INPUT} style={{ width: 120 }}
            />
          </div>
          <button onClick={handleOptimize} disabled={loading} className={BTN_PRIMARY}>
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

      {error && (
        <div className="bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-xl p-4 mb-6 text-red-700 dark:text-red-300 text-sm">
          {error}
        </div>
      )}

      {result && (
        <>
          {/* Summary cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
            {[
              { label: 'Per Siswa / Hari',   value: rp(feasibleDays.length ? result.weekly_per_student / feasibleDays.length : 0) },
              { label: 'Per Siswa / Minggu', value: rp(result.weekly_per_student) },
              { label: 'Total ' + numDays + ' Hari', value: rp(result.weekly_total) },
              { label: 'Rata-rata Energi',   value: (result.avg_nutrition?.energy || 0) + ' kkal' },
            ].map((s) => (
              <div key={s.label} className={`${CARD} p-4 text-center`}>
                <div className="text-[11px] text-gray-400 uppercase tracking-wide mb-1">{s.label}</div>
                <div className="text-base font-bold text-brand dark:text-accent">{s.value}</div>
              </div>
            ))}
          </div>

          {/* AKG targets reference */}
          <div className={`${CARD} p-3 mb-6`}>
            <div className="text-xs font-semibold text-gray-500 dark:text-gray-400 mb-2 uppercase tracking-wide">
              Target AKG Makan Siang (SD 7-12 tahun)
            </div>
            <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-gray-600 dark:text-gray-400">
              <span>Energi ≥ {c.min_energy || 600} kkal</span>
              <span>Protein ≥ {c.min_protein || 15}g</span>
              <span>Lemak ≤ {c.max_fat || 25}g</span>
              <span>Karbo ≥ {c.min_carbs || 80}g</span>
              <span>Serat ≥ {c.min_fiber || 4}g</span>
              <span>Besi ≥ {c.min_iron || 3}mg</span>
              <span>Vit C ≥ {c.min_vitc || 15}mg</span>
            </div>
          </div>

          {/* Weekly grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4 mb-6">
            {result.week.map((day) => (
              <DayCard key={day.day} day={day} constraints={c} />
            ))}
          </div>

          {/* Avg nutrition summary */}
          {result.avg_nutrition && (
            <div className={`${CARD} p-4`}>
              <div className="text-xs font-semibold text-gray-500 dark:text-gray-400 mb-3 uppercase tracking-wide">
                Rata-rata Gizi per Hari ({feasibleDays.length} hari optimal)
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                {[
                  { label: 'Energi',  val: result.avg_nutrition.energy,  unit: 'kkal', target: c.min_energy  || 600 },
                  { label: 'Protein', val: result.avg_nutrition.protein, unit: 'g',    target: c.min_protein || 15  },
                  { label: 'Karbo',   val: result.avg_nutrition.carbs,   unit: 'g',    target: c.min_carbs   || 80  },
                  { label: 'Serat',   val: result.avg_nutrition.fiber,   unit: 'g',    target: c.min_fiber   || 4   },
                ].map((n) => (
                  <div key={n.label} className="text-center">
                    <div className="text-2xl font-bold text-gray-800 dark:text-gray-100">
                      {Number(n.val).toFixed(1)}
                      <span className="text-sm font-normal text-gray-400 ml-1">{n.unit}</span>
                    </div>
                    <div className="text-xs text-gray-400">{n.label}</div>
                    <div className={`text-xs mt-0.5 font-medium ${n.val >= n.target ? 'text-accent' : 'text-red-500'}`}>
                      {n.val >= n.target ? '✓ Terpenuhi' : `↑ Kurang ${(n.target - n.val).toFixed(1)}${n.unit}`}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {!result && !loading && (
        <div className={`${CARD} p-12 text-center text-gray-400 dark:text-gray-500`}>
          <div className="text-4xl mb-3">🍽</div>
          <div className="text-sm">Klik "Optimasi Menu" untuk membuat rencana makan mingguan</div>
          <div className="text-xs mt-1">LP akan memilih bahan dari TKPI 2020 yang memenuhi AKG dengan biaya minimum</div>
        </div>
      )}
    </div>
  )
}
