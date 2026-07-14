import { useRef, useState, useEffect, useCallback } from 'react'
import { getCameraSnapshot } from '../api'
import { normalizeCoord, denormalizeCoord } from '../utils'
import type { RoiPolygon, MultiRoi } from '../types'

interface RoiEditorProps {
  cameraId: string
  initialPolygons: MultiRoi
  onPolygonsChange: (polygons: MultiRoi) => void
}

const VERTEX_RADIUS = 6
const CLOSE_THRESHOLD = 12
const MIN_VERTICES_TO_CLOSE = 3

// Colors for different polygons
const POLYGON_COLORS = [
  '#22C55E', // green
  '#3B82F6', // blue
  '#F59E0B', // amber
  '#EF4444', // red
  '#8B5CF6', // violet
  '#EC4899', // pink
  '#06B6D4', // cyan
  '#F97316', // orange
]

function getColor(index: number): string {
  return POLYGON_COLORS[index % POLYGON_COLORS.length]
}

export default function RoiEditor({
  cameraId,
  initialPolygons,
  onPolygonsChange,
}: RoiEditorProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const imgRef = useRef<HTMLImageElement | null>(null)

  // All completed polygons
  const [polygons, setPolygons] = useState<MultiRoi>(initialPolygons)
  // Current polygon being drawn (not yet closed)
  const [currentVertices, setCurrentVertices] = useState<RoiPolygon>([])
  // Whether we are waiting for the first click to start drawing
  const [waitingFirstClick, setWaitingFirstClick] = useState(false)
  // Which polygon is selected for editing (-1 = none)
  const [selectedIdx, setSelectedIdx] = useState<number>(-1)
  // Dragging state: [polygonIndex, vertexIndex]
  const [dragging, setDragging] = useState<[number, number] | null>(null)

  const [imgLoaded, setImgLoaded] = useState(false)
  const [imgError, setImgError] = useState(false)
  const [canvasSize, setCanvasSize] = useState({ w: 0, h: 0 })

  // Sync initial polygons when cameraId changes
  useEffect(() => {
    setPolygons(initialPolygons)
    setCurrentVertices([])
    setWaitingFirstClick(false)
    setSelectedIdx(-1)
  }, [cameraId, initialPolygons])

  // ── Image loading ──
  const loadImage = useCallback(() => {
    setImgError(false)
    setImgLoaded(false)
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => {
      imgRef.current = img
      setImgLoaded(true)
      setImgError(false)
    }
    img.onerror = () => {
      setImgError(true)
      setImgLoaded(false)
    }
    img.src = getCameraSnapshot(cameraId) + `?t=${Date.now()}`
  }, [cameraId])

  useEffect(() => {
    loadImage()
  }, [loadImage])

  // ── Resize handling ──
  const updateCanvasSize = useCallback(() => {
    const container = containerRef.current
    const canvas = canvasRef.current
    if (!container || !canvas) return
    const rect = container.getBoundingClientRect()
    const w = Math.floor(rect.width)
    const h = Math.floor(rect.width * 9 / 16) // 16:9
    canvas.width = w
    canvas.height = h
    setCanvasSize({ w, h })
  }, [])

  useEffect(() => {
    updateCanvasSize()
    window.addEventListener('resize', updateCanvasSize)
    return () => window.removeEventListener('resize', updateCanvasSize)
  }, [updateCanvasSize])

  // ── Drawing ──
  const draw = useCallback(() => {
    const canvas = canvasRef.current
    const ctx = canvas?.getContext('2d')
    if (!canvas || !ctx) return
    const { w, h } = canvasSize
    if (w === 0 || h === 0) return

    ctx.clearRect(0, 0, w, h)

    // Draw background image
    if (imgRef.current && imgLoaded) {
      ctx.drawImage(imgRef.current, 0, 0, w, h)
    }

    // Draw completed polygons
    for (let pi = 0; pi < polygons.length; pi++) {
      const poly = polygons[pi]
      if (poly.length < MIN_VERTICES_TO_CLOSE) continue
      const color = getColor(pi)
      const isSelected = pi === selectedIdx
      const pts = poly.map(([nx, ny]) => denormalizeCoord(nx, ny, w, h))

      // Fill
      ctx.beginPath()
      ctx.moveTo(pts[0][0], pts[0][1])
      for (let i = 1; i < pts.length; i++) {
        ctx.lineTo(pts[i][0], pts[i][1])
      }
      ctx.closePath()
      ctx.fillStyle = color + (isSelected ? '25' : '15')
      ctx.fill()

      // Stroke
      ctx.strokeStyle = color
      ctx.lineWidth = isSelected ? 2.5 : 1.5
      ctx.setLineDash(isSelected ? [] : [6, 4])
      ctx.stroke()
      ctx.setLineDash([])

      // Vertices (only show when selected)
      if (isSelected) {
        for (const [px, py] of pts) {
          ctx.beginPath()
          ctx.arc(px, py, VERTEX_RADIUS, 0, Math.PI * 2)
          ctx.fillStyle = color
          ctx.fill()
          ctx.strokeStyle = '#020617'
          ctx.lineWidth = 2
          ctx.stroke()
        }
      }

      // Label
      const cx = pts.reduce((s, p) => s + p[0], 0) / pts.length
      const cy = pts.reduce((s, p) => s + p[1], 0) / pts.length
      ctx.font = '600 10px system-ui'
      ctx.fillStyle = color
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText(`ROI ${pi + 1}`, cx, cy)
    }

    // Draw current polygon being drawn
    if (currentVertices.length > 0) {
      const color = getColor(polygons.length)
      const pts = currentVertices.map(([nx, ny]) => denormalizeCoord(nx, ny, w, h))

      if (pts.length > 1) {
        ctx.beginPath()
        ctx.moveTo(pts[0][0], pts[0][1])
        for (let i = 1; i < pts.length; i++) {
          ctx.lineTo(pts[i][0], pts[i][1])
        }
        ctx.strokeStyle = color
        ctx.lineWidth = 2
        ctx.stroke()
      }

      // Vertices
      for (const [px, py] of pts) {
        ctx.beginPath()
        ctx.arc(px, py, VERTEX_RADIUS, 0, Math.PI * 2)
        ctx.fillStyle = color
        ctx.fill()
        ctx.strokeStyle = '#020617'
        ctx.lineWidth = 2
        ctx.stroke()
      }
    }
  }, [polygons, currentVertices, canvasSize, imgLoaded, selectedIdx])

  useEffect(() => {
    draw()
  }, [draw])

  // ── Helpers ──
  const getCanvasPos = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>): [number, number] => {
      const canvas = canvasRef.current!
      const rect = canvas.getBoundingClientRect()
      return [e.clientX - rect.left, e.clientY - rect.top]
    },
    [],
  )

  const findVertexAt = useCallback(
    (px: number, py: number, polyIdx: number): number => {
      const { w, h } = canvasSize
      const poly = polyIdx < polygons.length ? polygons[polyIdx] : currentVertices
      for (let i = 0; i < poly.length; i++) {
        const [dx, dy] = denormalizeCoord(poly[i][0], poly[i][1], w, h)
        const dist = Math.hypot(px - dx, py - dy)
        if (dist <= CLOSE_THRESHOLD) return i
      }
      return -1
    },
    [polygons, currentVertices, canvasSize],
  )

  const findPolygonAt = useCallback(
    (px: number, py: number): number => {
      const { w, h } = canvasSize
      // Check vertices first (higher priority)
      for (let pi = 0; pi < polygons.length; pi++) {
        for (const [nx, ny] of polygons[pi]) {
          const [dx, dy] = denormalizeCoord(nx, ny, w, h)
          if (Math.hypot(px - dx, py - dy) <= CLOSE_THRESHOLD) return pi
        }
      }
      // Then check if point is inside any polygon (ray casting)
      for (let pi = 0; pi < polygons.length; pi++) {
        const poly = polygons[pi]
        if (poly.length < 3) continue
        const pts = poly.map(([nx, ny]) => denormalizeCoord(nx, ny, w, h))
        if (isPointInPolygon(px, py, pts)) return pi
      }
      return -1
    },
    [polygons, canvasSize],
  )

  // ── Event handlers ──
  const isDrawing = currentVertices.length > 0 || waitingFirstClick

  const handleCanvasClick = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      const [px, py] = getCanvasPos(e)
      const { w, h } = canvasSize

      // Waiting for first click to start a new polygon
      if (waitingFirstClick) {
        const norm = normalizeCoord(px, py, w, h)
        setCurrentVertices([norm])
        setWaitingFirstClick(false)
        return
      }

      // Currently drawing a polygon
      if (currentVertices.length > 0) {
        // Check if clicking first vertex to close
        if (currentVertices.length >= MIN_VERTICES_TO_CLOSE) {
          const idx = findVertexAt(px, py, polygons.length)
          if (idx === 0) {
            const next = [...polygons, currentVertices]
            setPolygons(next)
            setCurrentVertices([])
            setSelectedIdx(next.length - 1)
            onPolygonsChange(next)
            return
          }
        }
        // Add vertex
        const norm = normalizeCoord(px, py, w, h)
        setCurrentVertices([...currentVertices, norm])
        return
      }

      // Not drawing — check if clicking on existing polygon
      const clickedPoly = findPolygonAt(px, py)
      if (clickedPoly >= 0) {
        setSelectedIdx(clickedPoly)
      } else {
        setSelectedIdx(-1)
      }
    },
    [waitingFirstClick, currentVertices, polygons, canvasSize, getCanvasPos, findVertexAt, findPolygonAt, onPolygonsChange],
  )

  const handleDoubleClick = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      e.preventDefault()
      if (currentVertices.length < MIN_VERTICES_TO_CLOSE) return
      // Close polygon
      const next = [...polygons, currentVertices]
      setPolygons(next)
      setCurrentVertices([])
      setSelectedIdx(next.length - 1)
      onPolygonsChange(next)
    },
    [currentVertices, polygons, onPolygonsChange],
  )

  const handleMouseDown = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      if (isDrawing) return
      if (selectedIdx < 0 || selectedIdx >= polygons.length) return
      const [px, py] = getCanvasPos(e)
      const idx = findVertexAt(px, py, selectedIdx)
      if (idx >= 0) {
        setDragging([selectedIdx, idx])
        e.preventDefault()
      }
    },
    [isDrawing, selectedIdx, polygons, getCanvasPos, findVertexAt],
  )

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      if (!dragging) return
      const [polyIdx, vertIdx] = dragging
      const [px, py] = getCanvasPos(e)
      const { w, h } = canvasSize
      const norm = normalizeCoord(
        Math.max(0, Math.min(px, w)),
        Math.max(0, Math.min(py, h)),
        w,
        h,
      )
      const nextPolygons = polygons.map((p, i) =>
        i === polyIdx ? p.map((v, j) => (j === vertIdx ? norm : v)) : p,
      )
      setPolygons(nextPolygons)
    },
    [dragging, polygons, canvasSize, getCanvasPos],
  )

  const handleMouseUp = useCallback(() => {
    if (dragging) {
      setDragging(null)
      // Use functional update to ensure we get the latest polygons state
      setPolygons((current) => {
        onPolygonsChange(current)
        return current
      })
    }
  }, [dragging, onPolygonsChange])

  // ── Actions ──
  const handleStartDraw = useCallback(() => {
    setSelectedIdx(-1)
    setWaitingFirstClick(true)
    setCurrentVertices([])
  }, [])

  const handleDeleteSelected = useCallback(() => {
    if (selectedIdx < 0 || selectedIdx >= polygons.length) return
    const next = polygons.filter((_, i) => i !== selectedIdx)
    setPolygons(next)
    setSelectedIdx(-1)
    onPolygonsChange(next)
  }, [selectedIdx, polygons, onPolygonsChange])

  const handleClearAll = useCallback(() => {
    setPolygons([])
    setCurrentVertices([])
    setWaitingFirstClick(false)
    setSelectedIdx(-1)
    onPolygonsChange([])
  }, [onPolygonsChange])

  const handleUndoVertex = useCallback(() => {
    if (currentVertices.length === 0) return
    if (currentVertices.length === 1) {
      setCurrentVertices([])
      setWaitingFirstClick(true) // Go back to waiting state
      return
    }
    setCurrentVertices(currentVertices.slice(0, -1))
  }, [currentVertices])

  const handleCancelDraw = useCallback(() => {
    setCurrentVertices([])
    setWaitingFirstClick(false)
  }, [])

  return (
    <div>
      <div ref={containerRef} className="relative w-full">
        <canvas
          ref={canvasRef}
          className={`w-full aspect-video rounded-md bg-card ${isDrawing ? 'cursor-crosshair' : 'cursor-default'}`}
          onClick={handleCanvasClick}
          onDoubleClick={handleDoubleClick}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
        />
        {imgError && (
          <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
            <span className="text-t3 text-xs mb-2">Unable to get video feed, please confirm camera is online</span>
            <button
              onClick={(e) => { e.stopPropagation(); loadImage() }}
              className="pointer-events-auto px-3 py-1.5 rounded-md bg-card border border-border text-t2 text-xs cursor-pointer hover:text-t1 hover:border-hover transition-colors duration-150"
            >
              Retry
            </button>
          </div>
        )}
      </div>

      {/* Status hint */}
      <div className="text-[10px] text-t3 italic mt-2 mb-2">
        {isDrawing
          ? 'Click to add vertices, double-click or click the first vertex to close the polygon'
          : polygons.length > 0
            ? `${polygons.length} ROI region${polygons.length > 1 ? 's' : ''} defined. Click a region to select, or click "+ Add ROI" to draw more.`
            : 'No ROI defined. Click "+ Add ROI" to draw a detection region.'}
      </div>

      {/* Action buttons */}
      <div className="flex flex-wrap gap-1.5">
        {!isDrawing && (
          <button
            onClick={handleStartDraw}
            className="px-2.5 py-1.5 rounded-md text-[11px] bg-green/10 text-green border border-green/20 cursor-pointer hover:bg-green/20 transition-colors duration-150"
          >
            + Add ROI
          </button>
        )}
        {isDrawing && (
          <>
            <button
              onClick={handleUndoVertex}
              disabled={currentVertices.length === 0}
              className="px-2.5 py-1.5 rounded-md text-[11px] bg-card text-t2 border border-border cursor-pointer hover:text-t1 hover:border-hover transition-colors duration-150 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Undo
            </button>
            <button
              onClick={handleCancelDraw}
              className="px-2.5 py-1.5 rounded-md text-[11px] bg-card text-t2 border border-border cursor-pointer hover:text-t1 hover:border-hover transition-colors duration-150"
            >
              Cancel
            </button>
          </>
        )}
        {!isDrawing && selectedIdx >= 0 && (
          <button
            onClick={handleDeleteSelected}
            className="px-2.5 py-1.5 rounded-md text-[11px] bg-red/10 text-red border border-red/20 cursor-pointer hover:bg-red/20 transition-colors duration-150"
          >
            Delete ROI {selectedIdx + 1}
          </button>
        )}
        {!isDrawing && polygons.length > 0 && (
          <button
            onClick={handleClearAll}
            className="px-2.5 py-1.5 rounded-md text-[11px] bg-card text-t2 border border-border cursor-pointer hover:text-t1 hover:border-hover transition-colors duration-150"
          >
            Clear All
          </button>
        )}
      </div>
    </div>
  )
}

// ── Helper: point-in-polygon (ray casting) for click detection ──
function isPointInPolygon(x: number, y: number, pts: [number, number][]): boolean {
  let inside = false
  for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
    const xi = pts[i][0], yi = pts[i][1]
    const xj = pts[j][0], yj = pts[j][1]
    if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) {
      inside = !inside
    }
  }
  return inside
}
