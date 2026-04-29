import { useRef } from 'react'
import { Video } from 'lucide-react'
import type { Camera } from '../types'
import Go2RTCPlayer from './Go2RTCPlayer'
import DetectionOverlay from './DetectionOverlay'

interface CameraStreamProps {
  camera: Camera
  isAlert: boolean
}

export default function CameraStream({ camera, isAlert }: CameraStreamProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const isOnline = camera.online !== false
  const playerUrl = camera.id

  return (
    <div
      className={`relative aspect-video rounded-lg bg-bg2 border overflow-hidden cursor-pointer transition-[border-color] duration-150 ${
        isAlert
          ? 'border-red'
          : 'border-border hover:border-hover'
      }`}
      style={isAlert ? { animation: 'alert-pulse 1s infinite' } : undefined}
    >
      {isOnline ? (
        <>
          <div ref={containerRef} className="relative w-full h-full">
            <Go2RTCPlayer src={playerUrl} className="w-full h-full object-cover" />
            <DetectionOverlay cameraId={camera.id} containerRef={containerRef} />
          </div>
          {/* Camera name label */}
          <div className="absolute top-2 left-2 px-2 py-0.5 rounded bg-black/60 font-mono text-[10px] text-t2">
            {camera.id} · {camera.name}
          </div>
          {/* Status dot — online green */}
          <div
            className="absolute top-2 right-2 w-[7px] h-[7px] rounded-full bg-green"
            style={{ animation: 'dot-pulse 2s infinite' }}
          />
        </>
      ) : (
        <>
          {/* Offline placeholder */}
          <div className="w-full h-full flex flex-col items-center justify-center text-t3 text-[11px] gap-1.5 bg-[#111827]">
            <Video size={40} strokeWidth={1.5} className="text-hover" />
            <span className="text-[#374151]">Offline</span>
          </div>
          {/* Camera name label */}
          <div className="absolute top-2 left-2 px-2 py-0.5 rounded bg-black/60 font-mono text-[10px] text-t2">
            {camera.id} · {camera.name}
          </div>
          {/* Status dot — offline red */}
          <div className="absolute top-2 right-2 w-[7px] h-[7px] rounded-full bg-red" />
        </>
      )}
    </div>
  )
}
