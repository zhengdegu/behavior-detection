import { useState, useEffect, useCallback, useRef } from 'react'
import {
  Upload,
  Video,
  Download,
  AlertTriangle,
  Users,
  LayoutGrid,
  Clock,
  Activity,
  Trash2,
} from 'lucide-react'
import type { AnalysisTask, DetectionEvent } from '../types'
import {
  uploadVideo,
  getAnalysisTasks,
  startAnalysis,
  deleteAnalysisTask,
  getTaskFirstFrameUrl,
  getTaskVideoUrl,
} from '../api'
import { formatFileSize } from '../utils'

// ── Status label helpers ──

function statusLabel(status: string): string {
  switch (status) {
    case 'waiting_config':
      return 'Waiting Config'
    case 'processing':
      return 'Processing'
    case 'completed':
      return 'Completed'
    case 'failed':
      return 'Failed'
    default:
      return status
  }
}

function statusColor(status: string): string {
  switch (status) {
    case 'waiting_config':
      return 'text-orange'
    case 'processing':
      return 'text-blue'
    case 'completed':
      return 'text-green'
    case 'failed':
      return 'text-red'
    default:
      return 'text-t3'
  }
}

// ── Format date for display ──

function formatDate(iso: string): string {
  const d = new Date(iso)
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  const hh = String(d.getHours()).padStart(2, '0')
  const mi = String(d.getMinutes()).padStart(2, '0')
  return `${mm}-${dd} ${hh}:${mi}`
}

function formatSeconds(sec: number): string {
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

// ── Count events by sub_type ──

function countByType(events: DetectionEvent[]): Record<string, number> {
  const counts: Record<string, number> = {}
  for (const ev of events) {
    counts[ev.sub_type] = (counts[ev.sub_type] || 0) + 1
  }
  return counts
}

export default function Analyze() {
  const [tasks, setTasks] = useState<AnalysisTask[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [starting, setStarting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fileInputRef = useRef<HTMLInputElement>(null)
  const videoRef = useRef<HTMLVideoElement>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // ── Fetch tasks ──

  const fetchTasks = useCallback(async () => {
    try {
      const list = await getAnalysisTasks()
      setTasks(list)
    } catch {
      // silently ignore
    }
  }, [])

  // ── Initial fetch ──

  useEffect(() => {
    fetchTasks()
  }, [fetchTasks])

  // ── Poll every 3s while any task is processing ──

  useEffect(() => {
    const hasProcessing = tasks.some((t) => t.status === 'processing')

    if (hasProcessing) {
      if (!pollRef.current) {
        pollRef.current = setInterval(fetchTasks, 3000)
      }
    } else {
      if (pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
    }

    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
    }
  }, [tasks, fetchTasks])

  // ── Upload handler ──

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    setError(null)
    try {
      const task = await uploadVideo(file)
      await fetchTasks()
      setSelectedId(task.id)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setUploading(false)
      // Reset input so same file can be re-selected
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  // ── Start analysis ──

  const handleStart = async () => {
    if (!selectedId) return
    setStarting(true)
    setError(null)
    try {
      await startAnalysis(selectedId)
      await fetchTasks()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to start analysis')
    } finally {
      setStarting(false)
    }
  }

  // ── Delete task ──

  const handleDelete = async (taskId: string) => {
    setError(null)
    try {
      await deleteAnalysisTask(taskId)
      if (selectedId === taskId) setSelectedId(null)
      await fetchTasks()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Delete failed')
    }
  }

  // ── Seek video to timestamp ──

  const seekToTime = (timestamp: string) => {
    if (!videoRef.current || !selected) return
    // Parse event timestamp and task created_at to compute offset
    const eventTime = new Date(timestamp).getTime()
    const taskStart = new Date(selected.created_at).getTime()
    const offsetSec = Math.max(0, (eventTime - taskStart) / 1000)
    videoRef.current.currentTime = offsetSec
    videoRef.current.play().catch(() => {})
  }

  // ── Selected task ──

  const selected = tasks.find((t) => t.id === selectedId) ?? null

  // ── Event type badge color ──

  const badgeStyle = (subType: string) => {
    switch (subType) {
      case 'crowd':
      case 'fight':
        return 'bg-red/12 text-red'
      case 'fall':
        return 'bg-orange/12 text-orange'
      default:
        return 'bg-blue/12 text-blue'
    }
  }

  return (
    <div className="analyze-wrap grid gap-0 grid-cols-1 lg:grid-cols-[260px_1fr] h-[calc(100vh-92px)]">
      {/* ── Left: Task list panel ── */}
      <div className="task-list bg-bg2 border-r border-border flex flex-col overflow-hidden">
        {/* Header */}
        <div className="task-list-h flex items-center justify-between px-3 py-2.5 border-b border-border">
          <h3 className="text-xs font-semibold text-t3">Analysis Tasks</h3>
          <label
            className={`btn-upload inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-green text-bg text-[11px] font-semibold cursor-pointer hover:opacity-85 transition-opacity duration-150 ${uploading ? 'opacity-50 pointer-events-none' : ''}`}
          >
            <Upload size={12} />
            {uploading ? 'Uploading...' : 'Upload'}
            <input
              ref={fileInputRef}
              type="file"
              accept="video/*"
              className="hidden"
              onChange={handleFileChange}
              disabled={uploading}
            />
          </label>
        </div>

        {/* Error banner */}
        {error && (
          <div className="mx-2 mt-2 px-2 py-1.5 rounded-md bg-red/10 border border-red/20 text-red text-[11px]">
            {error}
          </div>
        )}

        {/* Task items */}
        <div className="flex-1 overflow-y-auto">
          {tasks.map((task) => (
            <div
              key={task.id}
              onClick={() => setSelectedId(task.id)}
              className={`task-item px-3 py-2.5 border-b border-border/50 cursor-pointer transition-colors duration-150 ${
                selectedId === task.id
                  ? 'active bg-green/8'
                  : 'hover:bg-card'
              }`}
            >
              <div className="task-row flex items-center gap-1.5 mb-0.5">
                <span className="task-name text-xs font-medium text-t1 truncate flex-1">
                  {task.filename}
                </span>
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    handleDelete(task.id)
                  }}
                  className="text-t3 hover:text-red cursor-pointer transition-colors duration-150 flex-shrink-0"
                  aria-label={`Delete task ${task.filename}`}
                >
                  <Trash2 size={12} />
                </button>
              </div>
              <div className="task-meta flex justify-between text-[10px] text-t3">
                <span className={statusColor(task.status)}>
                  {statusLabel(task.status)}
                </span>
                <span>{formatFileSize(task.file_size)}</span>
              </div>
              <div className="text-[9px] text-t3 mt-0.5">
                {formatDate(task.created_at)}
              </div>
              {task.status === 'processing' && (
                <div className="task-progress h-[3px] bg-border rounded-sm mt-1 overflow-hidden">
                  <div
                    className="task-progress-bar h-full bg-blue rounded-sm"
                    style={{
                      width: task.progress != null ? `${task.progress}%` : '100%',
                      animation: 'pulse 1.5s infinite',
                    }}
                  />
                </div>
              )}
            </div>
          ))}

          {tasks.length === 0 && (
            <div className="text-center py-8 text-t3 text-[11px]">
              No analysis tasks yet.
            </div>
          )}
        </div>
      </div>

      {/* ── Right: Task detail area ── */}
      <div className="task-detail overflow-y-auto p-4">
        {!selected ? (
          /* Empty state */
          <div className="flex flex-col items-center justify-center h-full gap-4">
            <Video size={48} className="text-t3" strokeWidth={1.5} />
            <p className="text-t2 text-sm text-center">
              Upload a video file for offline behavior analysis
              <br />
              <span className="text-t3 text-xs">
                Supports detection of crowd gathering, fighting, falling, and other anomalies
              </span>
            </p>
            <label className="btn-upload-lg inline-flex items-center gap-1.5 px-5 py-2 rounded-lg bg-green text-bg text-xs font-semibold cursor-pointer hover:opacity-85 transition-opacity duration-150">
              <Upload size={14} />
              Upload Video
              <input
                type="file"
                accept="video/*"
                className="hidden"
                onChange={handleFileChange}
                disabled={uploading}
              />
            </label>
          </div>
        ) : selected.status === 'waiting_config' ? (
          /* Waiting Config: show first frame + start button */
          <div>
            <div className="detail-header flex justify-between items-start mb-3.5">
              <div>
                <div className="detail-title text-sm font-semibold flex items-center gap-1.5">
                  <Video size={16} className="text-green" />
                  {selected.filename}
                </div>
                <div className="detail-meta text-[11px] text-t3 mt-0.5">
                  {formatFileSize(selected.file_size)} · {formatDate(selected.created_at)}
                </div>
              </div>
            </div>

            {/* First frame preview */}
            <div className="w-full aspect-video rounded-lg overflow-hidden border border-border bg-black mb-3.5">
              <img
                src={getTaskFirstFrameUrl(selected.id)}
                alt="Video first frame"
                className="w-full h-full object-contain"
              />
            </div>

            <button
              onClick={handleStart}
              disabled={starting}
              className="w-full py-2.5 rounded-lg bg-green text-bg text-xs font-semibold cursor-pointer hover:opacity-85 transition-opacity duration-150 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {starting ? 'Starting...' : 'Start Analysis'}
            </button>
          </div>
        ) : selected.status === 'processing' ? (
          /* Processing: show progress info */
          <div className="flex flex-col items-center justify-center h-full gap-4">
            <Activity size={40} className="text-blue animate-pulse" />
            <div className="text-center">
              <p className="text-t1 text-sm font-medium">{selected.filename}</p>
              <p className="text-t3 text-xs mt-1">
                Analyzing...{' '}
                {selected.progress != null && (
                  <span className="font-mono text-blue">{selected.progress}%</span>
                )}
              </p>
            </div>
            <div className="w-64 h-1.5 bg-border rounded-full overflow-hidden">
              <div
                className="h-full bg-blue rounded-full transition-all duration-300"
                style={{
                  width: selected.progress != null ? `${selected.progress}%` : '100%',
                  animation:
                    selected.progress == null ? 'pulse 1.5s infinite' : undefined,
                }}
              />
            </div>
          </div>
        ) : selected.status === 'completed' ? (
          /* Completed: video player + anomaly banner + stats + timeline */
          <div>
            {/* Header with download */}
            <div className="detail-header flex justify-between items-start mb-3.5">
              <div>
                <div className="detail-title text-sm font-semibold flex items-center gap-1.5">
                  <Video size={16} className="text-green" />
                  {selected.filename}
                </div>
                <div className="detail-meta text-[11px] text-t3 mt-0.5">
                  {formatFileSize(selected.file_size)} · {formatDate(selected.created_at)}
                </div>
              </div>
              <a
                href={getTaskVideoUrl(selected.id)}
                download
                className="btn-dl inline-flex items-center gap-1 px-2.5 py-1.5 rounded-md bg-card text-t2 border border-border text-[11px] cursor-pointer hover:text-t1 hover:border-hover transition-colors duration-150"
              >
                <Download size={12} />
                Download
              </a>
            </div>

            {/* Video player */}
            <div className="video-player w-full aspect-video rounded-lg overflow-hidden border border-border bg-black mb-3.5">
              <video
                ref={videoRef}
                src={getTaskVideoUrl(selected.id)}
                controls
                className="w-full h-full"
              />
            </div>

            {/* Anomaly banner */}
            {selected.events && selected.events.length > 0 && (
              <div className="anomaly-banner bg-red/8 border border-red/15 rounded-lg p-3 mb-3.5">
                <div className="anomaly-banner-h flex items-center gap-1.5 text-xs font-semibold mb-2">
                  <AlertTriangle size={14} className="text-red" />
                  <span className="text-red">Anomaly Events Detected</span>
                </div>
                <div className="anomaly-tags flex gap-1.5 flex-wrap">
                  {Object.entries(countByType(selected.events)).map(
                    ([type, count]) => (
                      <span
                        key={type}
                        className="atag inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-bg2 border border-border text-[11px] text-t2"
                      >
                        <span className={`badge font-mono text-[10px] font-medium uppercase ${badgeStyle(type)} px-1.5 py-0.5 rounded`}>
                          {type}
                        </span>
                        <span className="atag-v text-[13px] font-bold text-t1">
                          {count}
                        </span>
                      </span>
                    ),
                  )}
                </div>
              </div>
            )}

            {/* Stats cards */}
            {selected.stats && (
              <div className="analyze-stats grid grid-cols-1 sm:grid-cols-3 gap-2 mb-3.5">
                <div className="astat p-3 rounded-lg bg-bg2 border border-border">
                  <div className="astat-h flex items-center gap-1 text-[10px] text-t3 mb-1">
                    <Users size={12} />
                    Person Stats
                  </div>
                  <div className="astat-v font-mono text-[22px] font-semibold text-t1">
                    {selected.stats.max_persons}
                  </div>
                  <div className="astat-sub text-[9px] text-t3 mt-0.5">
                    max · avg {selected.stats.avg_persons.toFixed(1)}
                  </div>
                </div>

                <div className="astat p-3 rounded-lg bg-bg2 border border-border">
                  <div className="astat-h flex items-center gap-1 text-[10px] text-t3 mb-1">
                    <LayoutGrid size={12} />
                    Detections
                  </div>
                  <div className="astat-v font-mono text-[22px] font-semibold text-t1">
                    {selected.stats.total_detections}
                  </div>
                  <div className="astat-sub text-[9px] text-t3 mt-0.5">
                    total detections
                  </div>
                </div>

                <div className="astat p-3 rounded-lg bg-bg2 border border-border">
                  <div className="astat-h flex items-center gap-1 text-[10px] text-t3 mb-1">
                    <Clock size={12} />
                    Duration
                  </div>
                  <div className="astat-v font-mono text-[22px] font-semibold text-t1">
                    {formatSeconds(selected.stats.duration)}
                  </div>
                  <div className="astat-sub text-[9px] text-t3 mt-0.5">
                    {selected.stats.total_frames} frames
                  </div>
                </div>
              </div>
            )}

            {/* Event timeline */}
            {selected.events && selected.events.length > 0 && (
              <div className="timeline-section bg-bg2 rounded-lg border border-border overflow-hidden">
                <div className="timeline-h px-3.5 py-2.5 text-xs font-semibold flex items-center gap-1.5 border-b border-border">
                  <Activity size={12} />
                  Event Timeline
                  <span className="ml-auto font-mono text-[10px] text-t3 font-normal">
                    {selected.events.length} events
                  </span>
                </div>
                <div className="timeline-list max-h-60 overflow-y-auto">
                  {selected.events.map((ev, idx) => (
                    <div
                      key={`${ev.timestamp}-${idx}`}
                      onClick={() => seekToTime(ev.timestamp)}
                      className="tl-item flex items-center gap-2 px-3.5 py-2 border-b border-border/30 text-[11px] cursor-pointer transition-colors duration-150 hover:bg-card"
                    >
                      <span className="tl-time font-mono text-green text-[10px] w-12 flex-shrink-0">
                        {new Date(ev.timestamp).toLocaleTimeString('en-US', {
                          hour12: false,
                          hour: '2-digit',
                          minute: '2-digit',
                          second: '2-digit',
                        })}
                      </span>
                      <span
                        className={`badge font-mono text-[10px] font-medium uppercase px-1.5 py-0.5 rounded ${badgeStyle(ev.sub_type)}`}
                      >
                        {ev.sub_type}
                      </span>
                      <span className="tl-detail text-t2 overflow-hidden text-ellipsis whitespace-nowrap">
                        {ev.detail}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          /* Failed or unknown status */
          <div className="flex flex-col items-center justify-center h-full gap-3">
            <AlertTriangle size={40} className="text-red" />
            <p className="text-t2 text-sm">Analysis failed</p>
            <p className="text-t3 text-xs">{selected.filename}</p>
          </div>
        )}
      </div>
    </div>
  )
}
