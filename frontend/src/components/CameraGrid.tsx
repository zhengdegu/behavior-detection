import type { Camera } from '../types'
import { getGridColumns } from '../utils'
import CameraStream from './CameraStream'

interface CameraGridProps {
  cameras: Camera[]
  alertCameraIds: Set<string>
}

/** Static mapping so Tailwind can detect the classes at build time */
const gridColsClass: Record<number, string> = {
  1: 'grid-cols-1 md:grid-cols-1',
  2: 'grid-cols-1 md:grid-cols-2',
  3: 'grid-cols-1 md:grid-cols-3',
}

export default function CameraGrid({ cameras, alertCameraIds }: CameraGridProps) {
  const cols = getGridColumns(cameras.length)

  return (
    <div className={`grid gap-2 ${gridColsClass[cols] ?? 'grid-cols-1 md:grid-cols-3'}`}>
      {cameras.map((camera) => (
        <CameraStream
          key={camera.id}
          camera={camera}
          isAlert={alertCameraIds.has(camera.id)}
        />
      ))}
    </div>
  )
}
