import { useState, useEffect, useCallback, useRef } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, Camera, Settings, Activity } from 'lucide-react'
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
  const onlineCount = cameras.filter((c) => c.online !== false).length
  const todayEvents = events.length
  const lastAlertTime = events.length > 0 ? formatTimestamp(events[0].timestamp) : '—'

  // ── Loading state ──
  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh] text-t3 text-sm">
        加载中...
      </div>
    )
  }

  // ── Empty state: no cameras ──
  if (cameras.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] gap-4">
        <Camera size={48} className="text-t3" strokeWidth={1.5} />
        <p className="text-t2 text-sm">暂无摄像头配置</p>
        <Link
          to="/config"
          className="flex items-center gap-2 px-4 py-2 rounded-md bg-green text-bg text-sm font-semibold cursor-pointer hover:opacity-85 transition-opacity"
        >
          <Settings size={14} />
          前往 Config 页添加摄像头
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
          连接断开，重连中...
        </div>
      )}

      {/* Main two-column layout */}
      <div className="grid gap-3 grid-cols-1 lg:grid-cols-[1fr_300px]">
        {/* Left column: Camera grid + stats bar */}
        <div>
          <CameraGrid cameras={cameras} alertCameraIds={alertCameraIds} />

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
                <span>暂无事件</span>
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
