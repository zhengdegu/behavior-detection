import { useEffect, useRef, useState } from 'react'
import { Video } from 'lucide-react'

interface Go2RTCPlayerProps {
  /** go2rtc WebSocket URL, e.g. /go2rtc/ws?src=cam01 */
  src: string
  /** Called when the video element has loaded data */
  onVideoReady?: (video: HTMLVideoElement) => void
  /** Called on connection error */
  onError?: (error: string) => void
  className?: string
}

/** Track whether the VideoRTC custom element has been registered */
let registered = false
let registering = false
const callbacks: Array<(ok: boolean) => void> = []

function ensureVideoRTCRegistered(): Promise<boolean> {
  if (registered) return Promise.resolve(true)

  return new Promise((resolve) => {
    callbacks.push(resolve)
    if (registering) return

    registering = true

    // Load video-rtc.js as ES module and register the custom element
    const script = document.createElement('script')
    script.type = 'module'
    script.textContent = `
      import {VideoRTC} from '/go2rtc/video-rtc.js';
      if (!customElements.get('video-rtc')) {
        customElements.define('video-rtc', VideoRTC);
      }
      window.__go2rtc_ready = true;
      window.dispatchEvent(new Event('go2rtc-ready'));
    `
    document.head.appendChild(script)

    const onReady = () => {
      window.removeEventListener('go2rtc-ready', onReady)
      registered = true
      registering = false
      callbacks.forEach((cb) => cb(true))
      callbacks.length = 0
    }
    window.addEventListener('go2rtc-ready', onReady)

    // Timeout fallback
    setTimeout(() => {
      if (!registered) {
        registering = false
        callbacks.forEach((cb) => cb(false))
        callbacks.length = 0
      }
    }, 5000)
  })
}

export default function Go2RTCPlayer({
  src,
  onVideoReady,
  onError,
  className,
}: Go2RTCPlayerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const elementRef = useRef<HTMLElement | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    let cancelled = false

    async function init() {
      const ok = await ensureVideoRTCRegistered()
      if (cancelled) return

      if (!ok) {
        setError(true)
        onError?.('Failed to load video-rtc.js')
        return
      }

      const container = containerRef.current
      if (!container) return

      // Create the <video-rtc> custom element
      const el = document.createElement('video-rtc') as HTMLElement & { src: string }
      // Set src via property (triggers the setter which starts connection)
      el.style.width = '100%'
      el.style.height = '100%'
      el.style.display = 'block'

      container.appendChild(el)
      elementRef.current = el

      // Wait for the internal video element to appear, then set src
      const observer = new MutationObserver(() => {
        const video = el.querySelector('video')
        if (video) {
          video.style.objectFit = 'cover'
          video.addEventListener('loadeddata', () => {
            if (!cancelled) {
              setError(false)
              onVideoReady?.(video)
            }
          })
          observer.disconnect()
        }
      })
      observer.observe(el, { childList: true, subtree: true })

      // Build go2rtc URL — connect directly to go2rtc port (1984)
      // In production (Docker), go2rtc runs on the same host, port 1984
      // In development, Vite proxy forwards /go2rtc/* to localhost:1984
      const go2rtcPort = import.meta.env.VITE_GO2RTC_PORT || '1988'
      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const go2rtcHost = window.location.hostname
      const wsUrl = `${wsProtocol}//${go2rtcHost}:${go2rtcPort}/api/ws?src=${encodeURIComponent(src)}`
      el.src = wsUrl
    }

    init()

    return () => {
      cancelled = true
      const container = containerRef.current
      if (elementRef.current && container?.contains(elementRef.current)) {
        container.removeChild(elementRef.current)
      }
      elementRef.current = null
    }
  }, [src, onVideoReady, onError])

  if (error) {
    return (
      <div
        className={`flex flex-col items-center justify-center bg-[#111827] text-t3 text-[11px] gap-1.5 ${className ?? ''}`}
      >
        <Video size={40} strokeWidth={1.5} className="text-hover" />
        <span className="text-[#374151]">Video connection failed</span>
      </div>
    )
  }

  return <div ref={containerRef} className={className} />
}
