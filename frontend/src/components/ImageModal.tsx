import type { DetectionEvent } from '../types'
import { getEventColor, formatTimestamp } from '../utils'
import { X } from 'lucide-react'

interface ImageModalProps {
  event: DetectionEvent | null
  onClose: () => void
}

export default function ImageModal({ event, onClose }: ImageModalProps) {
  if (!event) return null

  const color = getEventColor(event.sub_type)
  const textClass =
    color === 'red'
      ? 'text-red'
      : color === 'orange'
        ? 'text-orange'
        : 'text-blue'

  return (
    <div
      className="fixed inset-0 z-200 flex items-center justify-center bg-black/80 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="w-[90%] max-w-[800px] bg-bg2 border border-border rounded-lg overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-3.5 py-2.5 border-b border-border">
          <span className={`text-xs font-semibold uppercase font-mono ${textClass}`}>
            {event.sub_type}
          </span>
          <button
            onClick={onClose}
            className="text-t3 hover:text-t1 cursor-pointer transition-colors duration-150"
          >
            <X size={16} />
          </button>
        </div>

        {/* Body — event screenshot */}
        <div className="p-3">
          <img
            src={`/events/${event.image}`}
            alt={`${event.sub_type} event screenshot`}
            className="w-full rounded-md"
          />
        </div>

        {/* Footer — metadata */}
        <div className="px-3.5 py-2 border-t border-border flex items-center gap-4 text-[11px] text-t3">
          <span className="font-mono">{event.camera_id}</span>
          <span className="font-mono">{formatTimestamp(event.timestamp)}</span>
          <span className="text-t2 truncate">{event.detail}</span>
        </div>
      </div>
    </div>
  )
}
