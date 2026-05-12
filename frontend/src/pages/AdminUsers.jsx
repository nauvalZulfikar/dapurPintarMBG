import { useEffect, useState } from 'react'
import {
  listUsers, createUser, patchUser, deleteUser,
  listKitchens, assignKitchen, unassignKitchen,
} from '../api/admin'

export default function AdminUsers() {
  const [users, setUsers] = useState([])
  const [kitchens, setKitchens] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [creating, setCreating] = useState(false)
  const [saving, setSaving] = useState(false)
  const [newUser, setNewUser] = useState({
    username: '', password: '', role: 'user',
    kitchen_id: '', kitchen_role: 'head_sppg',
  })

  const refresh = async () => {
    setLoading(true); setError('')
    try {
      const [u, k] = await Promise.all([listUsers(), listKitchens()])
      setUsers(u.data.users)
      setKitchens(k.data.kitchens.filter(x => x.active))
    } catch (e) {
      setError(e.response?.data?.detail || e.message)
    } finally {
      setLoading(false)
    }
  }
  useEffect(() => { refresh() }, [])

  const onCreate = async () => {
    if (saving) return
    if (!newUser.username || !newUser.password) return
    if (newUser.role === 'user' && !newUser.kitchen_id) {
      setError('Pick a kitchen for this user, or promote them to superadmin.')
      return
    }
    setSaving(true); setError('')
    try {
      const res = await createUser({
        username: newUser.username,
        password: newUser.password,
        role: newUser.role,
      })
      if (newUser.role === 'user' && newUser.kitchen_id) {
        await assignKitchen(res.data.id, Number(newUser.kitchen_id), newUser.kitchen_role)
      }
      setCreating(false)
      setNewUser({ username: '', password: '', role: 'user', kitchen_id: '', kitchen_role: 'admin' })
      refresh()
    } catch (e) {
      setError(e.response?.data?.detail || e.message)
    } finally {
      setSaving(false)
    }
  }

  const onAssign = async (userId, kitchenId, role) => {
    await assignKitchen(userId, kitchenId, role)
    refresh()
  }
  const onUnassign = async (userId, kitchenId) => {
    await unassignKitchen(userId, kitchenId)
    refresh()
  }
  const onPatchRole = async (user) => {
    const r = prompt(`Global role for ${user.username} (superadmin / user):`, user.role)
    if (!r || r === user.role) return
    await patchUser(user.id, { role: r })
    refresh()
  }
  const onReset = async (user) => {
    const p = prompt(`New password for ${user.username} (min 8 chars):`)
    if (!p || p.length < 8) return
    await patchUser(user.id, { password: p })
    alert('Password updated')
  }
  const onDelete = async (user) => {
    if (!confirm(`Delete user ${user.username}? This removes all kitchen assignments.`)) return
    await deleteUser(user.id)
    refresh()
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-900 dark:text-white">Users</h1>
        <button onClick={() => setCreating(true)} className="px-3 py-1.5 bg-brand text-white rounded hover:bg-brand/90 text-sm">+ New user</button>
      </div>

      {error && <div className="bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 px-3 py-2 rounded text-sm">{error}</div>}

      {creating && (
        <div data-testid="create-user-form" className="bg-white dark:bg-gray-800 rounded-lg shadow p-4 space-y-3">
          <fieldset disabled={saving} className="space-y-3 disabled:opacity-60">
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Username</label>
              <input value={newUser.username} onChange={e => setNewUser({ ...newUser, username: e.target.value })}
                className="w-full px-2 py-1.5 bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded text-sm text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Password</label>
              <input type="password" value={newUser.password} onChange={e => setNewUser({ ...newUser, password: e.target.value })}
                className="w-full px-2 py-1.5 bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded text-sm text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Access level</label>
              <select value={newUser.role} onChange={e => setNewUser({ ...newUser, role: e.target.value })}
                className="w-full px-2 py-1.5 bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded text-sm text-gray-900 dark:text-white">
                <option value="user">Kitchen staff (pick a kitchen below)</option>
                <option value="superadmin">Superadmin (all kitchens in this org)</option>
              </select>
            </div>
          </div>

          {newUser.role === 'user' && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Kitchen</label>
                <select
                  value={newUser.kitchen_id}
                  onChange={e => setNewUser({ ...newUser, kitchen_id: e.target.value })}
                  className="w-full px-2 py-1.5 bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded text-sm text-gray-900 dark:text-white"
                >
                  <option value="">— Select kitchen —</option>
                  {kitchens.map(k => (
                    <option key={k.id} value={k.id}>{k.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Role in this kitchen</label>
                <select
                  value={newUser.kitchen_role}
                  onChange={e => setNewUser({ ...newUser, kitchen_role: e.target.value })}
                  title={KITCHEN_ROLES.find(r => r.id === newUser.kitchen_role)?.hint}
                  className="w-full px-2 py-1.5 bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded text-sm text-gray-900 dark:text-white"
                >
                  {KITCHEN_ROLES.map(r => (
                    <option key={r.id} value={r.id}>{r.label} — {r.hint}</option>
                  ))}
                </select>
              </div>
            </div>
          )}
          </fieldset>

          <div className="flex gap-2 justify-end pt-1 items-center">
            {saving && (
              <span className="text-xs text-gray-500 dark:text-gray-400 mr-2 inline-flex items-center gap-1.5">
                <svg className="animate-spin h-3.5 w-3.5 text-brand" viewBox="0 0 24 24" fill="none">
                  <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" opacity="0.25" />
                  <path d="M4 12a8 8 0 018-8" stroke="currentColor" strokeWidth="4" strokeLinecap="round" />
                </svg>
                Membuat user…
              </span>
            )}
            <button onClick={() => setCreating(false)} disabled={saving}
              className="px-3 py-1.5 text-sm text-gray-600 dark:text-gray-300 disabled:opacity-50">Cancel</button>
            <button onClick={onCreate} disabled={saving}
              className="px-3 py-1.5 bg-brand text-white rounded text-sm disabled:opacity-50 inline-flex items-center gap-1.5">
              {saving && (
                <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24" fill="none">
                  <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" opacity="0.25" />
                  <path d="M4 12a8 8 0 018-8" stroke="currentColor" strokeWidth="4" strokeLinecap="round" />
                </svg>
              )}
              {saving ? 'Creating…' : 'Create user'}
            </button>
          </div>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            Tip: to add this user to multiple kitchens, create them here first, then use the Kitchens column below to assign more.
          </p>
        </div>
      )}

      <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 dark:bg-gray-700/50 text-left text-xs uppercase tracking-wider text-gray-500 dark:text-gray-400">
            <tr>
              <th className="px-3 py-2">ID</th>
              <th className="px-3 py-2">Username</th>
              <th className="px-3 py-2">Role</th>
              <th className="px-3 py-2">Kitchens</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
            {loading ? (
              <tr><td colSpan={5} className="px-3 py-6 text-center text-gray-500 dark:text-gray-400">Loading…</td></tr>
            ) : users.map(u => (
              <tr key={u.id} className="text-gray-900 dark:text-gray-100 align-top">
                <td className="px-3 py-2">{u.id}</td>
                <td className="px-3 py-2">{u.username}</td>
                <td className="px-3 py-2">
                  <span className={`text-xs px-2 py-0.5 rounded ${u.role === 'superadmin' || u.role === 'admin' ? 'bg-gold/20 text-amber-700 dark:text-amber-400' : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300'}`}>
                    {u.role}
                  </span>
                </td>
                <td className="px-3 py-2">
                  <KitchenAssignments
                    user={u}
                    kitchens={kitchens}
                    onAssign={onAssign}
                    onUnassign={onUnassign}
                  />
                </td>
                <td className="px-3 py-2 text-right whitespace-nowrap">
                  <button onClick={() => onPatchRole(u)} className="text-brand hover:underline text-xs mr-3">Role</button>
                  <button onClick={() => onReset(u)} className="text-brand hover:underline text-xs mr-3">Reset pw</button>
                  <button onClick={() => onDelete(u)} className="text-red-600 hover:underline text-xs">Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// Canonical 5 BGN-aligned kitchen roles (Phase 0 RBAC).
// Legacy roles `admin` & `ahli_gizi` still accepted by the API as aliases
// (head_sppg & nutritionist respectively) — see backend/utils/permissions.py.
const KITCHEN_ROLES = [
  { id: 'head_sppg',    label: 'Kepala SPPG',  hint: 'Pimpinan SPPG — full kitchen ops, approve menu, sign LRA' },
  { id: 'nutritionist', label: 'Ahli Gizi',    hint: 'Menu planner, AKG, QC bahan, sign-off Joint Inspection' },
  { id: 'accountant',   label: 'Akuntan',      hint: 'PO, expense, LRA, sign-off Joint Inspection' },
  { id: 'aslap',        label: 'ASLAP',        hint: 'Asisten Lapangan — daily checklist, delivery confirm' },
  { id: 'head_kitchen', label: 'Kepala Chef',  hint: 'Production batch trigger, tablet processing scan' },
]

function KitchenAssignments({ user, kitchens, onAssign, onUnassign }) {
  const [addKid, setAddKid] = useState('')
  const [addRole, setAddRole] = useState('head_sppg')
  const assigned = new Set(user.kitchens.map(k => k.kitchen_id))
  const available = kitchens.filter(k => !assigned.has(k.id))

  return (
    <div className="space-y-1">
      {user.kitchens.length === 0 && <div className="text-xs text-gray-400 dark:text-gray-500">None</div>}
      {user.kitchens.map(k => (
        <div key={k.kitchen_id} className="flex items-center gap-2 text-xs">
          <span className="font-mono text-gray-500 dark:text-gray-400">#{k.kitchen_id}</span>
          <span>{k.name}</span>
          <span className="text-gray-400 dark:text-gray-500">· {k.role}</span>
          <button onClick={() => onUnassign(user.id, k.kitchen_id)} className="text-red-500 hover:underline">remove</button>
        </div>
      ))}
      {available.length > 0 && (
        <div className="flex items-center gap-2 text-xs mt-1">
          <select value={addKid} onChange={e => setAddKid(e.target.value)} className="px-1.5 py-1 bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded">
            <option value="">+ assign kitchen…</option>
            {available.map(k => <option key={k.id} value={k.id}>{k.name}</option>)}
          </select>
          {addKid && (
            <>
              <select
                value={addRole}
                onChange={e => setAddRole(e.target.value)}
                title={KITCHEN_ROLES.find(r => r.id === addRole)?.hint}
                className="px-1.5 py-1 bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded"
              >
                {KITCHEN_ROLES.map(r => (
                  <option key={r.id} value={r.id}>{r.label}</option>
                ))}
              </select>
              <button
                onClick={() => { onAssign(user.id, Number(addKid), addRole); setAddKid('') }}
                className="px-2 py-1 bg-brand text-white rounded"
              >Add</button>
            </>
          )}
        </div>
      )}
    </div>
  )
}
