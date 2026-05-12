import { useEffect, useState } from 'react'
import { getNutritionDaily, getWeeklyCompliance } from '../api/nutrition'

function todayISO() {
  return new Date().toISOString().slice(0, 10)
}

function weekStartISO(offsetWeeks = 0) {
  const d = new Date()
  const day = d.getDay()
  const offset = day === 0 ? -6 : 1 - day
  d.setDate(d.getDate() + offset + offsetWeeks * 7)
  return d.toISOString().slice(0, 10)
}

const NUTR_COLS = [
  { key: 'energy',  label: 'Energi (kkal)' },
  { key: 'protein', label: 'Protein (g)' },
  { key: 'fat',     label: 'Lemak (g)' },
  { key: 'carbs',   label: 'KH (g)' },
]

const COLOR_CELL = {
  green:   'bg-green-100 dark:bg-green-900/40 text-green-800 dark:text-green-200',
  amber:   'bg-amber-100 dark:bg-amber-900/30 text-amber-800 dark:text-amber-300',
  red:     'bg-red-100   dark:bg-red-900/30   text-red-800   dark:text-red-300',
  no_data: 'bg-gray-100  dark:bg-gray-700     text-gray-400  dark:text-gray-500',
}

const DAY_LABELS = ['Sen', 'Sel', 'Rab', 'Kam', 'Jum', 'Sab', 'Min']

function fmt(v, dec = 1) {
  return v == null ? '—' : Number(v).toFixed(dec)
}
function fmtPct(v) {
  return v == null ? '—' : `${Number(v).toFixed(1)}%`
}


// ── AKG Tracker cell tooltip ──────────────────────────────────────────────────
function DayCell({ day }) {
  const [showTip, setShowTip] = useState(false)
  const colorClass = COLOR_CELL[day.color] || COLOR_CELL.no_data
  const dateLabel = day.date.slice(5) // MM-DD
  return (
    <div className="relative">
      <button
        data-testid={`akg-cell-${day.date}`}
        onClick={() => setShowTip((v) => !v)}
        className={`w-full rounded-lg p-2 text-center cursor-pointer transition-opacity hover:opacity-80 ${colorClass}`}
      >
        <div className="text-[10px] font-semibold">{dateLabel}</div>
        <div className="text-xs font-bold mt-0.5">
          {day.no_data ? 'Tdk ada data' : `${fmtPct(day.pct_met_avg)}`}
        </div>
      </button>
      {showTip && !day.no_data && (
        <div
          className="absolute z-30 top-full mt-1 left-0 w-64 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-xl p-3 text-xs"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex justify-between items-start mb-2">
            <span className="font-semibold text-gray-800 dark:text-gray-100">{day.date}</span>
            <button onClick={() => setShowTip(false)} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 ml-2">×</button>
          </div>
          <div className="space-y-1">
            {NUTR_COLS.map((col) => (
              <div key={col.key} className="flex justify-between">
                <span className="text-gray-500 dark:text-gray-400">{col.label}</span>
                <span className="font-medium tabular-nums text-gray-800 dark:text-gray-100">
                  {fmt(day.totals?.[col.key])}
                </span>
              </div>
            ))}
          </div>
          {(day.schools || []).slice(0, 5).length > 0 && (
            <div className="mt-2 pt-2 border-t border-gray-100 dark:border-gray-700">
              <div className="text-[10px] text-gray-400 dark:text-gray-500 uppercase mb-1">Per Sekolah (5 teratas)</div>
              {(day.schools || []).slice(0, 5).map((s) => (
                <div key={s.school_id} className="flex justify-between">
                  <span className="text-gray-500 dark:text-gray-400 truncate max-w-[120px]" title={s.school_name}>{s.school_name}</span>
                  <span className="font-medium text-gray-700 dark:text-gray-300 tabular-nums">{fmtPct(s.pct_met?.energy)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Laporan Harian tab ────────────────────────────────────────────────────────
function LaporanHarian() {
  const [selectedDate, setSelectedDate] = useState(todayISO())
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [data, setData] = useState(null)

  const load = async (d) => {
    setLoading(true); setError('')
    try {
      const r = await getNutritionDaily(d)
      setData(r.data)
    } catch (e) {
      setError(e.response?.data?.detail || e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load(selectedDate) }, [])

  const onDateChange = (e) => {
    setSelectedDate(e.target.value)
    load(e.target.value)
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <div>
          <label className="text-xs text-gray-500 dark:text-gray-400 mr-2">Tanggal:</label>
          <input
            type="date"
            value={selectedDate}
            onChange={onDateChange}
            data-testid="date-picker-daily"
            className="px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
          />
        </div>
        <button
          onClick={() => load(selectedDate)}
          disabled={loading}
          className="px-3 py-1.5 bg-brand text-white rounded text-sm disabled:opacity-50"
        >
          {loading ? 'Memuat…' : 'Refresh'}
        </button>
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 px-3 py-2 rounded text-sm">{error}</div>
      )}

      {!loading && data?.no_data && (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow px-4 py-10 text-center text-gray-400 dark:text-gray-500 text-sm">
          Tidak ada data — belum ada tray terkirim pada tanggal ini.
        </div>
      )}

      {!data?.no_data && (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 dark:bg-gray-700/50 text-left text-xs uppercase text-gray-500 dark:text-gray-400">
              <tr>
                <th className="px-3 py-2">Sekolah</th>
                <th className="px-3 py-2 text-right">Siswa</th>
                {NUTR_COLS.map((col) => (
                  <th key={col.key} className="px-3 py-2 text-right">{col.label}</th>
                ))}
                {NUTR_COLS.map((col) => (
                  <th key={col.key + '_pct'} className="px-3 py-2 text-right">% AKG {col.label.split(' ')[0]}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
              {loading ? (
                <tr><td colSpan={2 + NUTR_COLS.length * 2} className="px-3 py-6 text-center text-gray-500 dark:text-gray-400">Memuat…</td></tr>
              ) : (data?.schools || []).length === 0 ? (
                <tr><td colSpan={2 + NUTR_COLS.length * 2} className="px-3 py-6 text-center text-gray-500 dark:text-gray-400">Tidak ada data</td></tr>
              ) : (data.schools || []).map((s) => (
                <tr key={s.school_id} className="text-gray-900 dark:text-gray-100">
                  <td className="px-3 py-2 font-medium">{s.school_name}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{s.student_count}</td>
                  {NUTR_COLS.map((col) => (
                    <td key={col.key} className="px-3 py-2 text-right tabular-nums">{fmt(s.nutrition?.[col.key])}</td>
                  ))}
                  {NUTR_COLS.map((col) => {
                    const pct = s.pct_met?.[col.key]
                    const cls = pct == null ? 'text-gray-400' : pct >= 90 ? 'text-green-600 dark:text-green-400' : pct >= 70 ? 'text-amber-600 dark:text-amber-400' : 'text-red-600 dark:text-red-400'
                    return (
                      <td key={col.key + '_pct'} className={`px-3 py-2 text-right tabular-nums text-xs font-semibold ${cls}`}>
                        {fmtPct(pct)}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
            {data?.totals && !data.no_data && (
              <tfoot className="bg-gray-50 dark:bg-gray-700/50 font-semibold text-gray-900 dark:text-gray-100 border-t border-gray-200 dark:border-gray-600">
                <tr>
                  <td className="px-3 py-2">TOTAL</td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {(data.schools || []).reduce((s, r) => s + (r.student_count || 0), 0)}
                  </td>
                  {NUTR_COLS.map((col) => (
                    <td key={col.key} className="px-3 py-2 text-right tabular-nums">{fmt(data.totals?.[col.key])}</td>
                  ))}
                  {NUTR_COLS.map((col) => {
                    const pct = data.totals_pct_met?.[col.key]
                    const cls = pct == null ? 'text-gray-400' : pct >= 90 ? 'text-green-600 dark:text-green-400' : pct >= 70 ? 'text-amber-600 dark:text-amber-400' : 'text-red-600 dark:text-red-400'
                    return (
                      <td key={col.key + '_pct'} className={`px-3 py-2 text-right tabular-nums text-xs font-semibold ${cls}`}>
                        {fmtPct(pct)}
                      </td>
                    )
                  })}
                </tr>
              </tfoot>
            )}
          </table>
        </div>
      )}
    </div>
  )
}

// ── AKG Tracker tab ───────────────────────────────────────────────────────────
function AkgTracker() {
  const [weekOffset, setWeekOffset] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [data, setData] = useState(null)

  const load = async (ws) => {
    setLoading(true); setError('')
    try {
      const r = await getWeeklyCompliance(ws)
      setData(r.data)
    } catch (e) {
      setError(e.response?.data?.detail || e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load(weekStartISO(0)) }, [])

  const navigate = (delta) => {
    const newOffset = weekOffset + delta
    setWeekOffset(newOffset)
    load(weekStartISO(newOffset))
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate(-1)}
          data-testid="prev-week"
          className="px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700"
        >
          ← Minggu lalu
        </button>
        <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
          {data ? `${data.week_start} – ${data.week_end}` : '…'}
        </span>
        <button
          onClick={() => navigate(+1)}
          disabled={weekOffset >= 0}
          data-testid="next-week"
          className="px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-40"
        >
          Minggu depan →
        </button>
        {weekOffset < 0 && (
          <button
            onClick={() => { setWeekOffset(0); load(weekStartISO(0)) }}
            className="text-xs text-brand hover:underline"
          >
            Kembali ke minggu ini
          </button>
        )}
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 px-3 py-2 rounded text-sm">{error}</div>
      )}

      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
        <div className="flex items-center gap-3 mb-3 text-xs text-gray-500 dark:text-gray-400">
          <span className="flex items-center gap-1"><span className="inline-block w-3 h-3 rounded bg-green-200 dark:bg-green-900/50" /> ≥ 90% AKG</span>
          <span className="flex items-center gap-1"><span className="inline-block w-3 h-3 rounded bg-amber-200 dark:bg-amber-900/50" /> 70–89%</span>
          <span className="flex items-center gap-1"><span className="inline-block w-3 h-3 rounded bg-red-200 dark:bg-red-900/50" /> &lt; 70%</span>
          <span className="flex items-center gap-1"><span className="inline-block w-3 h-3 rounded bg-gray-200 dark:bg-gray-700" /> Tidak ada data</span>
        </div>

        {loading ? (
          <div className="py-8 text-center text-gray-400 dark:text-gray-500 text-sm">Memuat…</div>
        ) : (
          <div className="grid grid-cols-7 gap-2">
            {DAY_LABELS.map((label, i) => (
              <div key={i} className="text-center text-[11px] font-semibold text-gray-500 dark:text-gray-400 pb-1">{label}</div>
            ))}
            {(data?.days || []).map((day) => (
              <DayCell key={day.date} day={day} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function NutritionReport() {
  const [tab, setTab] = useState('harian')

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-gray-900 dark:text-white">Laporan Nutrisi</h1>
        <p className="text-xs text-gray-500 dark:text-gray-400">
          Analisis kecukupan gizi berdasarkan bahan yang diterima & tray terkirim.
        </p>
      </div>

      <div className="flex gap-2 border-b border-gray-200 dark:border-gray-700">
        {[
          { key: 'harian', label: 'Laporan Harian' },
          { key: 'tracker', label: 'AKG Tracker Mingguan' },
        ].map((t) => (
          <button
            key={t.key}
            data-testid={`tab-${t.key}`}
            onClick={() => setTab(t.key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              tab === t.key
                ? 'border-brand text-brand dark:text-accent'
                : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div>
        {tab === 'harian' ? <LaporanHarian /> : <AkgTracker />}
      </div>
    </div>
  )
}
