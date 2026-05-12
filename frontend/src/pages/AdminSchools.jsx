import { useEffect, useState } from 'react'
import { listSchoolsAdmin, createSchool, updateSchool, deleteSchool } from '../api/schools'
import { useAuth } from '../hooks/useAuth'

const LEVELS = ['PAUD', 'TK', 'SD', 'SMP', 'SMA']
const AGE_GROUPS = [
  'PAUD (3-5 tahun)',
  'TK (4-6 tahun)',
  'SD (7-9 tahun)',
  'SD (10-12 tahun)',
  'SMP (13-15 tahun)',
  'SMA (16-18 tahun)',
]

export default function AdminSchools() {
  const { hasPermission } = useAuth()
  const canEdit = hasPermission('school.manage')
  const [schools, setSchools] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [includeInactive, setIncludeInactive] = useState(false)
  const [adding, setAdding] = useState(false)
  const [editingId, setEditingId] = useState(null)

  const empty = {
    name: '', address: '', level: 'SD', age_group: 'SD (7-9 tahun)',
    student_count: 0, distance: 0, gps_lat: '', gps_long: '', contact: '',
  }
  const [form, setForm] = useState(empty)

  const refresh = async () => {
    setLoading(true); setError('')
    try {
      const r = await listSchoolsAdmin(includeInactive)
      setSchools(r.data.schools || [])
    } catch (e) {
      setError(e.response?.data?.detail || e.message)
    } finally {
      setLoading(false)
    }
  }
  useEffect(() => { refresh() /* eslint-disable-next-line */ }, [includeInactive])

  const startAdd = () => { setForm(empty); setAdding(true); setEditingId(null) }
  const startEdit = (s) => {
    setForm({
      name: s.name || '', address: s.address || '',
      level: s.level || 'SD', age_group: s.age_group || 'SD (7-9 tahun)',
      student_count: s.student_count || 0, distance: s.distance || 0,
      gps_lat: s.gps_lat || '', gps_long: s.gps_long || '', contact: s.contact || '',
    })
    setEditingId(s.id); setAdding(false)
  }

  const submit = async () => {
    setError('')
    try {
      const payload = {
        ...form,
        student_count: Number(form.student_count) || 0,
        distance: Number(form.distance) || 0,
      }
      if (editingId) {
        await updateSchool(editingId, payload)
      } else {
        await createSchool(payload)
      }
      setAdding(false); setEditingId(null)
      refresh()
    } catch (e) {
      setError(e.response?.data?.detail || e.message)
    }
  }

  const onDelete = async (s) => {
    if (!confirm(`Nonaktifkan sekolah "${s.name}"?`)) return
    try {
      await deleteSchool(s.id)
      refresh()
    } catch (e) {
      setError(e.response?.data?.detail || e.message)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-gray-800 dark:text-gray-100">Master Sekolah Binaan</h2>
        <div className="flex items-center gap-3">
          <label className="text-sm text-gray-600 dark:text-gray-300 flex items-center gap-2">
            <input type="checkbox" checked={includeInactive} onChange={e => setIncludeInactive(e.target.checked)} />
            Tampilkan non-aktif
          </label>
          {canEdit && (
            <button onClick={startAdd} className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded">
              + Tambah Sekolah
            </button>
          )}
        </div>
      </div>

      {error && <div className="text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 px-3 py-2 rounded">{error}</div>}

      {(adding || editingId) && canEdit && (
        <div className="bg-white dark:bg-gray-800 p-4 rounded border border-gray-200 dark:border-gray-700">
          <h3 className="font-medium mb-3">{editingId ? 'Edit Sekolah' : 'Sekolah Baru'}</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <Field label="Nama Sekolah *">
              <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} className={inp} />
            </Field>
            <Field label="Kontak (HP/WA)">
              <input value={form.contact} onChange={e => setForm({ ...form, contact: e.target.value })} className={inp} />
            </Field>
            <Field label="Jenjang">
              <select value={form.level} onChange={e => setForm({ ...form, level: e.target.value })} className={inp}>
                {LEVELS.map(l => <option key={l} value={l}>{l}</option>)}
              </select>
            </Field>
            <Field label="Kelompok AKG">
              <select value={form.age_group} onChange={e => setForm({ ...form, age_group: e.target.value })} className={inp}>
                {AGE_GROUPS.map(a => <option key={a} value={a}>{a}</option>)}
              </select>
            </Field>
            <Field label="Jumlah Siswa">
              <input type="number" min="0" value={form.student_count} onChange={e => setForm({ ...form, student_count: e.target.value })} className={inp} />
            </Field>
            <Field label="Jarak (meter)">
              <input type="number" min="0" value={form.distance} onChange={e => setForm({ ...form, distance: e.target.value })} className={inp} />
            </Field>
            <Field label="Alamat" className="md:col-span-2">
              <input value={form.address} onChange={e => setForm({ ...form, address: e.target.value })} className={inp} />
            </Field>
            <Field label="GPS Lat (opsional)">
              <input value={form.gps_lat} onChange={e => setForm({ ...form, gps_lat: e.target.value })} className={inp} />
            </Field>
            <Field label="GPS Long (opsional)">
              <input value={form.gps_long} onChange={e => setForm({ ...form, gps_long: e.target.value })} className={inp} />
            </Field>
          </div>
          <div className="mt-3 flex gap-2">
            <button onClick={submit} className="px-3 py-1.5 bg-green-600 hover:bg-green-700 text-white text-sm rounded">
              {editingId ? 'Simpan' : 'Tambah'}
            </button>
            <button onClick={() => { setAdding(false); setEditingId(null) }} className="px-3 py-1.5 bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 text-sm rounded">
              Batal
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="text-sm text-gray-500">Memuat...</div>
      ) : (
        <div className="bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700 overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 dark:bg-gray-700/50 text-gray-600 dark:text-gray-300">
              <tr>
                <th className="px-3 py-2 text-left">Nama</th>
                <th className="px-3 py-2 text-left">Jenjang</th>
                <th className="px-3 py-2 text-left">Kelompok AKG</th>
                <th className="px-3 py-2 text-right">Siswa</th>
                <th className="px-3 py-2 text-right">Jarak (m)</th>
                <th className="px-3 py-2 text-left">Kontak</th>
                <th className="px-3 py-2 text-left">Status</th>
                {canEdit && <th className="px-3 py-2 text-right">Aksi</th>}
              </tr>
            </thead>
            <tbody>
              {schools.length === 0 ? (
                <tr><td colSpan={canEdit ? 8 : 7} className="text-center py-6 text-gray-400">Belum ada sekolah</td></tr>
              ) : schools.map(s => (
                <tr key={s.id} className="border-t border-gray-100 dark:border-gray-700">
                  <td className="px-3 py-2 font-medium">{s.name}</td>
                  <td className="px-3 py-2">{s.level}</td>
                  <td className="px-3 py-2 text-gray-600 dark:text-gray-400">{s.age_group}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{s.student_count}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{s.distance}</td>
                  <td className="px-3 py-2">{s.contact || '—'}</td>
                  <td className="px-3 py-2">
                    {s.is_active
                      ? <span className="text-xs px-2 py-0.5 rounded bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400">Aktif</span>
                      : <span className="text-xs px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-700 text-gray-500">Non-aktif</span>}
                  </td>
                  {canEdit && (
                    <td className="px-3 py-2 text-right space-x-2">
                      <button onClick={() => startEdit(s)} className="text-xs text-blue-600 hover:underline">Edit</button>
                      {s.is_active && <button onClick={() => onDelete(s)} className="text-xs text-red-600 hover:underline">Nonaktifkan</button>}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

const inp = "w-full px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500"

function Field({ label, children, className = '' }) {
  return (
    <label className={`block ${className}`}>
      <span className="text-xs text-gray-600 dark:text-gray-400 block mb-1">{label}</span>
      {children}
    </label>
  )
}
