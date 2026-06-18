import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Shield } from 'lucide-react'
import { login } from '../api'
import { setToken } from '../auth'

export default function Login() {
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)

    try {
      const res = await login(username, password)
      setToken(res.token)
      navigate('/', { replace: true })
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center px-4">
      <div className="w-full max-w-[360px]">
        {/* Brand */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-card border border-border mb-4">
            <Shield size={24} className="text-green" />
          </div>
          <h1 className="font-mono text-[15px] font-semibold text-green">
            BD<span className="text-t3 font-normal">.monitor</span>
          </h1>
          <p className="text-[11px] text-t3 mt-1">Behavior Detection System</p>
        </div>

        {/* Login Form */}
        <form onSubmit={handleSubmit} className="bg-bg2 rounded-lg border border-border p-5">
          {error && (
            <div className="mb-3 px-2.5 py-2 rounded-md bg-red/10 border border-red/20 text-red text-[11px]">
              {error}
            </div>
          )}

          <div className="flex flex-col gap-3">
            <div className="flex flex-col gap-1">
              <label htmlFor="username" className="text-[10px] text-t3 uppercase tracking-wide">
                Username
              </label>
              <input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                autoFocus
                required
                className="px-2.5 py-2 rounded-md bg-card text-t1 border border-border font-mono text-[12px] outline-none focus:border-green transition-colors duration-150"
              />
            </div>

            <div className="flex flex-col gap-1">
              <label htmlFor="password" className="text-[10px] text-t3 uppercase tracking-wide">
                Password
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                required
                className="px-2.5 py-2 rounded-md bg-card text-t1 border border-border font-mono text-[12px] outline-none focus:border-green transition-colors duration-150"
              />
            </div>

            <button
              type="submit"
              disabled={loading || !username || !password}
              className="mt-2 w-full py-2 rounded-md bg-green text-bg text-[12px] font-semibold cursor-pointer hover:opacity-85 transition-opacity duration-150 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Signing in...' : 'Sign In'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
