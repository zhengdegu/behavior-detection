import { useState, useEffect } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import {
  Radio,
  CalendarClock,
  Settings,
  FlaskConical,
  Monitor,
  LogOut,
} from 'lucide-react'
import type { Camera } from '../types'
import { getCameras } from '../api'
import { clearToken } from '../auth'

const navItems = [
  { to: '/', label: 'Live', icon: Radio },
  { to: '/events', label: 'Events', icon: CalendarClock },
  { to: '/config', label: 'Config', icon: Settings },
  { to: '/analyze', label: 'Analyze', icon: FlaskConical },
  { to: '/system', label: 'System', icon: Monitor },
]

export default function Layout() {
  const [cameras, setCameras] = useState<Camera[]>([])
  const navigate = useNavigate()
  useEffect(() => {
    let cancelled = false
    const fetchCameras = () => {
      getCameras()
        .then((data) => { if (!cancelled) setCameras(data) })
        .catch(() => {})
    }
    fetchCameras()
    const interval = setInterval(fetchCameras, 10_000)
    return () => { cancelled = true; clearInterval(interval) }
  }, [])

  const total = cameras.length
  const online = cameras.filter((c) => c.online !== false).length

  return (
    <div className="min-h-screen bg-bg">
      {/* Fixed top navigation bar */}
      <nav
        className="fixed top-0 left-0 right-0 z-100 flex items-center justify-between px-6 h-[52px] border-b border-border"
        style={{
          background: 'rgba(2,6,23,0.88)',
          backdropFilter: 'blur(12px)',
        }}
      >
        {/* Left: Brand */}
        <div className="font-mono text-[13px] font-semibold text-green select-none">
          BD<span className="text-t3 font-normal">.monitor</span>
        </div>

        {/* Center: Tab navigation */}
        <div className="flex gap-0.5">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-1.5 px-3.5 py-1.5 rounded-md text-xs font-medium cursor-pointer transition-colors duration-150 ${
                  isActive
                    ? 'bg-card text-t1'
                    : 'text-t3 hover:text-t2 hover:bg-card'
                }`
              }
            >
              <Icon size={14} />
              {label}
            </NavLink>
          ))}
        </div>

        {/* Right: Camera status + Logout */}
        <div className="hidden md:flex items-center gap-3 text-[11px] text-t3 font-mono">
          <span
            className="w-1.5 h-1.5 rounded-full bg-green"
            style={{ animation: 'dot-pulse 2s infinite' }}
          />
          <span>{total} cameras · {online} online</span>
          <button
            onClick={() => { clearToken(); navigate('/login', { replace: true }) }}
            className="ml-2 flex items-center gap-1 px-2 py-1 rounded-md text-t3 hover:text-red hover:bg-card cursor-pointer transition-colors duration-150"
            title="Logout"
          >
            <LogOut size={13} />
          </button>
        </div>
      </nav>

      {/* Page content area */}
      <main className="pt-[68px] px-6 max-w-[1400px] mx-auto pb-6">
        <Outlet />
      </main>
    </div>
  )
}
