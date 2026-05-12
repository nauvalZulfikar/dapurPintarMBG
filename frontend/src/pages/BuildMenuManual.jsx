import { useEffect, useMemo, useState } from 'react'
import { calcManualMenu, listAkgPresets, saveMenuPhase2, submitMenuForReview, cycleCheck } from '../api/menuPhase2'
import { useAuth } from '../hooks/useAuth'
import api from '../api/client'

const NUTR_LABELS = {
  energy:  { label: 'Energi',   unit: 'kcal' },
  protein: { label: 'Protein',  unit: 'g' },
  fat:     { label: 'Lemak',    unit: 'g' },
  carbs:   { label: 'Karbo',    unit: 'g' },
  fiber:   { label: 'Serat',    unit: 'g' },
  iron:    { label: 'Zat Besi', unit: 'mg' },
  vitc:    { label: 'Vit C',    unit: 'mg' },
  calcium: { label: 'Kalsium',  unit: 'mg' },
}

const STATUS_PILL = {
  ok:   'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400',
  low:  'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400',
  high: 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400',
}

export default function BuildMenuManual() {
  const { hasPermission } = useAuth()
  const canSubmit = hasPermission('menu.submit_for_review')
  const [foods, setFoods] = useState([])
  const [foodsLoading, setFoodsLoading] = useState(true)
  const [presets, setPresets] = useState({})
  const [items, setItems] = useState([])  // {code, name, category, grams}
  const [search, setSearch] = useState('')
  const [showResults, setShowResults] = useState(false)
  const [ageGroup, setAgeGroup] = useState('SD (7-9 tahun)')
  const [calcResult, setCalcResult] = useState(null)
  const [calcLoading, setCalcLoading] = useState(false)
  const [error, setError] = useState('')

  const [menuName, setMenuName] = useState('')
  const [targetDate, setTargetDate] = useState('')
  const [saving, setSaving] = useState(false)
  const [savedNotice, setSavedNotice] = useState('')

  const [cycleData, setCycleData] = useState(null)

  useEffect(() => {
    api.get('/menu/foods').then(r => {
      const flat = []
      Object.entries(r.data.categories || {}).forEach(([cat, items]) => {
        items.forEach(f => { if (f.has_price) flat.push(f) })
      })
      setFoods(flat)
    }).catch(e => setError(e.response?.data?.detail || e.message))
      .finally(() => setFoodsLoading(false))

    listAkgPresets().then(r => setPresets(r.data || {})).catch(() => {})
    cycleCheck(20).then(r => setCycleData(r.data)).catch(() => {})
  }, [])

  // Recalc when items change (debounced)
  useEffect(() => {
    if (items.length === 0) { setCalcResult(null); return }
    const t = setTimeout(async () => {
      setCalcLoading(true); setError('')
      try {
        const r = await calcManualMenu(items.map(i => ({ code: i.code, grams: Number(i.grams) || 0 })), ageGroup)
        setCalcResult(r.data)
      } catch (e) {
        setError(e.response?.data?.detail || e.message)
      } finally {
        setCalcLoading(false)
      }
    }, 350)
    return () => clearTimeout(t)
  }, [items, ageGroup])

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return []
    return foods.filter(f => f.name.toLowerCase().includes(q) || f.code.toLowerCase().includes(q)).slice(0, 30)
  }, [search, foods])

  const addFood = (f) => {
    if (items.find(i => i.code === f.code)) return
    setItems([...items, { code: f.code, name: f.name, category: f.category, grams: 100 }])
    setSearch(''); setShowResults(false)
  }
  const removeItem = (code) => setItems(items.filter(i => i.code !== code))
  const updateGrams = (code, val) => setItems(items.map(i => i.code === code ? { ...i, grams: val } : i))

  const onSave = async (asReview) => {
    if (!menuName.trim()) { setError('Nama menu wajib diisi.'); return }
    if (items.length === 0) { setError('Minimal 1 bahan harus dipilih.'); return }
    setSaving(true); setError(''); setSavedNotice('')
    try {
      const payload = {
        items: calcResult?.items || [],
        totals: calcResult?.totals,
        cost_per_serving: calcResult?.cost_per_serving,
        age_group: ageGroup,
        akg_compare: calcResult?.akg_compare,
      }
      const saveRes = await saveMenuPhase2({
        name: menuName.trim(),
        payload,
        source: 'manual',
        target_date: targetDate || null,
      })
      if (asReview && canSubmit) {
        await submitMenuForReview(saveRes.data.id)
        setSavedNotice(`✅ Menu "${menuName}" disimpan & di-submit untuk review.`)
      } else {
        setSavedNotice(`✅ Menu "${menuName}" disimpan sebagai draft.`)
      }
      // Reset form
      setMenuName(''); setTargetDate(''); setItems([])
    } catch (e) {
      setError(e.response?.data?.detail || e.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-bold text-gray-800 dark:text-gray-100">Build Menu Manual</h2>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          Input menu manual (mis. dari permintaan siswa), lihat gizi & biaya real-time vs AKG.
        </p>
      </div>

      {error && <div className="text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 px-3 py-2 rounded">{error}</div>}
      {savedNotice && <div className="text-sm text-green-700 dark:text-green-400 bg-green-50 dark:bg-green-900/20 px-3 py-2 rounded">{savedNotice}</div>}

      {/* Cycle check warning */}
      {cycleData?.warnings?.length > 0 && (
        <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-300 dark:border-amber-700 rounded p-3">
          <div className="text-sm font-medium text-amber-800 dark:text-amber-300">⚠️ Anti-bosen warning (siklus 20 hari BGN)</div>
          <ul className="mt-1 text-xs text-amber-700 dark:text-amber-400 list-disc pl-5">
            {cycleData.warnings.map((w, i) => <li key={i}>{w}</li>)}
          </ul>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Left: search + items list */}
        <div className="bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700 p-4">
          <div className="flex items-center gap-2 mb-3">
            <input
              type="text" value={search} placeholder="Cari bahan TKPI (nama atau kode)..."
              onChange={e => { setSearch(e.target.value); setShowResults(true) }}
              onFocus={() => setShowResults(true)}
              className={inp + ' flex-1'}
            />
            <select value={ageGroup} onChange={e => setAgeGroup(e.target.value)} className={inp + ' w-44'}>
              {Object.keys(presets).map(k => <option key={k} value={k}>{k}</option>)}
            </select>
          </div>

          {showResults && filtered.length > 0 && (
            <div className="border border-gray-200 dark:border-gray-700 rounded max-h-56 overflow-y-auto bg-white dark:bg-gray-900 mb-3">
              {filtered.map(f => (
                <button key={f.code} onClick={() => addFood(f)}
                  className="w-full text-left px-3 py-2 hover:bg-blue-50 dark:hover:bg-blue-900/20 border-b border-gray-100 dark:border-gray-800 last:border-0">
                  <div className="flex justify-between items-center text-sm">
                    <div>
                      <div className="font-medium">{f.name}</div>
                      <div className="text-xs font-mono text-gray-500">{f.code} · {f.category}</div>
                    </div>
                    <div className="text-xs text-blue-600 dark:text-blue-400">+ Tambah</div>
                  </div>
                </button>
              ))}
            </div>
          )}

          <h3 className="text-sm font-medium text-gray-600 dark:text-gray-300 mt-2 mb-2">Bahan dipilih ({items.length})</h3>
          {items.length === 0 ? (
            <div className="text-sm text-gray-400 italic py-4 text-center">Belum ada bahan. Cari di atas.</div>
          ) : (
            <div className="space-y-1">
              {items.map(it => (
                <div key={it.code} className="flex items-center gap-2 py-1.5 border-b border-gray-100 dark:border-gray-700 last:border-0">
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium truncate">{it.name}</div>
                    <div className="text-xs text-gray-500 font-mono">{it.code} · {it.category}</div>
                  </div>
                  <input
                    type="number" min="0" step="10" value={it.grams}
                    onChange={e => updateGrams(it.code, e.target.value)}
                    className={inp + ' w-20 text-right'}
                  />
                  <span className="text-xs text-gray-500 w-6">g</span>
                  <button onClick={() => removeItem(it.code)} className="text-red-500 text-xs hover:underline">×</button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right: live calc */}
        <div className="bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700 p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-gray-600 dark:text-gray-300">Analisis Gizi & Biaya</h3>
            {calcLoading && <span className="text-xs text-gray-400">menghitung...</span>}
          </div>

          {!calcResult ? (
            <div className="text-sm text-gray-400 italic py-12 text-center">Pilih bahan dulu.</div>
          ) : (
            <>
              <div className="bg-blue-50 dark:bg-blue-900/20 rounded p-3 mb-3">
                <div className="flex justify-between items-baseline">
                  <span className="text-xs text-blue-700 dark:text-blue-400">Biaya per porsi</span>
                  <span className="text-2xl font-bold text-blue-900 dark:text-blue-300 tabular-nums">
                    Rp{(calcResult.cost_per_serving || 0).toLocaleString('id-ID')}
                  </span>
                </div>
                {calcResult.cost_per_serving > 15000 && (
                  <div className="text-xs text-amber-700 dark:text-amber-400 mt-1">⚠️ Lebih dari target Rp15rb/porsi BGN</div>
                )}
              </div>

              <div className="space-y-1.5">
                {Object.entries(NUTR_LABELS).map(([key, def]) => {
                  const val = calcResult.totals?.[key] ?? 0
                  const cmp = calcResult.akg_compare?.[key]
                  return (
                    <div key={key} className="flex items-center gap-2 text-sm">
                      <span className="w-20 text-gray-600 dark:text-gray-400">{def.label}</span>
                      <span className="flex-1 tabular-nums font-mono text-gray-800 dark:text-gray-100">
                        {val.toFixed(1)} {def.unit}
                      </span>
                      {cmp && (
                        <span className={`text-xs px-2 py-0.5 rounded ${STATUS_PILL[cmp.status] || ''} tabular-nums`}>
                          {cmp.kind === 'min' ? `${cmp.pct}% dari ${cmp.target}` : `${cmp.pct}% dari max ${cmp.target}`}
                        </span>
                      )}
                    </div>
                  )
                })}
              </div>

              {calcResult.missing_codes?.length > 0 && (
                <div className="mt-3 text-xs text-red-600">⚠️ Kode tidak ditemukan: {calcResult.missing_codes.join(', ')}</div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Save panel */}
      {items.length > 0 && (
        <div className="bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700 p-4">
          <h3 className="text-sm font-medium mb-3">Simpan Menu</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
            <label className="block">
              <span className="text-xs text-gray-600 dark:text-gray-400 block mb-1">Nama Menu *</span>
              <input value={menuName} onChange={e => setMenuName(e.target.value)} className={inp} placeholder="e.g. Menu Selasa Senin SD 7-9" />
            </label>
            <label className="block">
              <span className="text-xs text-gray-600 dark:text-gray-400 block mb-1">Tanggal Disajikan (opsional)</span>
              <input type="date" value={targetDate} onChange={e => setTargetDate(e.target.value)} className={inp} />
            </label>
          </div>
          <div className="flex gap-2">
            <button onClick={() => onSave(false)} disabled={saving} className="px-3 py-1.5 bg-gray-600 hover:bg-gray-700 text-white text-sm rounded disabled:opacity-50">
              Simpan Draft
            </button>
            {canSubmit && (
              <button onClick={() => onSave(true)} disabled={saving} className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded disabled:opacity-50">
                Simpan & Submit untuk Review
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

const inp = "px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
