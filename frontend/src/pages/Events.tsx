import { useEffect, useState, useMemo } from 'react'
import { Image } from 'lucide-react'
import { getEvents } from '../api'
import { filterEvents, paginateEvents, formatTimestamp } from '../utils'
import ImageModal from '../components/ImageModal'
import type { DetectionEvent } from '../types'

const PAGE_SIZE = 20
const FILTER_TYPES = ['all', 'crowd', 'fight', 'fall'] as const

/** Gradient background class per event sub_type */
function thumbBgClass(subType: string): string {
  switch (subType) {
    case 'crowd':
      return 'bg-gradient-to-br from-[#1a0a0a] to-[#2a1020]'
    case 'fight':
      return 'bg-gradient-to-br from-[#1a0a0a] to-[#2a0a1a]'
    case 'fall':
      return 'bg-gradient-to-br from-[#1a1000] to-[#2a1a0a]'
    default:
      return 'bg-gradient-to-br from-[#0a0a1a] to-[#1a1a2e]'
  }
}

/** Badge colour classes per event sub_type */
function badgeClass(subType: string): string {
  switch (subType) {
    case 'crowd':
      return 'bg-red/12 text-red'
    case 'fight':
      return 'bg-red/12 text-red'
    case 'fall':
      return 'bg-orange/12 text-orange'
    default:
      return 'bg-blue/12 text-blue'
  }
}

export default function Events() {
  const [events, setEvents] = useState<DetectionEvent[]>([])
  const [filter, setFilter] = useState<string>('all')
  const [page, setPage] = useState(1)
  const [modalEvent, setModalEvent] = useState<DetectionEvent | null>(null)
  const [loading, setLoading] = useState(true)

  // Fetch events once on mount
  useEffect(() => {
    let cancelled = false
    setLoading(true)
    getEvents({ limit: 500 })
      .then((data) => {
        if (!cancelled) setEvents(data)
      })
      .catch(() => {
        /* silently handle — empty list shown */
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  // Reset to page 1 when filter changes
  useEffect(() => {
    setPage(1)
  }, [filter])

  const filtered = useMemo(() => filterEvents(events, filter), [events, filter])
  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const pageEvents = useMemo(() => paginateEvents(filtered, page, PAGE_SIZE), [filtered, page])

  const showStart = filtered.length === 0 ? 0 : (page - 1) * PAGE_SIZE + 1
  const showEnd = Math.min(page * PAGE_SIZE, filtered.length)

  /** Build page number buttons (max 5 visible) */
  const pageNumbers = useMemo(() => {
    const pages: number[] = []
    let start = Math.max(1, page - 2)
    let end = Math.min(totalPages, start + 4)
    if (end - start < 4) start = Math.max(1, end - 4)
    for (let i = start; i <= end; i++) pages.push(i)
    return pages
  }, [page, totalPages])

  return (
    <div>
      {/* Filter chips */}
      <div className="flex flex-wrap gap-1.5 mb-3.5">
        {FILTER_TYPES.map((t) => (
          <button
            key={t}
            onClick={() => setFilter(t)}
            className={`px-3 py-1.5 rounded-2xl text-[11px] font-medium border cursor-pointer transition-all duration-150 ${
              filter === t
                ? 'bg-green text-bg border-green'
                : 'bg-card text-t3 border-border hover:text-t2 hover:border-hover'
            }`}
          >
            {t === 'all' ? 'All' : t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
        <span className="ml-auto text-[11px] text-t3 self-center">
          {filtered.length} events
        </span>
      </div>

      {/* Events table */}
      <div className="bg-bg2 rounded-lg border border-border overflow-hidden">
        <table className="w-full text-xs border-collapse">
          <thead>
            <tr className="bg-card">
              <th className="text-left px-3.5 py-2 text-[10px] font-semibold text-t3 uppercase tracking-wider w-20">
                Screenshot
              </th>
              <th className="text-left px-3.5 py-2 text-[10px] font-semibold text-t3 uppercase tracking-wider">
                Time
              </th>
              <th className="text-left px-3.5 py-2 text-[10px] font-semibold text-t3 uppercase tracking-wider">
                Type
              </th>
              <th className="text-left px-3.5 py-2 text-[10px] font-semibold text-t3 uppercase tracking-wider">
                Camera
              </th>
              <th className="text-left px-3.5 py-2 text-[10px] font-semibold text-t3 uppercase tracking-wider">
                Detail
              </th>
              <th className="text-left px-3.5 py-2 text-[10px] font-semibold text-t3 uppercase tracking-wider">
                Track ID
              </th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={6} className="px-3.5 py-8 text-center text-t3 text-[11px]">
                  Loading…
                </td>
              </tr>
            )}
            {!loading && pageEvents.length === 0 && (
              <tr>
                <td colSpan={6} className="px-3.5 py-8 text-center text-t3 text-[11px]">
                  No events
                </td>
              </tr>
            )}
            {pageEvents.map((ev, idx) => (
              <tr
                key={`${ev.timestamp}-${ev.camera_id}-${idx}`}
                className="cursor-pointer transition-colors duration-150 hover:bg-card"
              >
                {/* Thumbnail */}
                <td className="px-3.5 py-2.5 border-t border-border">
                  <div
                    className={`w-16 h-9 rounded flex items-center justify-center cursor-pointer transition-opacity duration-150 hover:opacity-80 ${thumbBgClass(ev.sub_type)}`}
                    onClick={() => ev.image && setModalEvent(ev)}
                  >
                    {ev.image ? (
                      <img
                        src={`/events/${ev.image}`}
                        alt={`${ev.sub_type} event`}
                        className="w-full h-full object-cover rounded"
                      />
                    ) : (
                      <Image size={16} className="text-white/50" />
                    )}
                  </div>
                </td>
                {/* Time */}
                <td className="px-3.5 py-2.5 border-t border-border font-mono text-[11px] text-t2">
                  {formatTimestamp(ev.timestamp)}
                </td>
                {/* Type badge */}
                <td className="px-3.5 py-2.5 border-t border-border">
                  <span
                    className={`inline-block px-1.5 py-0.5 rounded font-mono text-[10px] font-medium uppercase ${badgeClass(ev.sub_type)}`}
                  >
                    {ev.sub_type}
                  </span>
                </td>
                {/* Camera */}
                <td className="px-3.5 py-2.5 border-t border-border text-t2">
                  {ev.camera_id}
                </td>
                {/* Detail */}
                <td className="px-3.5 py-2.5 border-t border-border text-t2">
                  {ev.detail}
                </td>
                {/* Track IDs */}
                <td className="px-3.5 py-2.5 border-t border-border text-t2">
                  {(ev.track_ids ?? []).map((id) => `#${id}`).join(',') || '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex justify-between items-center mt-3 text-[11px] text-t3">
        <span>
          Showing {showStart}-{showEnd} of {filtered.length}
        </span>
        <div className="flex gap-1">
          {pageNumbers.map((p) => (
            <button
              key={p}
              onClick={() => setPage(p)}
              className={`px-2.5 py-1 rounded text-[11px] border cursor-pointer transition-all duration-150 ${
                p === page
                  ? 'bg-green text-bg border-green'
                  : 'bg-card text-t2 border-border hover:text-t1 hover:border-hover'
              }`}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {/* Image modal */}
      <ImageModal event={modalEvent} onClose={() => setModalEvent(null)} />
    </div>
  )
}
