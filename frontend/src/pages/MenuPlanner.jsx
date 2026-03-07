import { useState } from 'react'
import { optimizeMenu } from '../api/menu'

const CARD = 'bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700'
const INPUT = 'w-full rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent'

const CAT_LABELS = {
  staple: 'Makanan Pokok',
  animal: 'Lauk Hewani',
  plant: 'Lauk Nabati',
  vegetable: 'Sayuran',
  fruit: 'Buah',
  other: 'Lainnya',
}

const CAT_COLORS = {
  staple: 'bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-200',
  animal: 'bg-red-100 dark:bg-red-900/40 text-red-800 dark:text-red-200',
  plant: 'bg-green-100 dark:bg-green-900/40 text-green-800 dark:text-green-200',
  vegetable: 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-800 dark:text-emerald-200',
  fruit: 'bg-orange-100 dark:bg-orange-900/40 text-orange-800 dark:text-orange-200',
  other: 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300',
}

function formatRp(n) {
  return 'Rp' + Math.round(n).toLocaleString('id-ID')
}

function NutritionBar({ label, value, target, unit, max }) {
  const pct = Math.min(100, (value / (max || target)) * 100)
  const met = max ? value <= target : value >= target
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-16 text-gray-500 dark:text-gray-400 shrink-0">{label}</span>
      <div className="flex-1 h-2 bg-gray-200 dark:bg-gray-600 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${met ? 'bg-accent' : 'bg-red-400'}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={`w-20 text-right tabular-nums ${met ? 'text-gray-600 dark:text-gray-300' : 'text-red-500'}`}>
        {Math.round(value * 10) / 10}{unit}
      </span>
    </div>
  )
}

export default function MenuPlanner() {
  const [numDays, setNumDays] = useState(5)
  const [numStudents, setNumStudents] = useState(100)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleOptimize = () => {
    setLoading(true)
    setError(null)
    optimizeMenu({ num_days: numDays, num_students: numStudents })
      .then((res) => setResult(res.data))
      .catch((err) => setError(err.response?.data?.detail || 'Gagal mengoptimasi menu.'))
      .finally(() => setLoading(false))
  }

  const constraints = result?.constraints_used || {}

  return (
    <div>
      <h2 className="text-xl font-bold text-gray-800 dark:text-gray-100 mb-4">Menu Planner</h2>

      {/* Controls */}
      <div className={`${CARD} p-4 mb-6`}>
        <div className="flex flex-wrap items-end gap-4">
          <div>
            <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Jumlah Hari</label>
            <input type="number" min={1} max={7} value={numDays} onChange={(e) => setNumDays(+e.target.value || 5)} className={INPUT} style={{ width: 80 }} />
          </div>
          <div>
            <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Jumlah Siswa</label>
            <input type="number" min={1} value={numStudents} onChange={(e) => setNumStudents(+e.target.value || 100)} className={INPUT} style={{ width: 120 }} />
          </div>
          <button
            onClick={handleOptimize}
            disabled={loading}
            className="px-6 py-2 bg-brand hover:bg-brand-mid text-white rounded font-semibold text-sm disabled:opacity-50 transition-colors"
          >
            {loading ? 'Mengoptimasi...' : 'Optimasi Menu'}
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-lg p-3 mb-6 text-red-700 dark:text-red-300 text-sm">
          {error}
        </div>
      )}

      {result && (
        <>
          {/* Summary */}
          <div className={`${CARD} p-4 mb-6`}>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-center">
              <div>
                <div className="text-xs text-gray-500 dark:text-gray-400 uppercase">Per Siswa / Hari</div>
                <div className="text-lg font-bold text-brand dark:text-accent">
                  {formatRp(result.weekly_per_student / numDays)}
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-500 dark:text-gray-400 uppercase">Per Siswa / Minggu</div>
                <div className="text-lg font-bold text-brand dark:text-accent">
                  {formatRp(result.weekly_per_student)}
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-500 dark:text-gray-400 uppercase">Total / Minggu</div>
                <div className="text-lg font-bold text-brand dark:text-accent">
                  {formatRp(result.weekly_total)}
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-500 dark:text-gray-400 uppercase">Rata-rata Energi</div>
                <div className="text-lg font-bold text-brand dark:text-accent">
                  {result.avg_nutrition?.energy || 0} kkal
                </div>
              </div>
            </div>
          </div>

          {/* Weekly grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-5 gap-4 mb-6">
            {result.week.map((day) => (
              <div key={day.day} className={`${CARD} flex flex-col`}>
                {/* Day header */}
                <div className="px-4 py-2 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
                  <span className="font-bold text-sm text-gray-800 dark:text-gray-100">{day.label}</span>
                  {day.feasible && (
                    <span className="text-xs font-semibold text-brand dark:text-accent">
                      {formatRp(day.cost_per_serving)}/porsi
                    </span>
                  )}
                </div>

                {!day.feasible ? (
                  <div className="p-4 text-center text-gray-400 text-sm">Tidak ada solusi optimal</div>
                ) : (
                  <>
                    {/* Food items */}
                    <div className="flex-1 p-3 space-y-2">
                      {day.items.map((item, i) => (
                        <div key={i} className="flex items-start gap-2">
                          <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium shrink-0 ${CAT_COLORS[item.category] || CAT_COLORS.other}`}>
                            {CAT_LABELS[item.category] || item.category}
                          </span>
                          <div className="flex-1 min-w-0">
                            <div className="text-sm text-gray-800 dark:text-gray-200 truncate">{item.name}</div>
                            <div className="text-xs text-gray-400">{item.grams}g &middot; {formatRp(item.cost)}</div>
                          </div>
                        </div>
                      ))}
                    </div>

                    {/* Nutrition bars */}
                    <div className="px-3 pb-3 space-y-1 border-t border-gray-100 dark:border-gray-700 pt-2">
                      <NutritionBar label="Energi" value={day.nutrition.energy} target={constraints.min_energy || 600} unit=" kkal" />
                      <NutritionBar label="Protein" value={day.nutrition.protein} target={constraints.min_protein || 15} unit="g" />
                      <NutritionBar label="Lemak" value={day.nutrition.fat} target={constraints.max_fat || 25} unit="g" max={constraints.max_fat || 25} />
                      <NutritionBar label="Karbo" value={day.nutrition.carbs} target={constraints.min_carbs || 80} unit="g" />
                    </div>
                  </>
                )}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
