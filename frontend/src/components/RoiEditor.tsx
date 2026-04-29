import { useRef, useState, useEffect, useCallback } from 'react'
import { getCameraSnapshot } from '../api'
import { normalizeCoord, denormalizeCoord } from '../utils'

interface RoiEditorProps {
  cameraId: string
  initialVertices: [number, number][]
  onVerticesChange: (vertices: [number, number][]) => void
}

const VERTEX_RADIUS = 6
const CLOSE_THRESHOLD = 12
const MIN_VERTICES_TO_CLOSE = 3

export default function RoiEditor({
  cameraId,
  initialVertices,
  onVerticesChange,
}: RoiEditorProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const imgRef = useRef<HTMLImageElement | null>(null)

  // Normalised vertices (0~1)
  const [vertices, setVertices] = useState<[number, number][]>(initialVertices)
  const [closed, setClosed] = useState(initialVertices.length >= MIN_VERTICES_TO_CLOSE)
  const [draggingIdx, setDraggingIdx] = useState<number | null>(null)
  const [imgLoaded, setImgLoaded] = useState(false)
  const [imgError, setImgError] = useState(false)
  const [canvasSize, setCanvasSize] = useState({ w: 0, h: 0 })

  // Sync initial vertices when cameraId changes
  useEffect(() => {
    setVertices(initialVertices)
    setClosed(initialVertices.length >= MIN_VERTICES_TO_CLOSE)
  }, [cameraId, initialVertices])

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

    if (vertices.length === 0) return

    // Convert normalised → pixel
    const pts = vertices.map(([nx, ny]) => denormalizeCoord(nx, ny, w, h))

    // Draw polygon fill if closed
    if (closed && pts.length >= MIN_VERTICES_TO_CLOSE) {
      ctx.beginPath()
      ctx.moveTo(pts[0][0], pts[0][1])
      for (let i = 1; i < pts.length; i++) {
        ctx.lineTo(pts[i][0], pts[i][1])
      }
      ctx.closePath()
      ctx.fillStyle = 'rgba(34, 197, 94, 0.12)'
      ctx.fill()
      ctx.strokeStyle = '#22C55E'
      ctx.lineWidth = 2
      ctx.setLineDash([6, 4])
      ctx.stroke()
      ctx.setLineDash([])
    } else if (pts.length > 1) {
      // Draw open polyline
      ctx.beginPath()
      ctx.moveTo(pts[0][0], pts[0][1])
      for (let i = 1; i < pts.length; i++) {
        ctx.lineTo(pts[i][0], pts[i][1])
      }
      ctx.strokeStyle = '#22C55E'
      ctx.lineWidth = 2
      ctx.stroke()
    }

    // Draw vertices
    for (let i = 0; i < pts.length; i++) {
      ctx.beginPath()
      ctx.arc(pts[i][0], pts[i][1], VERTEX_RADIUS, 0, Math.PI * 2)
      ctx.fillStyle = '#22C55E'
      ctx.fill()
      ctx.strokeStyle = '#020617'
      ctx.lineWidth = 2
      ctx.stroke()
    }
  }, [vertices, closed, canvasSize, imgLoaded])

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
    (px: number, py: number): number => {
      const { w, h } = canvasSize
      for (let i = 0; i < vertices.length; i++) {
        const [dx, dy] = denormalizeCoord(vertices[i][0], vertices[i][1], w, h)
        const dist = Math.hypot(px - dx, py - dy)
        if (dist <= CLOSE_THRESHOLD) return i
      }
      return -1
    },
    [vertices, canvasSize],
  )

  // ── Event handlers ──
  const handleClick = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      if (closed) return
      const [px, py] = getCanvasPos(e)
      const { w, h } = canvasSize

      // Check if clicking first vertex to close
      if (vertices.length >= MIN_VERTICES_TO_CLOSE) {
        const idx = findVertexAt(px, py)
        if (idx === 0) {
          setClosed(true)
          onVerticesChange(vertices)
          return
        }
      }

      // Add new vertex
      const norm = normalizeCoord(px, py, w, h)
      const next = [...vertices, norm]
      setVertices(next)
      onVerticesChange(next)
    },
    [closed, vertices, canvasSize, getCanvasPos, findVertexAt, onVerticesChange],
  )

  const handleDoubleClick = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      e.preventDefault()
      if (closed || vertices.length < MIN_VERTICES_TO_CLOSE) return
      setClosed(true)
      onVerticesChange(vertices)
    },
    [closed, vertices, onVerticesChange],
  )

  const handleMouseDown = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      if (!closed) return
      const [px, py] = getCanvasPos(e)
      const idx = findVertexAt(px, py)
      if (idx >= 0) {
        setDraggingIdx(idx)
        e.preventDefault()
      }
    },
    [closed, getCanvasPos, findVertexAt],
  )

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      if (draggingIdx === null) return
      const [px, py] = getCanvasPos(e)
      const { w, h } = canvasSize
      const norm = normalizeCoord(
        Math.max(0, Math.min(px, w)),
        Math.max(0, Math.min(py, h)),
        w,
        h,
      )
      const next = [...vertices]
      next[draggingIdx] = norm
      setVertices(next)
    },
    [draggingIdx, vertices, canvasSize, getCanvasPos],
  )

  const handleMouseUp = useCallback(() => {
    if (draggingIdx !== null) {
      setDraggingIdx(null)
      onVerticesChange(vertices)
    }
  }, [draggingIdx, vertices, onVerticesChange])

  // ── Clear / Undo ──
  const handleClear = useCallback(() => {
    setVertices([])
    setClosed(false)
    onVerticesChange([])
  }, [onVerticesChange])

  const handleUndo = useCallback(() => {
    if (vertices.length === 0) return
    if (closed) {
      setClosed(false)
      onVerticesChange(vertices)
      return
    }
    const next = vertices.slice(0, -1)
    setVertices(next)
    onVerticesChange(next)
  }, [vertices, closed, onVerticesChange])

  return (
    <div>
      <div ref={containerRef} className="relative w-full">
        <canvas
          ref={canvasRef}
          className="w-full aspect-video rounded-md bg-card cursor-crosshair"
          onClick={handleClick}
          onDoubleClick={handleDoubleClick}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
        />
        {imgError && (
          <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
            <span className="text-t3 text-xs mb-2">无法获取画面，请确认摄像头在线</span>
            <button
              onClick={(e) => { e.stopPropagation(); loadImage() }}
              className="pointer-events-auto px-3 py-1.5 rounded-md bg-card border border-border text-t2 text-xs cursor-pointer hover:text-t1 hover:border-hover transition-colors duration-150"
            >
              重试
            </button>
          </div>
        )}
      </div>

      <div className="text-[10px] text-t3 italic mt-2 mb-2">
        {closed
          ? '拖拽顶点调整区域，或点击 Clear 重新绘制'
          : '点击画面添加顶点，双击或点击首顶点闭合多边形'}
      </div>

      <div className="flex gap-1.5">
        <button
          onClick={handleClear}
          className="px-2.5 py-1.5 rounded-md text-[11px] bg-card text-t2 border border-border cursor-pointer hover:text-t1 hover:border-hover transition-colors duration-150"
        >
          Clear
        </button>
        <button
          onClick={handleUndo}
          className="px-2.5 py-1.5 rounded-md text-[11px] bg-card text-t2 border border-border cursor-pointer hover:text-t1 hover:border-hover transition-colors duration-150"
        >
          Undo
        </button>
      </div>
    </div>
  )
}
