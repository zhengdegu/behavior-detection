import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, Camera, Settings, Activity, ChevronLeft, ChevronRight, Search } from 'lucide-react'
import type { Camera as CameraType, DetectionEvent } from '../types'
import { getCameras } from '../api'
import { useWebSocket } from '../hooks/useWebSocket'
import CameraGrid from '../components/CameraGrid'
import EventCard from '../components/EventCard'
import { formatTimestamp } from '../utils'

export default function Live() {
  // ── Camera state ──
  const [cameras, setCameras] = useState<CameraType[]>([])
  const [loading, setLoading] = useState(true)
  const [currentPage, setCurrentPage] = useState(1)
  const [searchQuery, setSearchQuery] = useState('')
  const pageSize = 9

  // ── Alert state: camera IDs with active alerts ──
  const [alertCameraIds, setAlertCameraIds] = useState<Set<string>>(new Set())
  const alertTimers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map())

  // ── WebSocket for real-time events ──
  const wsUrl = `ws://${window.location.host}/ws/events`
  const { status: wsStatus, lastEvent, events } = useWebSocket(wsUrl)

  // ── Fetch cameras on mount ──
  useEffect(() => {
    let cancelled = false
    getCameras()
      .then((data) => {
        if (!cancelled) setCameras(data)
      })
      .catch(() => {
        // silently handle — cameras will be empty
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  // ── Handle new events: add camera_id to alert set, clear after 5s ──
  const addAlert = useCallback((cameraId: string) => {
    setAlertCameraIds((prev) => {
      const next = new Set(prev)
      next.add(cameraId)
      return next
    })

    // Clear any existing timer for this camera
    const existing = alertTimers.current.get(cameraId)
    if (existing) clearTimeout(existing)

    const timer = setTimeout(() => {
      setAlertCameraIds((prev) => {
        const next = new Set(prev)
        next.delete(cameraId)
        return next
      })
      alertTimers.current.delete(cameraId)
    }, 5000)

    alertTimers.current.set(cameraId, timer)
  }, [])

  useEffect(() => {
    if (lastEvent) {
      addAlert(lastEvent.camera_id)
    }
  }, [lastEvent, addAlert])

  // ── Cleanup alert timers on unmount ──
  useEffect(() => {
    return () => {
      alertTimers.current.forEach((timer) => clearTimeout(timer))
      alertTimers.current.clear()
    }
  }, [])

  // ── Derived stats ──
  const enabledCameras = useMemo(() => cameras.filter((c) => c.enabled !== false), [cameras])
  const onlineCount = enabledCameras.filter((c) => c.online !== false).length
  const todayEvents = events.length
  const lastAlertTime = events.length > 0 ? formatTimestamp(events[0].timestamp) : '—'

  // ── Pagination ──
  const filteredCameras = useMemo(() => {
    let list = enabledCameras
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase()
      list = list.filter(
        (c) => c.name.toLowerCase().includes(q) || c.id.toLowerCase().includes(q),
      )
    }
    return list
  }, [enabledCameras, searchQuery])

  const totalPages = Math.max(1, Math.ceil(filteredCameras.length / pageSize))
  const pagedCameras = useMemo(
    () => filteredCameras.slice((currentPage - 1) * pageSize, currentPage * pageSize),
    [filteredCameras, currentPage],
  )

  // Reset page when search changes
  useEffect(() => {
    setCurrentPage(1)
  }, [searchQuery])

  // ── Loading state ──
  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh] text-t3 text-sm">
        Loading...
      </div>
    )
  }

  // ── Empty state: no cameras ──
  if (cameras.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] gap-4">
        <Camera size={48} className="text-t3" strokeWidth={1.5} />
        <p className="text-t2 text-sm">No cameras configured</p>
        <Link
          to="/config"
          className="flex items-center gap-2 px-4 py-2 rounded-md bg-green text-bg text-sm font-semibold cursor-pointer hover:opacity-85 transition-opacity"
        >
          <Settings size={14} />
          Go to Config page to add cameras
        </Link>
      </div>
    )
  }

  return (
    <div>
      {/* WebSocket disconnected warning bar */}
      {wsStatus === 'disconnected' && (
        <div className="flex items-center gap-2 px-4 py-2 mb-3 rounded-lg bg-orange/10 border border-orange/20 text-orange text-xs font-medium">
          <AlertTriangle size={14} />
          Disconnected, reconnecting...
        </div>
      )}

      {/* Main two-column layout */}
      <div className="grid gap-3 grid-cols-1 lg:grid-cols-[1fr_300px]">
        {/* Left column: Camera grid + pagination + stats bar */}
        <div>
          {/* Search bar */}
          <div className="mb-2 relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-t3" />
            <input
              type="text"
              placeholder="Search by name or ID..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-2 rounded-lg bg-bg2 text-t1 border border-border text-xs outline-none focus:border-green transition-colors duration-150"
            />
          </div>

          <CameraGrid cameras={pagedCameras} alertCameraIds={alertCameraIds} />

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="mt-2 flex items-center justify-center gap-2 py-2">
              <button
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                disabled={currentPage === 1}
                className="p-1.5 rounded-md text-t3 hover:text-t1 hover:bg-card cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed transition-colors duration-150"
              >
                <ChevronLeft size={16} />
              </button>
              {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
                <button
                  key={page}
                  onClick={() => setCurrentPage(page)}
                  className={`w-7 h-7 rounded-md text-xs font-medium cursor-pointer transition-colors duration-150 ${
                    currentPage === page
                      ? 'bg-green text-bg'
                      : 'text-t3 hover:text-t1 hover:bg-card'
                  }`}
                >
                  {page}
                </button>
              ))}
              <button
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                disabled={currentPage === totalPages}
                className="p-1.5 rounded-md text-t3 hover:text-t1 hover:bg-card cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed transition-colors duration-150"
              >
                <ChevronRight size={16} />
              </button>
              <span className="text-[10px] text-t3 ml-2">
                {(currentPage - 1) * pageSize + 1}-{Math.min(currentPage * pageSize, filteredCameras.length)} / {filteredCameras.length}
              </span>
            </div>
          )}

          {/* Stats bar */}
          <div className="mt-3 px-4 py-2.5 bg-bg2 rounded-lg border border-border flex flex-wrap gap-6 text-[11px] text-t3">
            <span>
              Cameras{' '}
              <span className="font-mono text-t1 font-medium">{cameras.length}</span>
            </span>
            <span>
              Online{' '}
              <span className="font-mono text-green font-medium">{onlineCount}</span>
            </span>
            <span>
              Today{' '}
              <span className="font-mono text-t1 font-medium">{todayEvents}</span>
            </span>
            <span>
              Last alert{' '}
              <span className="font-mono text-t1 font-medium">{lastAlertTime}</span>
            </span>
          </div>
        </div>

        {/* Right column: Event Feed */}
        <div className="bg-bg2 rounded-lg border border-border flex flex-col max-h-[calc(100vh-92px)]">
          {/* Feed header */}
          <div className="px-3.5 py-2.5 border-b border-border text-[11px] font-semibold text-t3 uppercase tracking-wide flex justify-between items-center">
            <span className="flex items-center gap-1.5">
              <Activity size={12} />
              Event Feed
            </span>
            <span className="font-mono text-green text-[10px] normal-case">
              {todayEvents} today
            </span>
          </div>

          {/* Scrollable event list */}
          <div className="flex-1 overflow-y-auto p-1.5 flex flex-col gap-1">
            {events.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-t3 text-[11px] gap-2">
                <Activity size={24} strokeWidth={1.5} />
                <span>No events</span>
              </div>
            ) : (
              events.map((event: DetectionEvent, index: number) => (
                <EventCard key={`${event.timestamp}-${event.camera_id}-${index}`} event={event} />
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
