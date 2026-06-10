import { useEffect, useRef } from 'react'
import { useDetectionWebSocket } from '../hooks/useDetectionWebSocket'
import { normalizedToPixel } from '../utils'
import type { DetectionFrame } from '../hooks/useDetectionWebSocket'

interface DetectionOverlayProps {
  /** Camera ID to subscribe to detection data */
  cameraId: string
  /** Reference to the container element for size synchronization */
  containerRef: React.RefObject<HTMLDivElement | null>
  /** Whether the overlay is enabled (default: true) */
  enabled?: boolean
}

/** Event-related class names that should be drawn in red */
const EVENT_CLASSES = new Set(['crowd', 'fight', 'fall', 'loiter'])

function drawDetections(
  ctx: CanvasRenderingContext2D,
  frame: DetectionFrame,
  canvasWidth: number,
  canvasHeight: number,
) {
  ctx.clearRect(0, 0, canvasWidth, canvasHeight)

  for (const det of frame.detections) {
    const [x1, y1] = normalizedToPixel(det.bbox[0], det.bbox[1], canvasWidth, canvasHeight)
    const [x2, y2] = normalizedToPixel(det.bbox[2], det.bbox[3], canvasWidth, canvasHeight)
    const w = x2 - x1
    const h = y2 - y1

    const isEvent = EVENT_CLASSES.has(det.class_name)
    const color = isEvent ? '#ef4444' : '#22c55e' // red / green

    // Draw bounding box
    ctx.strokeStyle = color
    ctx.lineWidth = 2
    ctx.strokeRect(x1, y1, w, h)

    // Draw label background
    const label = `${det.class_name} #${det.track_id}`
    ctx.font = '12px monospace'
    const textMetrics = ctx.measureText(label)
    const textHeight = 16
    const padding = 4

    ctx.fillStyle = color
    ctx.fillRect(
      x1,
      y1 - textHeight - padding,
      textMetrics.width + padding * 2,
      textHeight + padding,
    )

    // Draw label text
    ctx.fillStyle = '#ffffff'
    ctx.fillText(label, x1 + padding, y1 - padding)
  }
}

export default function DetectionOverlay({
  cameraId,
  containerRef,
  enabled = true,
}: DetectionOverlayProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const { status, latestFrame } = useDetectionWebSocket(cameraId)

  // Sync canvas size with container using ResizeObserver
  useEffect(() => {
    const container = containerRef.current
    const canvas = canvasRef.current
    if (!container || !canvas) return

    const syncSize = () => {
      const rect = container.getBoundingClientRect()
      canvas.width = rect.width
      canvas.height = rect.height
    }

    syncSize()

    const observer = new ResizeObserver(() => {
      syncSize()
    })
    observer.observe(container)

    return () => {
      observer.disconnect()
    }
  }, [containerRef])

  // Draw detections when latestFrame changes
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    if (!enabled || !latestFrame || status === 'disconnected') {
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      return
    }

    drawDetections(ctx, latestFrame, canvas.width, canvas.height)
  }, [latestFrame, enabled, status])

  // Clear canvas on disconnect
  useEffect(() => {
    if (status === 'disconnected') {
      const canvas = canvasRef.current
      if (!canvas) return
      const ctx = canvas.getContext('2d')
      if (ctx) {
        ctx.clearRect(0, 0, canvas.width, canvas.height)
      }
    }
  }, [status])

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'absolute',
        inset: 0,
        pointerEvents: 'none',
      }}
    />
  )
}
