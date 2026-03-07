import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

const INPUT = 'w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-accent'

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(username, password)
      navigate('/', { replace: true })
    } catch {
      setError('Invalid username or password')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-50 dark:bg-gray-900">
      <form onSubmit={handleSubmit} className="bg-white dark:bg-gray-800 p-8 rounded-lg border border-gray-200 dark:border-gray-700 w-80">
        <div className="mb-6">
          <div className="text-xs font-semibold text-gold uppercase tracking-widest">Dapur Pintar</div>
          <div className="text-xl font-bold text-brand dark:text-white">MBG</div>
        </div>

        {error && (
          <div className="mb-4 p-2 text-sm text-red-700 dark:text-red-400 bg-red-50 dark:bg-red-900/30 rounded">{error}</div>
        )}

        <label className="block text-sm text-gray-600 dark:text-gray-300 mb-1">Username</label>
        <input
          type="text"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          className={`${INPUT} mb-4`}
          autoFocus
          required
        />

        <label className="block text-sm text-gray-600 dark:text-gray-300 mb-1">Password</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className={`${INPUT} mb-6`}
          required
        />

        <button
          type="submit"
          disabled={loading}
          className="w-full py-2 bg-brand text-white rounded text-sm font-medium hover:bg-brand-dark disabled:opacity-50"
        >
          {loading ? 'Logging in...' : 'Login'}
        </button>
      </form>
    </div>
  )
}
