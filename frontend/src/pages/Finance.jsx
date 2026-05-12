import { useEffect, useState } from 'react'
import {
  priceTrendsSummary, spikeAlerts,
  listExpenses, createExpense, deleteExpense,
  listVolunteers, createVolunteer,
  costPerPorsi, listLRAPeriods, generateLRA, submitLRA,
  generatePOFromForecast,
} from '../api/finance'
import { listSuppliers } from '../api/suppliers'
import { useAuth } from '../hooks/useAuth'

const CATEGORIES = ['bahan', 'listrik', 'gas', 'air', 'internet', 'honor', 'bbm', 'lainnya']

export default function Finance() {
  const { hasPermission } = useAuth()
  const canCreate = hasPermission('expense.create')
  const canVolunteer = hasPermission('volunteer.manage')
  const canLRA = hasPermission('lra.generate')
  const canSignoff = hasPermission('lra.signoff')
  const canPO = hasPermission('po.create')

  const [tab, setTab] = useState('cost')
  const [error, setError] = useState('')

  // Cost & price tab
  const [trendsData, setTrendsData] = useState(null)
  const [alertsData, setAlertsData] = useState(null)
  const [costData, setCostData] = useState(null)
  const [costFrom, setCostFrom] = useState(() => isoDaysAgo(14))
  const [costTo, setCostTo] = useState(() => isoToday())

  // Expenses
  const [expenses, setExpenses] = useState([])
  const [expenseFrom, setExpenseFrom] = useState(() => isoDaysAgo(30))
  const [expenseTo, setExpenseTo] = useState(() => isoToday())

  // Volunteers
  const [volunteers, setVolunteers] = useState([])

  // LRA
  const [lras, setLras] = useState([])

  const refresh = async () => {
    setError('')
    try {
      const [tr, sp, c, ex, v, l] = await Promise.all([
        priceTrendsSummary(30, 50),
        spikeAlerts(15),
        costPerPorsi(costFrom, costTo),
        listExpenses({ from_date: expenseFrom, to_date: expenseTo }),
        listVolunteers({ from_date: expenseFrom, to_date: expenseTo }),
        listLRAPeriods(),
      ])
      setTrendsData(tr.data); setAlertsData(sp.data); setCostData(c.data)
      setExpenses(ex.data.expenses || [])
      setVolunteers(v.data.volunteers || [])
      setLras(l.data.periods || [])
    } catch (e) { setError(e.response?.data?.detail || e.message) }
  }
  useEffect(() => { refresh() /* eslint-disable-next-line */ }, [])

  const onAddExpense = async () => {
    const cat = window.prompt(`Kategori? ${CATEGORIES.join(' / ')}`, 'bahan')
    if (!cat || !CATEGORIES.includes(cat)) { setError('Kategori invalid.'); return }
    const amt = window.prompt('Jumlah (Rp)?')
    if (!amt) return
    const amount = parseInt(amt, 10)
    if (!amount || amount < 0) { setError('Amount invalid.'); return }
    const dt = window.prompt('Tanggal?', isoToday())
    if (!dt) return
    const notes = window.prompt('Catatan (opsional)?') || ''
    try {
      await createExpense({ category: cat, amount_idr: amount, expense_date: dt, notes })
      refresh()
    } catch (e) { setError(e.response?.data?.detail || e.message) }
  }

  const onAddVolunteer = async () => {
    const name = window.prompt('Nama relawan?')
    if (!name) return
    const dt = window.prompt('Tanggal kerja?', isoToday())
    if (!dt) return
    const totalStr = window.prompt('Total honor (Rp)?')
    if (!totalStr) return
    const total = parseInt(totalStr, 10)
    if (!total) { setError('Amount invalid.'); return }
    try {
      await createVolunteer({ name, work_date: dt, total_amount: total, hours_worked: 0, hourly_rate: 0 })
      refresh()
    } catch (e) { setError(e.response?.data?.detail || e.message) }
  }

  const onGenerateLRA = async () => {
    const start = window.prompt('Period start?', isoDaysAgo(14))
    if (!start) return
    const end = window.prompt('Period end?', isoToday())
    if (!end) return
    const revStr = window.prompt('Total revenue (dana BGN, Rp)?', '0')
    if (revStr === null) return
    const rev = parseInt(revStr, 10) || 0
    try {
      await generateLRA({ period_start: start, period_end: end, total_revenue_idr: rev })
      refresh()
    } catch (e) { setError(e.response?.data?.detail || e.message) }
  }

  const onSubmitLRA = async (id) => {
    if (!confirm('Submit LRA ini ke BGN?')) return
    try { await submitLRA(id); refresh() }
    catch (e) { setError(e.response?.data?.detail || e.message) }
  }

  const onGeneratePO = async () => {
    const from = window.prompt('Forecast from?', isoDaysAgo(0))
    if (!from) return
    const to = window.prompt('Forecast to?', isoDaysAgo(-7))
    if (!to) return
    try {
      const sups = await listSuppliers()
      const opts = sups.data.suppliers || []
      if (opts.length === 0) { setError('Tidak ada supplier aktif.'); return }
      const sup_id = opts.length === 1 ? opts[0].id : Number(window.prompt(
        `Supplier ID?\n${opts.map(s => `${s.id}: ${s.name}`).join('\n')}`,
        opts[0].id))
      if (!sup_id) return
      const r = await generatePOFromForecast({ from_date: from, to_date: to, supplier_id: sup_id })
      alert(`✅ PO generated: PO-${r.data.po_id}, ${r.data.lines_count} lines, total Rp${r.data.total_idr.toLocaleString('id-ID')}`)
    } catch (e) { setError(e.response?.data?.detail || e.message) }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-gray-800 dark:text-gray-100">Akuntan Finance</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400">Price trends · Cost-per-porsi · Expense · LRA biweekly · PO Generator</p>
        </div>
      </div>

      {error && <div className="text-sm text-red-600 bg-red-50 dark:bg-red-900/20 px-3 py-2 rounded">{error}</div>}

      <div className="flex flex-wrap gap-2">
        {[
          { key: 'cost',    label: 'Cost-per-porsi' },
          { key: 'trends',  label: 'Price Trends' },
          { key: 'alerts',  label: 'Spike Alerts' },
          { key: 'expense', label: 'Expense' },
          { key: 'lra',     label: 'LRA Biweekly' },
          { key: 'po',      label: 'PO Generator' },
        ].map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`px-3 py-1.5 text-sm rounded ${tab === t.key ? 'bg-blue-600 text-white' : 'bg-gray-100 dark:bg-gray-700'}`}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'cost' && costData && (
        <div className="space-y-3">
          <div className="flex flex-wrap gap-2 items-end">
            <FieldDate label="Dari" value={costFrom} onChange={setCostFrom} />
            <FieldDate label="Sampai" value={costTo} onChange={setCostTo} />
            <button onClick={refresh} className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded">Update</button>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Stat label="Total Expense" value={`Rp${(costData.total_expense_idr || 0).toLocaleString('id-ID')}`} />
            <Stat label="Total Porsi" value={costData.total_porsi_confirmed || 0} accent="blue" />
            <Stat label="Cost / Porsi"
              value={`Rp${(costData.cost_per_porsi_idr || 0).toLocaleString('id-ID')}`}
              accent={costData.over_target ? 'red' : 'green'} />
            <Stat label="Target BGN" value={`Rp${(costData.target_idr || 15000).toLocaleString('id-ID')}`} />
          </div>
          <div className="bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700 p-4">
            <h3 className="font-medium mb-2">Breakdown Kategori</h3>
            <table className="w-full text-sm">
              <tbody>
                {CATEGORIES.map(cat => {
                  const v = costData.expenses_by_category?.[cat] || 0
                  if (v === 0) return null
                  return (
                    <tr key={cat} className="border-b border-gray-100 dark:border-gray-700">
                      <td className="py-1">{cat}</td>
                      <td className="py-1 text-right tabular-nums">Rp{v.toLocaleString('id-ID')}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'trends' && trendsData && (
        <div className="bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700 overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 dark:bg-gray-700/50 text-xs uppercase">
              <tr>
                <th className="px-3 py-2 text-left">Bahan</th>
                <th className="px-3 py-2 text-right">Sekarang</th>
                <th className="px-3 py-2 text-right">7 Hari Lalu</th>
                <th className="px-3 py-2 text-right">WoW %</th>
                <th className="px-3 py-2 text-left">Source</th>
              </tr>
            </thead>
            <tbody>
              {(trendsData.items || []).map(it => (
                <tr key={it.food_code} className="border-t border-gray-100 dark:border-gray-700">
                  <td className="px-3 py-1.5">{it.food_name}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums">Rp{it.current_price.toLocaleString('id-ID')}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums text-gray-500">Rp{it.price_7d_ago.toLocaleString('id-ID')}</td>
                  <td className={`px-3 py-1.5 text-right tabular-nums font-semibold ${it.wow_pct > 5 ? 'text-red-600' : it.wow_pct < -5 ? 'text-green-600' : 'text-gray-500'}`}>
                    {it.wow_pct > 0 ? '+' : ''}{it.wow_pct}%
                  </td>
                  <td className="px-3 py-1.5 text-xs text-gray-500">{it.is_manual ? '✏️ manual' : it.source}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'alerts' && alertsData && (
        <div>
          <div className="text-sm text-gray-500 mb-3">Threshold: ≥{alertsData.threshold_pct}% WoW change</div>
          {alertsData.count === 0 ? (
            <div className="text-sm text-gray-400 italic py-8 text-center">
              ✓ Tidak ada bahan yang berubah harga signifikan.
            </div>
          ) : (
            <div className="bg-white dark:bg-gray-800 rounded border border-amber-300 dark:border-amber-700 overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-amber-50 dark:bg-amber-900/20 text-xs uppercase">
                  <tr>
                    <th className="px-3 py-2 text-left">⚠️ Bahan</th>
                    <th className="px-3 py-2 text-right">WoW %</th>
                    <th className="px-3 py-2 text-right">Sekarang</th>
                    <th className="px-3 py-2 text-right">7 Hari Lalu</th>
                  </tr>
                </thead>
                <tbody>
                  {alertsData.alerts.map(a => (
                    <tr key={a.food_code} className="border-t border-gray-100 dark:border-gray-700">
                      <td className="px-3 py-1.5 font-medium">{a.food_name}</td>
                      <td className={`px-3 py-1.5 text-right font-bold ${a.wow_pct > 0 ? 'text-red-600' : 'text-green-600'}`}>
                        {a.wow_pct > 0 ? '+' : ''}{a.wow_pct}%
                      </td>
                      <td className="px-3 py-1.5 text-right tabular-nums">Rp{a.current_price.toLocaleString('id-ID')}</td>
                      <td className="px-3 py-1.5 text-right tabular-nums text-gray-500">Rp{a.price_7d_ago.toLocaleString('id-ID')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {tab === 'expense' && (
        <div className="space-y-3">
          <div className="flex flex-wrap gap-2 items-end">
            <FieldDate label="Dari" value={expenseFrom} onChange={setExpenseFrom} />
            <FieldDate label="Sampai" value={expenseTo} onChange={setExpenseTo} />
            <button onClick={refresh} className="px-3 py-1.5 bg-gray-200 dark:bg-gray-700 text-sm rounded">Refresh</button>
            {canCreate && <button onClick={onAddExpense} className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded">+ Expense</button>}
            {canVolunteer && <button onClick={onAddVolunteer} className="px-3 py-1.5 bg-teal-600 hover:bg-teal-700 text-white text-sm rounded">+ Honor Relawan</button>}
          </div>
          <div className="bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700 overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-gray-700/50 text-xs uppercase">
                <tr>
                  <th className="px-3 py-2 text-left">Tanggal</th>
                  <th className="px-3 py-2 text-left">Kategori</th>
                  <th className="px-3 py-2 text-right">Jumlah</th>
                  <th className="px-3 py-2 text-left">Catatan</th>
                </tr>
              </thead>
              <tbody>
                {expenses.length === 0 ? (
                  <tr><td colSpan={4} className="text-center py-6 text-gray-400">Belum ada expense.</td></tr>
                ) : expenses.map(e => (
                  <tr key={e.id} className="border-t border-gray-100 dark:border-gray-700">
                    <td className="px-3 py-1.5 text-xs">{e.expense_date}</td>
                    <td className="px-3 py-1.5"><span className="text-xs px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-700">{e.category}</span></td>
                    <td className="px-3 py-1.5 text-right tabular-nums">Rp{e.amount_idr.toLocaleString('id-ID')}</td>
                    <td className="px-3 py-1.5 text-xs text-gray-500">{e.notes}</td>
                  </tr>
                ))}
                {volunteers.length > 0 && (
                  <>
                    <tr><td colSpan={4} className="px-3 py-2 text-xs font-semibold bg-gray-100 dark:bg-gray-700/50">Honor Relawan</td></tr>
                    {volunteers.map(v => (
                      <tr key={`v-${v.id}`} className="border-t border-gray-100 dark:border-gray-700">
                        <td className="px-3 py-1.5 text-xs">{v.work_date}</td>
                        <td className="px-3 py-1.5"><span className="text-xs px-2 py-0.5 rounded bg-teal-100 dark:bg-teal-900/30 text-teal-700">honor</span></td>
                        <td className="px-3 py-1.5 text-right tabular-nums">Rp{v.total_amount.toLocaleString('id-ID')}</td>
                        <td className="px-3 py-1.5 text-xs text-gray-500">{v.name} {v.notes && `· ${v.notes}`}</td>
                      </tr>
                    ))}
                  </>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'lra' && (
        <div className="space-y-3">
          {canLRA && (
            <button onClick={onGenerateLRA} className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded">
              + Generate LRA Periode Baru
            </button>
          )}
          <div className="bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700 overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-gray-700/50 text-xs uppercase">
                <tr>
                  <th className="px-3 py-2 text-left">Periode</th>
                  <th className="px-3 py-2 text-left">Status</th>
                  <th className="px-3 py-2 text-right">Revenue</th>
                  <th className="px-3 py-2 text-right">Expense</th>
                  <th className="px-3 py-2 text-right">Porsi</th>
                  <th className="px-3 py-2 text-right">Cost/porsi</th>
                  <th className="px-3 py-2 text-right">Aksi</th>
                </tr>
              </thead>
              <tbody>
                {lras.length === 0 ? (
                  <tr><td colSpan={7} className="text-center py-6 text-gray-400">Belum ada LRA.</td></tr>
                ) : lras.map(l => (
                  <tr key={l.id} className="border-t border-gray-100 dark:border-gray-700">
                    <td className="px-3 py-1.5 text-xs">{l.period_start} → {l.period_end}</td>
                    <td className="px-3 py-1.5">
                      <span className={`text-xs px-2 py-0.5 rounded ${
                        l.status === 'submitted' ? 'bg-green-100 dark:bg-green-900/30 text-green-700' :
                        l.status === 'generated' ? 'bg-amber-100 dark:bg-amber-900/30 text-amber-700' :
                        'bg-gray-100 dark:bg-gray-700'}`}>{l.status}</span>
                    </td>
                    <td className="px-3 py-1.5 text-right tabular-nums">Rp{l.total_revenue_idr.toLocaleString('id-ID')}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums">Rp{l.total_expense_idr.toLocaleString('id-ID')}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums">{l.total_porsi}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums">Rp{l.cost_per_porsi.toLocaleString('id-ID')}</td>
                    <td className="px-3 py-1.5 text-right">
                      {canSignoff && l.status === 'generated' && (
                        <button onClick={() => onSubmitLRA(l.id)} className="text-xs text-green-600 hover:underline">
                          ✓ Submit ke BGN
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'po' && (
        <div className="bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700 p-6 text-center">
          <div className="text-lg mb-2">PO Auto-Generator dari Forecast</div>
          <div className="text-sm text-gray-500 dark:text-gray-400 mb-4">
            Generate PO draft langsung dari forecast bahan menu approved (Phase 2B).
          </div>
          {canPO && (
            <button onClick={onGeneratePO} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded">
              🚀 Generate PO
            </button>
          )}
        </div>
      )}
    </div>
  )
}

function Stat({ label, value, accent }) {
  const cls = accent === 'green' ? 'text-green-600 dark:text-green-400'
    : accent === 'red' ? 'text-red-600 dark:text-red-400'
    : accent === 'blue' ? 'text-blue-600 dark:text-blue-400'
    : 'text-gray-700 dark:text-gray-200'
  return (
    <div className="bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700 p-3">
      <div className="text-xs text-gray-500 dark:text-gray-400">{label}</div>
      <div className={`text-xl font-bold tabular-nums ${cls}`}>{value}</div>
    </div>
  )
}

function FieldDate({ label, value, onChange }) {
  return (
    <label className="block">
      <span className="text-xs text-gray-600 dark:text-gray-400 block mb-1">{label}</span>
      <input type="date" value={value} onChange={e => onChange(e.target.value)}
        className="px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700" />
    </label>
  )
}

function isoToday() { return new Date().toISOString().slice(0, 10) }
function isoDaysAgo(n) { const d = new Date(); d.setDate(d.getDate() - n); return d.toISOString().slice(0, 10) }
