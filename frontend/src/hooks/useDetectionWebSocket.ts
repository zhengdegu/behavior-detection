import { useState, useEffect, useRef, useCallback } from 'react'

// ── Types ──

export interface DetectionFrame {
  camera_id: string
  timestamp: number
  detections: Array<{
    bbox: [number, number, number, number] // [x1, y1, x2, y2] normalized 0-1
    class_name: string
    track_id: number
    confidence: number
  }>
}

export interface UseDetectionWebSocketReturn {
  status: 'connecting' | 'connected' | 'disconnected'
  latestFrame: DetectionFrame | null
}

// ── Constants ──

const MAX_DELAY_MS = 30_000

// ── Helpers ──

function getReconnectDelay(attempt: number): number {
  return Math.min(Math.pow(2, attempt) * 1000, MAX_DELAY_MS)
}

// ── Hook ──

export function useDetectionWebSocket(
  cameraId: string,
): UseDetectionWebSocketReturn {
  const [status, setStatus] =
    useState<UseDetectionWebSocketReturn['status']>('connecting')
  const [latestFrame, setLatestFrame] = useState<DetectionFrame | null>(null)

  const wsRef = useRef<WebSocket | null>(null)
  const attemptRef = useRef(0)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const unmountedRef = useRef(false)

  const connect = useCallback(() => {
    if (unmountedRef.current) return

    setStatus('connecting')

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${protocol}//${window.location.host}/ws/detections/${cameraId}`
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      if (unmountedRef.current) return
      attemptRef.current = 0
      setStatus('connected')
    }

    ws.onmessage = (event: MessageEvent) => {
      if (unmountedRef.current) return
      try {
        const parsed = JSON.parse(event.data as string) as DetectionFrame
        setLatestFrame(parsed)
      } catch {
        // Ignore malformed messages
      }
    }

    ws.onclose = () => {
      if (unmountedRef.current) return
      setStatus('disconnected')
      setLatestFrame(null)
      scheduleReconnect()
    }

    ws.onerror = () => {
      ws.close()
    }
  }, [cameraId])

  const scheduleReconnect = useCallback(() => {
    if (unmountedRef.current) return
    const delay = getReconnectDelay(attemptRef.current)
    attemptRef.current += 1
    timerRef.current = setTimeout(() => {
      connect()
    }, delay)
  }, [connect])

  useEffect(() => {
    unmountedRef.current = false
    connect()

    return () => {
      unmountedRef.current = true

      if (timerRef.current !== null) {
        clearTimeout(timerRef.current)
        timerRef.current = null
      }

      if (wsRef.current) {
        wsRef.current.onopen = null
        wsRef.current.onmessage = null
        wsRef.current.onclose = null
        wsRef.current.onerror = null
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [connect])

  return { status, latestFrame }
}
