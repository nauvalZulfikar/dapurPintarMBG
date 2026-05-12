import { useEffect, useState } from 'react'
import { listOrgs, createOrg, patchOrg, deactivateOrg } from '../api/admin'

export default function AdminOrgs() {
  const [orgs, setOrgs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [creating, setCreating] = useState(false)
  const [form, setForm] = useState({ slug: '', name: '', active: true })

  const refresh = async () => {
    setLoading(true); setError('')
    try {
      const r = await listOrgs()
      setOrgs(r.data.organizations)
    } catch (e) {
      setError(e.response?.data?.detail || e.message)
    } finally {
      setLoading(false)
    }
  }
  useEffect(() => { refresh() }, [])

  const onCreate = async () => {
    if (!form.slug || !form.name) return
    try {
      await createOrg(form)
      setCreating(false)
      setForm({ slug: '', name: '', active: true })
      refresh()
    } catch (e) {
      setError(e.response?.data?.detail || e.message)
    }
  }

  const onRename = async (o) => {
    const name = prompt(`Rename "${o.name}" to:`, o.name)
    if (!name || name === o.name) return
    await patchOrg(o.id, { name })
    refresh()
  }
  const onToggle = async (o) => {
    await patchOrg(o.id, { active: !o.active })
    refresh()
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-900 dark:text-white">Organizations</h1>
        <button onClick={() => setCreating(true)} className="px-3 py-1.5 bg-brand text-white rounded hover:bg-brand/90 text-sm">+ New organization</button>
      </div>

      {error && <div className="bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 px-3 py-2 rounded text-sm">{error}</div>}

      {creating && (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4 grid grid-cols-3 gap-3 items-end">
          <div>
            <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Slug (unique, e.g. "kitaraya")</label>
            <input value={form.slug} onChange={e => setForm({ ...form, slug: e.target.value.toLowerCase() })} className="w-full px-2 py-1.5 bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded text-sm font-mono" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Name</label>
            <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} className="w-full px-2 py-1.5 bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded text-sm" />
          </div>
          <div className="flex gap-2">
            <button onClick={onCreate} className="px-3 py-1.5 bg-brand text-white rounded text-sm">Create</button>
            <button onClick={() => setCreating(false)} className="px-3 py-1.5 text-sm text-gray-600 dark:text-gray-300">Cancel</button>
          </div>
        </div>
      )}

      <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 dark:bg-gray-700/50 text-left text-xs uppercase tracking-wider text-gray-500 dark:text-gray-400">
            <tr>
              <th className="px-3 py-2">ID</th>
              <th className="px-3 py-2">Slug</th>
              <th className="px-3 py-2">Name</th>
              <th className="px-3 py-2">Active</th>
              <th className="px-3 py-2 text-right"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
            {loading ? (
              <tr><td colSpan={5} className="px-3 py-6 text-center text-gray-500 dark:text-gray-400">Loading…</td></tr>
            ) : orgs.map(o => (
              <tr key={o.id} className="text-gray-900 dark:text-gray-100">
                <td className="px-3 py-2">{o.id}</td>
                <td className="px-3 py-2 font-mono text-xs">{o.slug}</td>
                <td className="px-3 py-2">{o.name}</td>
                <td className="px-3 py-2">
                  <span className={`inline-block px-2 py-0.5 rounded text-xs ${o.active ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' : 'bg-gray-200 text-gray-600 dark:bg-gray-700 dark:text-gray-400'}`}>
                    {o.active ? 'active' : 'inactive'}
                  </span>
                </td>
                <td className="px-3 py-2 text-right whitespace-nowrap">
                  <button onClick={() => onRename(o)} className="text-brand hover:underline text-xs mr-3">Rename</button>
                  <button onClick={() => onToggle(o)} className="text-brand hover:underline text-xs">
                    {o.active ? 'Deactivate' : 'Activate'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-gray-500 dark:text-gray-400">Deactivating an org hides it in listings but keeps its kitchens & data intact.</p>
    </div>
  )
}
