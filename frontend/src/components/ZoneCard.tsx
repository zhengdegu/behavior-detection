import { Trash2 } from 'lucide-react'
import RoiEditor from './RoiEditor'
import type { ZoneConfig, RoiPolygon } from '../types'

export interface ZoneCardProps {
  index: number
  zone: ZoneConfig
  ruleType: 'crowd' | 'fight' | 'fall' | 'loiter'
  defaults: Record<string, number>
  cameraId: string
  onChange: (zone: ZoneConfig) => void
  onDelete: () => void
}

// ── Parameter definitions per rule type ──

interface ParamDef {
  key: string
  label: string
  unit?: string
  step?: number
}

const COMMON_PARAMS: ParamDef[] = [
  { key: 'confirm_frames', label: 'confirm_frames' },
  { key: 'cooldown', label: 'cooldown', unit: 's' },
]

const RULE_PARAMS: Record<string, ParamDef[]> = {
  crowd: [
    { key: 'max_count', label: 'max_count' },
    { key: 'radius', label: 'radius', unit: 'px' },
  ],
  fight: [
    { key: 'proximity_radius', label: 'proximity_radius', unit: 'px' },
    { key: 'min_speed', label: 'min_speed', unit: 'px/s' },
    { key: 'min_persons', label: 'min_persons' },
    { key: 'co_move_cos_threshold', label: 'co_move_cos_threshold', step: 0.01 },
    { key: 'min_relative_speed', label: 'min_relative_speed', unit: 'px/s' },
    { key: 'min_distance_variance', label: 'min_distance_variance', unit: 'px²' },
    { key: 'joint_overlap_threshold', label: 'joint_overlap_threshold' },
  ],
  fall: [
    { key: 'ratio_threshold', label: 'ratio_threshold', step: 0.01 },
    { key: 'min_ratio_change', label: 'min_ratio_change', step: 0.01 },
    { key: 'min_y_drop', label: 'min_y_drop', unit: 'px' },
    { key: 'min_hip_velocity', label: 'min_hip_velocity', unit: 'px/f' },
    { key: 'spine_angle_threshold', label: 'spine_angle_threshold', unit: '°' },
    { key: 'inactivity_frames', label: 'inactivity_frames' },
    { key: 'inactivity_threshold', label: 'inactivity_threshold', unit: 'px' },
    { key: 'history_size', label: 'history_size' },
  ],
  loiter: [
    { key: 'min_duration', label: 'min_duration', unit: 's' },
    { key: 'max_distance', label: 'max_distance', unit: 'px' },
    { key: 'max_displacement_ratio', label: 'max_disp_ratio', step: 0.01 },
    { key: 'min_total_path', label: 'min_total_path', unit: 'px' },
    { key: 'trajectory_window', label: 'trajectory_window', unit: 's' },
    { key: 'inertia', label: 'inertia' },
  ],
}

// ── Zone parameter field with inheritance visual hint ──
// Inherited (undefined): dashed border, lighter text, placeholder shows rule default
// Overridden (has value): solid border, normal text — matches RuleForm Field style

function ZoneField({
  label,
  value,
  defaultValue,
  unit,
  step,
  onChange,
}: {
  label: string
  value: number | undefined
  defaultValue: number | undefined
  unit?: string
  step?: number
  onChange: (v: number | undefined) => void
}) {
  const isOverridden = value !== undefined

  return (
    <div className="flex flex-col gap-1">
      <label className="text-[10px] text-t3 font-medium">{label}</label>
      <input
        type="number"
        data-testid={`zone-field-${label}`}
        data-inherited={!isOverridden}
        value={isOverridden ? value : ''}
        placeholder={defaultValue !== undefined ? String(defaultValue) : '—'}
        step={step ?? 1}
        onChange={(e) => {
          const raw = e.target.value
          if (raw === '') {
            onChange(undefined)
          } else {
            onChange(Number(raw))
          }
        }}
        className={
          isOverridden
            ? 'px-2 py-1.5 rounded-md bg-card text-t1 border border-border font-mono text-[11px] outline-none w-full focus:border-green transition-colors duration-150'
            : 'px-2 py-1.5 rounded-md bg-card text-t3 border border-dashed border-border/60 font-mono text-[11px] outline-none w-full placeholder:text-t3/70 focus:border-green transition-colors duration-150'
        }
      />
      {unit && <span className="text-[9px] text-t3">{unit}</span>}
    </div>
  )
}

// ── ZoneCard component ──

export default function ZoneCard({
  index,
  zone,
  ruleType,
  defaults,
  cameraId,
  onChange,
  onDelete,
}: ZoneCardProps) {
  const params = [...(RULE_PARAMS[ruleType] || []), ...COMMON_PARAMS]

  const handleNameChange = (name: string) => {
    onChange({ ...zone, name: name || undefined })
  }

  const handleRoiChange = (polygons: RoiPolygon[]) => {
    // singleMode: take only the first polygon (or empty)
    onChange({ ...zone, roi: polygons[0] ?? [] })
  }

  const handleParamChange = (key: string, value: number | undefined) => {
    onChange({ ...zone, [key]: value })
  }

  return (
    <div className="p-3 rounded-lg bg-base border border-border/60">
      {/* Header: Zone title + name input + delete */}
      <div className="flex items-center gap-2 mb-2">
        <span className="text-[11px] font-semibold text-t2 shrink-0">
          Zone {index + 1}
        </span>
        <input
          type="text"
          value={zone.name ?? ''}
          onChange={(e) => handleNameChange(e.target.value)}
          placeholder="Zone name (optional)"
          className="flex-1 px-2 py-1 rounded-md bg-card text-t1 border border-border text-[11px] outline-none placeholder:text-t3/60 focus:border-green transition-colors duration-150"
        />
        <button
          type="button"
          onClick={onDelete}
          className="p-1 rounded text-t3 hover:text-red hover:bg-red/10 cursor-pointer transition-colors duration-150"
          aria-label={`Delete Zone ${index + 1}`}
        >
          <Trash2 size={12} />
        </button>
      </div>

      {/* ROI Editor (singleMode) */}
      <div className="mb-2">
        <RoiEditor
          cameraId={cameraId}
          initialPolygons={zone.roi.length >= 3 ? [zone.roi] : []}
          onPolygonsChange={handleRoiChange}
          singleMode={true}
          labels={zone.name ? [zone.name] : undefined}
        />
      </div>

      {/* Parameter override fields */}
      <div className="mt-2 pt-2 border-t border-border/50">
        <div className="text-[10px] text-t3 font-medium mb-1.5">
          Parameter Overrides
        </div>
        <div className="grid grid-cols-2 gap-1.5">
          {params.map((param) => (
            <ZoneField
              key={param.key}
              label={param.label}
              value={(zone as unknown as Record<string, unknown>)[param.key] as number | undefined}
              defaultValue={defaults[param.key]}
              unit={param.unit}
              step={param.step}
              onChange={(v) => handleParamChange(param.key, v)}
            />
          ))}
        </div>
      </div>
    </div>
  )
}
