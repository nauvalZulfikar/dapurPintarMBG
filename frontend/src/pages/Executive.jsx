import { useEffect, useState } from 'react'
import {
  kpiToday, complianceScore, kpiTrend,
  multiKitchen, platformOverview, complianceBundle,
} from '../api/executive'
import { useAuth } from '../hooks/useAuth'

export default function Executive() {
  const { user, hasPermission } = useAuth()
  const isPlatform = user?.role === 'platform_admin'
  const isSuper = isPlatform || ['superadmin', 'admin'].includes(user?.role)
  const canBundle = hasPermission('compliance.bundle_export')

  const [tab, setTab] = useState(isPlatform ? 'platform' : isSuper ? 'multi' : 'mine')
  const [kpi, setKpi] = useState(null)
  const [comp, setComp] = useState(null)
  const [trend, setTrend] = useState(null)
  const [multi, setMulti] = useState(null)
  const [platformData, setPlatformData] = useState(null)
  const [error, setError] = useState('')

  const refresh = async () => {
    setError('')
    try {
      const [k, c, t] = await Promise.all([
        kpiToday().catch(() => ({ data: null })),
        complianceScore(30).catch(() => ({ data: null })),
        kpiTrend('porsi_confirmed', 30).catch(() => ({ data: null })),
      ])
      setKpi(k.data); setComp(c.data); setTrend(t.data)
      if (isSuper) {
        const m = await multiKitchen().catch(() => ({ data: null }))
        setMulti(m.data)
      }
      if (isPlatform) {
        const p = await platformOverview().catch(() => ({ data: null }))
        setPlatformData(p.data)
      }
    } catch (e) { setError(e.response?.data?.detail || e.message) }
  }
  useEffect(() => { refresh() /* eslint-disable-next-line */ }, [])

  const onBundle = async () => {
    const from = window.prompt('From date?', isoDaysAgo(30))
    if (!from) return
    const to = window.prompt('To date?', isoToday())
    if (!to) return
    try {
      const r = await complianceBundle(from, to)
      const blob = new Blob([JSON.stringify(r.data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `bgn-compliance-${from}-to-${to}.json`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) { setError(e.response?.data?.detail || e.message) }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-gray-800 dark:text-gray-100">Executive Dashboard</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400">3 level: per-kitchen · multi-kitchen (yayasan) · platform-wide</p>
        </div>
        {canBundle && (
          <button onClick={onBundle} className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-sm rounded">
            📥 Export BGN Compliance Bundle
          </button>
        )}
      </div>

      {error && <div className="text-sm text-red-600 bg-red-50 dark:bg-red-900/20 px-3 py-2 rounded">{error}</div>}

      <div className="flex flex-wrap gap-2">
        <button onClick={() => setTab('mine')}
          className={`px-3 py-1.5 text-sm rounded ${tab === 'mine' ? 'bg-blue-600 text-white' : 'bg-gray-100 dark:bg-gray-700'}`}>
          Per Dapur
        </button>
        {isSuper && (
          <button onClick={() => setTab('multi')}
            className={`px-3 py-1.5 text-sm rounded ${tab === 'multi' ? 'bg-blue-600 text-white' : 'bg-gray-100 dark:bg-gray-700'}`}>
            Multi-SPPG (Yayasan)
          </button>
        )}
        {isPlatform && (
          <button onClick={() => setTab('platform')}
            className={`px-3 py-1.5 text-sm rounded ${tab === 'platform' ? 'bg-blue-600 text-white' : 'bg-gray-100 dark:bg-gray-700'}`}>
            Platform (Cross-Org)
          </button>
        )}
      </div>

      {/* PER-KITCHEN VIEW */}
      {tab === 'mine' && kpi && (
        <div className="space-y-3">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Stat label="Target Porsi" value={kpi.target_porsi} />
            <Stat label="Items Diterima" value={kpi.items_received} accent="blue" />
            <Stat label="Tray Delivered" value={kpi.trays_delivered} />
            <Stat label="Confirmed Guru" value={kpi.porsi_confirmed} accent="green" />
            <Stat label="Defect Rate" value={`${kpi.defect_rate_pct}%`} accent={kpi.defect_rate_pct > 5 ? 'red' : 'green'} />
            <Stat label="Expense Hari Ini" value={`Rp${kpi.expense_today_idr.toLocaleString('id-ID')}`} />
            <Stat
              label="Cost / Porsi"
              value={kpi.cost_per_porsi_today_idr ? `Rp${kpi.cost_per_porsi_today_idr.toLocaleString('id-ID')}` : '—'}
              accent={kpi.cost_over_target ? 'red' : 'green'}
            />
            <Stat label="Target BGN" value={`Rp${kpi.cost_per_porsi_target_idr.toLocaleString('id-ID')}`} />
          </div>

          {comp && (
            <div className="bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700 p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold">Compliance Score (30 hari)</h3>
                <div className="flex items-baseline gap-2">
                  <span className={`text-3xl font-bold ${comp.composite >= 90 ? 'text-green-600' : comp.composite >= 75 ? 'text-amber-600' : 'text-red-600'}`}>
                    {comp.composite}%
                  </span>
                  <span className="text-lg font-semibold text-gray-500">Grade {comp.grade}</span>
                </div>
              </div>
              <div className="space-y-2">
                {Object.entries(comp.factors).map(([k, v]) => (
                  <FactorBar key={k} label={k.replace(/_/g, ' ').replace('pct', '')} value={v} />
                ))}
              </div>
            </div>
          )}

          {trend && trend.series && (
            <div className="bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700 p-4">
              <h3 className="font-semibold mb-3">Trend: {trend.metric} (30 hari)</h3>
              <MiniChart series={trend.series} />
            </div>
          )}
        </div>
      )}

      {/* MULTI-KITCHEN VIEW */}
      {tab === 'multi' && multi && (
        <div className="space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <RankingCard title="🏆 Compliance Terbaik" items={multi.rankings.best_compliance} accent="green" />
            <RankingCard title="💰 Cost Per Porsi Terendah" items={multi.rankings.lowest_cost} accent="blue" />
            <RankingCard title="⚠️ Defect Rate Tertinggi" items={multi.rankings.highest_defect} accent="red" />
          </div>
          <div className="bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700 overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-gray-700/50 text-xs uppercase">
                <tr>
                  <th className="px-3 py-2 text-left">Dapur</th>
                  <th className="px-3 py-2 text-right">Porsi (target)</th>
                  <th className="px-3 py-2 text-right">Confirmed</th>
                  <th className="px-3 py-2 text-right">Cost/Porsi</th>
                  <th className="px-3 py-2 text-right">Defect %</th>
                  <th className="px-3 py-2 text-right">Compliance</th>
                </tr>
              </thead>
              <tbody>
                {multi.kitchens.map(k => (
                  <tr key={k.kitchen_id} className="border-t border-gray-100 dark:border-gray-700">
                    <td className="px-3 py-1.5 font-medium">{k.kitchen_name}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums">{k.kpi.target_porsi}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums">{k.kpi.porsi_confirmed}</td>
                    <td className={`px-3 py-1.5 text-right tabular-nums ${k.kpi.cost_over_target ? 'text-red-600' : ''}`}>
                      {k.kpi.cost_per_porsi_today_idr ? `Rp${k.kpi.cost_per_porsi_today_idr.toLocaleString('id-ID')}` : '—'}
                    </td>
                    <td className={`px-3 py-1.5 text-right tabular-nums ${k.kpi.defect_rate_pct > 5 ? 'text-red-600' : ''}`}>
                      {k.kpi.defect_rate_pct}%
                    </td>
                    <td className={`px-3 py-1.5 text-right tabular-nums font-semibold ${k.compliance.composite >= 90 ? 'text-green-600' : k.compliance.composite >= 75 ? 'text-amber-600' : 'text-red-600'}`}>
                      {k.compliance.composite}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* PLATFORM VIEW */}
      {tab === 'platform' && platformData && (
        <div className="space-y-3">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <Stat label="Yayasan" value={platformData.totals.organizations} />
            <Stat label="SPPG/Dapur" value={platformData.totals.kitchens} />
            <Stat label="Users" value={platformData.totals.users} />
            <Stat label="Porsi Nasional" value={platformData.totals.porsi_nasional} accent="green" />
            <Stat label="Items Diterima" value={platformData.totals.items_received} accent="blue" />
          </div>
          <div className="bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700 overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-gray-700/50 text-xs uppercase">
                <tr>
                  <th className="px-3 py-2 text-left">Yayasan</th>
                  <th className="px-3 py-2 text-right">SPPG</th>
                  <th className="px-3 py-2 text-right">Porsi Hari Ini</th>
                  <th className="px-3 py-2 text-right">LRA Telat</th>
                  <th className="px-3 py-2 text-left">Status</th>
                </tr>
              </thead>
              <tbody>
                {platformData.per_org.map(o => (
                  <tr key={o.org_id} className="border-t border-gray-100 dark:border-gray-700">
                    <td className="px-3 py-1.5 font-medium">{o.org_name}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums">{o.kitchens}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums">{o.porsi_today}</td>
                    <td className={`px-3 py-1.5 text-right tabular-nums ${o.lra_late_count > 0 ? 'text-red-600' : ''}`}>{o.lra_late_count}</td>
                    <td className="px-3 py-1.5">
                      {o.churn_risk
                        ? <span className="text-xs px-2 py-0.5 rounded bg-red-100 dark:bg-red-900/30 text-red-700">⚠️ Churn risk</span>
                        : <span className="text-xs px-2 py-0.5 rounded bg-green-100 dark:bg-green-900/30 text-green-700">✓ Healthy</span>
                      }
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
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
      <div className={`text-xl font-bold tabular-nums ${cls}`}>{typeof value === 'number' ? value.toLocaleString('id-ID') : value}</div>
    </div>
  )
}

function FactorBar({ label, value }) {
  const color = value >= 90 ? 'bg-green-500' : value >= 75 ? 'bg-amber-500' : 'bg-red-500'
  return (
    <div>
      <div className="flex justify-between text-xs text-gray-600 dark:text-gray-400 mb-1">
        <span className="capitalize">{label}</span>
        <span className="tabular-nums font-medium">{value}%</span>
      </div>
      <div className="h-2 bg-gray-200 dark:bg-gray-700 rounded overflow-hidden">
        <div className={color} style={{ width: `${Math.min(100, value)}%`, height: '100%' }} />
      </div>
    </div>
  )
}

function RankingCard({ title, items, accent }) {
  const border = accent === 'green' ? 'border-green-300 dark:border-green-700'
    : accent === 'red' ? 'border-red-300 dark:border-red-700'
    : 'border-blue-300 dark:border-blue-700'
  return (
    <div className={`bg-white dark:bg-gray-800 rounded border-2 ${border} p-3`}>
      <div className="text-sm font-semibold mb-2">{title}</div>
      {items.length === 0 ? (
        <div className="text-xs text-gray-400 italic">—</div>
      ) : (
        <ol className="text-sm space-y-1 list-decimal pl-5">
          {items.map((n, i) => <li key={i}>{n}</li>)}
        </ol>
      )}
    </div>
  )
}

function MiniChart({ series }) {
  if (!series || series.length === 0) return <div className="text-sm text-gray-400">No data</div>
  const max = Math.max(...series.map(s => s.value), 1)
  return (
    <div className="flex items-end gap-0.5 h-32">
      {series.map((s, i) => {
        const h = (s.value / max) * 100
        return (
          <div key={i} className="flex-1 bg-blue-500/70 hover:bg-blue-600 rounded-t" style={{ height: `${Math.max(2, h)}%` }} title={`${s.date}: ${s.value.toLocaleString('id-ID')}`} />
        )
      })}
    </div>
  )
}

function isoToday() { return new Date().toISOString().slice(0, 10) }
function isoDaysAgo(n) { const d = new Date(); d.setDate(d.getDate() - n); return d.toISOString().slice(0, 10) }
