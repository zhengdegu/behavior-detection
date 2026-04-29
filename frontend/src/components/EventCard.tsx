import type { DetectionEvent } from '../types'
import { getEventColor, formatTimestamp } from '../utils'

interface EventCardProps {
  event: DetectionEvent
}

export default function EventCard({ event }: EventCardProps) {
  const color = getEventColor(event.sub_type)

  const borderClass =
    color === 'red'
      ? 'border-l-red'
      : color === 'orange'
        ? 'border-l-orange'
        : 'border-l-blue'

  const textClass =
    color === 'red'
      ? 'text-red'
      : color === 'orange'
        ? 'text-orange'
        : 'text-blue'

  return (
    <div
      className={`p-2.5 rounded-md bg-card border-l-3 ${borderClass} cursor-pointer transition-colors duration-150 hover:bg-hover`}
    >
      <div className={`font-mono text-[10px] font-semibold uppercase ${textClass}`}>
        {event.sub_type}
      </div>
      <div className="text-[11px] text-t2 mt-0.5">{event.detail}</div>
      <div className="font-mono text-[9px] text-t3 mt-1">
        {formatTimestamp(event.timestamp)}
      </div>
    </div>
  )
}
