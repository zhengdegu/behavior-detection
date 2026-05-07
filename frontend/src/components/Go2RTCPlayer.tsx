import { useRef } from 'react'

interface Go2RTCPlayerProps {
  /** Camera stream name (e.g. cam01) */
  src: string
  /** Called when the video element has loaded data */
  onVideoReady?: (video: HTMLVideoElement) => void
  /** Called on connection error */
  onError?: (error: string) => void
  className?: string
}

export default function Go2RTCPlayer({
  src,
  className,
}: Go2RTCPlayerProps) {
  const iframeRef = useRef<HTMLIFrameElement>(null)

  // Build go2rtc player URL
  // Production: use backend reverse proxy (same origin) for HTTP resources,
  // but go2rtc stream.html handles its own WebSocket connections internally.
  // Development: use go2rtc directly via configured port
  const isDev = window.location.port === '5173'
  let playerUrl: string
  if (isDev) {
    const go2rtcPort = import.meta.env.VITE_GO2RTC_PORT || '1984'
    playerUrl = `http://${window.location.hostname}:${go2rtcPort}/stream.html?src=${encodeURIComponent(src)}&mode=mse,webrtc`
  } else {
    playerUrl = `/go2rtc/stream.html?src=${encodeURIComponent(src)}&mode=mse,webrtc`
  }

  return (
    <iframe
      ref={iframeRef}
      src={playerUrl}
      className={className}
      style={{ width: '100%', height: '100%', border: 'none' }}
      allow="autoplay"
    />
  )
}
