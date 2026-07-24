import { useState, useEffect, useRef } from 'react'
import type { RulesConfig, ScheduleConfig, TimePeriod, MultiRoi, ZoneConfig } from '../types'
import { Users, Zap, TrendingDown, Clock, Plus, Trash2, Footprints, MapPin } from 'lucide-react'
import RoiEditor from './RoiEditor'
import ZoneCard from './ZoneCard'

interface RuleFormProps {
  rules: RulesConfig
  onChange: (rules: RulesConfig) => void
  cameraId?: string
}

// ── Toggle switch ──

function Toggle({
  checked,
  onChange,
}: {
  checked: boolean
  onChange: (v: boolean) => void
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={`relative w-8 h-[18px] rounded-[9px] cursor-pointer transition-colors duration-150 ${
        checked ? 'bg-green' : 'bg-hover'
      }`}
    >
      <span
        className="absolute top-[2px] left-[2px] w-[14px] h-[14px] rounded-full bg-white transition-transform duration-150"
        style={{ transform: checked ? 'translateX(14px)' : 'translateX(0)' }}
      />
    </button>
  )
}

// ── Number input field ──

function Field({
  label,
  value,
  unit,
  onChange,
  step,
}: {
  label: string
  value: number
  unit?: string
  onChange: (v: number) => void
  step?: number
}) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-[10px] text-t3 font-medium">{label}</label>
      <input
        type="number"
        value={value}
        step={step ?? 1}
        onChange={(e) => onChange(Number(e.target.value))}
        className="px-2 py-1.5 rounded-md bg-card text-t1 border border-border font-mono text-[11px] outline-none w-full focus:border-green transition-colors duration-150"
      />
      {unit && <span className="text-[9px] text-t3">{unit}</span>}
    </div>
  )
}

// ── Section header with icon ──

function SectionHeader({
  icon: Icon,
  label,
  colorClass,
  enabled,
  onToggle,
  collapsed,
  onToggleCollapse,
}: {
  icon: React.ComponentType<{ size?: number }>
  label: string
  colorClass: string
  enabled: boolean
  onToggle: (v: boolean) => void
  collapsed: boolean
  onToggleCollapse: () => void
}) {
  return (
    <div className="flex items-center justify-between">
      <div
        className="flex items-center gap-1.5 text-xs font-semibold cursor-pointer select-none flex-1"
        onClick={onToggleCollapse}
      >
        <span
          className={`w-[18px] h-[18px] rounded flex items-center justify-center ${colorClass}`}
        >
          <Icon size={10} />
        </span>
        {label}
        <span className={`text-[10px] text-t3 transition-transform duration-150 ${collapsed ? '' : 'rotate-90'}`}>
          ▶
        </span>
      </div>
      <Toggle checked={enabled} onChange={onToggle} />
    </div>
  )
}

// ── Day names ──

const DAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

// ── Schedule Editor ──

function ScheduleEditor({
  schedule,
  onChange,
}: {
  schedule: ScheduleConfig
  onChange: (s: ScheduleConfig) => void
}) {
  const addPeriod = () => {
    onChange({
      ...schedule,
      periods: [
        ...schedule.periods,
        { start: '08:00', end: '18:00', days: [0, 1, 2, 3, 4, 5, 6] },
      ],
    })
  }

  const removePeriod = (index: number) => {
    onChange({
      ...schedule,
      periods: schedule.periods.filter((_, i) => i !== index),
    })
  }

  const updatePeriod = (index: number, patch: Partial<TimePeriod>) => {
    onChange({
      ...schedule,
      periods: schedule.periods.map((p, i) =>
        i === index ? { ...p, ...patch } : p,
      ),
    })
  }

  const toggleDay = (periodIndex: number, day: number) => {
    const period = schedule.periods[periodIndex]
    const days = period.days.includes(day)
      ? period.days.filter((d) => d !== day)
      : [...period.days, day].sort()
    updatePeriod(periodIndex, { days })
  }

  return (
    <div className="mt-2 pt-2 border-t border-border/50">
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-1 text-[10px] text-t3 font-medium">
          <Clock size={10} />
          Detection Schedule
        </div>
        <Toggle
          checked={schedule.enabled}
          onChange={(v) => onChange({ ...schedule, enabled: v })}
        />
      </div>

      {schedule.enabled && (
        <div className="space-y-2">
          <p className="text-[9px] text-t3">
            Only detect during these time periods:
          </p>

          {schedule.periods.map((period, idx) => (
            <div
              key={idx}
              className="p-1.5 rounded-md bg-base border border-border/50"
            >
              <div className="flex items-center gap-1.5 mb-1.5">
                <input
                  type="time"
                  value={period.start}
                  onChange={(e) =>
                    updatePeriod(idx, { start: e.target.value })
                  }
                  className="px-1.5 py-1 rounded bg-card text-t1 border border-border font-mono text-[10px] outline-none focus:border-green transition-colors duration-150"
                />
                <span className="text-[10px] text-t3">—</span>
                <input
                  type="time"
                  value={period.end}
                  onChange={(e) =>
                    updatePeriod(idx, { end: e.target.value })
                  }
                  className="px-1.5 py-1 rounded bg-card text-t1 border border-border font-mono text-[10px] outline-none focus:border-green transition-colors duration-150"
                />
                <button
                  type="button"
                  onClick={() => removePeriod(idx)}
                  className="ml-auto p-0.5 rounded text-t3 hover:text-red hover:bg-red/10 cursor-pointer transition-colors duration-150"
                  aria-label="Remove period"
                >
                  <Trash2 size={10} />
                </button>
              </div>
              <div className="flex gap-0.5">
                {DAY_LABELS.map((label, dayIdx) => (
                  <button
                    key={dayIdx}
                    type="button"
                    onClick={() => toggleDay(idx, dayIdx)}
                    className={`px-1 py-0.5 rounded text-[8px] font-medium cursor-pointer transition-colors duration-150 ${
                      period.days.includes(dayIdx)
                        ? 'bg-green/20 text-green'
                        : 'bg-hover text-t3'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
          ))}

          <button
            type="button"
            onClick={addPeriod}
            className="flex items-center gap-1 text-[10px] text-green hover:text-green/80 cursor-pointer transition-colors duration-150"
          >
            <Plus size={10} />
            Add time period
          </button>
        </div>
      )}
    </div>
  )
}

// ── Rule-level ROI Section ──

function RuleRoiSection({
  cameraId,
  roi,
  onChange,
}: {
  cameraId?: string
  roi: MultiRoi
  onChange: (roi: MultiRoi) => void
}) {
  const [useCustom, setUseCustom] = useState(roi.length > 0)

  // Sync toggle state when camera changes (roi prop resets)
  useEffect(() => {
    setUseCustom(roi.length > 0)
  }, [cameraId])

  // Don't render ROI editor if no camera context (e.g. video analysis)
  if (!cameraId) return null

  return (
    <div className="mt-2 pt-2 border-t border-border/50">
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-1 text-[10px] text-t3 font-medium">
          <MapPin size={10} />
          Custom ROI
        </div>
        <Toggle
          checked={useCustom}
          onChange={(v) => {
            setUseCustom(v)
            if (!v) onChange([])
          }}
        />
      </div>
      {useCustom && (
        <RoiEditor
          cameraId={cameraId}
          initialPolygons={roi}
          onPolygonsChange={onChange}
        />
      )}
      {!useCustom && (
        <p className="text-[9px] text-t3 italic">Using camera global ROI</p>
      )}
    </div>
  )
}

// ── Helper: extract numeric defaults from a rule config ──

function extractDefaults(ruleConfig: object): Record<string, number> {
  const defaults: Record<string, number> = {}
  for (const [key, value] of Object.entries(ruleConfig)) {
    if (typeof value === 'number') {
      defaults[key] = value
    }
  }
  return defaults
}

// ── Zone list section ──

function ZoneListSection({
  zones,
  zonesEnabled,
  ruleType,
  defaults,
  cameraId,
  onChange,
  onToggle,
}: {
  zones: ZoneConfig[]
  zonesEnabled: boolean
  ruleType: 'crowd' | 'fight' | 'fall' | 'loiter'
  defaults: Record<string, number>
  cameraId: string
  onChange: (zones: ZoneConfig[]) => void
  onToggle: (enabled: boolean) => void
}) {
  // Stable keys: assign monotonically increasing IDs to zones
  const keyCounterRef = useRef(0)
  const keysRef = useRef<number[]>([])

  // Sync keys array with zones length
  while (keysRef.current.length < zones.length) {
    keysRef.current.push(keyCounterRef.current++)
  }
  if (keysRef.current.length > zones.length) {
    keysRef.current = keysRef.current.slice(0, zones.length)
  }

  const handleZoneChange = (index: number, zone: ZoneConfig) => {
    const updated = [...zones]
    updated[index] = zone
    onChange(updated)
  }

  const handleZoneDelete = (index: number) => {
    keysRef.current = keysRef.current.filter((_, i) => i !== index)
    onChange(zones.filter((_, i) => i !== index))
  }

  const handleAddZone = () => {
    keysRef.current.push(keyCounterRef.current++)
    onChange([...zones, { roi: [] }])
  }

  return (
    <div className="mt-3 pt-3 border-t border-border/50">
      <div className="flex items-center gap-2 mb-2">
        <div className="text-[10px] text-t3 font-semibold uppercase tracking-wide">
          Zones
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={zonesEnabled}
          aria-label="Toggle zones detection"
          onClick={() => onToggle(!zonesEnabled)}
          className={`relative inline-flex h-4 w-7 shrink-0 items-center rounded-full transition-colors duration-200 cursor-pointer ${zonesEnabled ? 'bg-green' : 'bg-border'}`}
        >
          <span
            className={`inline-block h-3 w-3 rounded-full bg-white shadow-sm transition-transform duration-200 ${zonesEnabled ? 'translate-x-3.5' : 'translate-x-0.5'}`}
          />
        </button>
        <span className="text-[9px] text-t3">
          {zonesEnabled ? 'Zone detection' : 'Full-frame detection'}
        </span>
      </div>
      {zonesEnabled && (
        <>
          <div className="space-y-2">
            {zones.map((zone, idx) => (
              <ZoneCard
                key={keysRef.current[idx] ?? idx}
                index={idx}
                zone={zone}
                ruleType={ruleType}
                defaults={defaults}
                cameraId={cameraId}
                onChange={(z) => handleZoneChange(idx, z)}
                onDelete={() => handleZoneDelete(idx)}
              />
            ))}
          </div>
          <button
            type="button"
            onClick={handleAddZone}
            className="flex items-center gap-1 mt-2 text-[10px] text-green hover:text-green/80 cursor-pointer transition-colors duration-150"
          >
            <Plus size={10} />
            添加 Zone
          </button>
        </>
      )}
    </div>
  )
}

// ── Default schedule ──

const DEFAULT_SCHEDULE: ScheduleConfig = { enabled: false, periods: [] }

export default function RuleForm({ rules, onChange, cameraId }: RuleFormProps) {
  // Collapse state for each section (default: all collapsed)
  const [collapsed, setCollapsed] = useState({
    crowd: true,
    fight: true,
    fall: true,
    loiter: true,
  })

  const toggle = (section: keyof typeof collapsed) => {
    setCollapsed((prev) => ({ ...prev, [section]: !prev[section] }))
  }

  // Helper to update a nested rule section
  function update<K extends keyof RulesConfig>(
    section: K,
    patch: Partial<RulesConfig[K]>,
  ) {
    onChange({
      ...rules,
      [section]: { ...rules[section], ...patch },
    })
  }

  return (
    <div>
      {/* ── Crowd Detection ── */}
      <div className="mb-4 pb-3.5 border-b border-border">
        <SectionHeader
          icon={Users}
          label="Crowd Detection"
          colorClass="bg-red/12 text-red"
          enabled={rules.crowd.enabled}
          onToggle={(v) => update('crowd', { enabled: v })}
          collapsed={collapsed.crowd}
          onToggleCollapse={() => toggle('crowd')}
        />
        {!collapsed.crowd && (
          <div className="mt-2.5">
            <div className="text-[10px] text-t3 font-semibold uppercase tracking-wide mb-1.5">
              Default Parameters
            </div>
            <div className="grid grid-cols-2 gap-1.5">
              <Field
                label="max_count"
                value={rules.crowd.max_count}
                onChange={(v) => update('crowd', { max_count: v })}
              />
              <Field
                label="radius"
                value={rules.crowd.radius}
                unit="px"
                onChange={(v) => update('crowd', { radius: v })}
              />
              <Field
                label="confirm_frames"
                value={rules.crowd.confirm_frames}
                onChange={(v) => update('crowd', { confirm_frames: v })}
              />
              <Field
                label="cooldown"
                value={rules.crowd.cooldown}
                unit="s"
                onChange={(v) => update('crowd', { cooldown: v })}
              />
            </div>
            <ScheduleEditor
              schedule={rules.crowd.schedule ?? DEFAULT_SCHEDULE}
              onChange={(s) => update('crowd', { schedule: s })}
            />
            <RuleRoiSection
              cameraId={cameraId}
              roi={rules.crowd.roi ?? []}
              onChange={(roi) => update('crowd', { roi })}
            />
            {cameraId && (
              <ZoneListSection
                zones={rules.crowd.zones ?? []}
                zonesEnabled={rules.crowd.zones_enabled ?? false}
                ruleType="crowd"
                defaults={extractDefaults(rules.crowd)}
                cameraId={cameraId}
                onChange={(zones) => update('crowd', { zones })}
                onToggle={(zones_enabled) => update('crowd', { zones_enabled })}
              />
            )}
          </div>
        )}
      </div>

      {/* ── Fight Detection ── */}
      <div className="mb-4 pb-3.5 border-b border-border">
        <SectionHeader
          icon={Zap}
          label="Fight Detection"
          colorClass="bg-red/12 text-red"
          enabled={rules.fight.enabled}
          onToggle={(v) => update('fight', { enabled: v })}
          collapsed={collapsed.fight}
          onToggleCollapse={() => toggle('fight')}
        />
        {!collapsed.fight && (
          <div className="mt-2.5">
            <div className="text-[10px] text-t3 font-semibold uppercase tracking-wide mb-1.5">
              Default Parameters
            </div>
            <div className="grid grid-cols-2 gap-1.5">
              <Field
                label="proximity_radius"
                value={rules.fight.proximity_radius}
                unit="px"
                onChange={(v) => update('fight', { proximity_radius: v })}
              />
              <Field
                label="min_speed"
                value={rules.fight.min_speed}
                unit="px/s"
                onChange={(v) => update('fight', { min_speed: v })}
              />
              <Field
                label="min_persons"
                value={rules.fight.min_persons}
                onChange={(v) => update('fight', { min_persons: v })}
              />
              <Field
                label="confirm_frames"
                value={rules.fight.confirm_frames}
                onChange={(v) => update('fight', { confirm_frames: v })}
              />
              <Field
                label="co_move_cos_threshold"
                value={rules.fight.co_move_cos_threshold ?? 0.7}
                step={0.01}
                onChange={(v) => update('fight', { co_move_cos_threshold: v })}
              />
              <Field
                label="min_relative_speed"
                value={rules.fight.min_relative_speed ?? 40}
                unit="px/s"
                onChange={(v) => update('fight', { min_relative_speed: v })}
              />
              <Field
                label="min_distance_variance"
                value={rules.fight.min_distance_variance ?? 10}
                unit="px²"
                onChange={(v) => update('fight', { min_distance_variance: v })}
              />
              <Field
                label="joint_overlap_threshold"
                value={rules.fight.joint_overlap_threshold ?? 1}
                onChange={(v) => update('fight', { joint_overlap_threshold: v })}
              />
              <Field
                label="cooldown"
                value={rules.fight.cooldown}
                unit="s"
                onChange={(v) => update('fight', { cooldown: v })}
              />
            </div>
            <ScheduleEditor
              schedule={rules.fight.schedule ?? DEFAULT_SCHEDULE}
              onChange={(s) => update('fight', { schedule: s })}
            />
            <RuleRoiSection
              cameraId={cameraId}
              roi={rules.fight.roi ?? []}
              onChange={(roi) => update('fight', { roi })}
            />
            {cameraId && (
              <ZoneListSection
                zones={rules.fight.zones ?? []}
                zonesEnabled={rules.fight.zones_enabled ?? false}
                ruleType="fight"
                defaults={extractDefaults(rules.fight)}
                cameraId={cameraId}
                onChange={(zones) => update('fight', { zones })}
                onToggle={(zones_enabled) => update('fight', { zones_enabled })}
              />
            )}
          </div>
        )}
      </div>

      {/* ── Fall Detection ── */}
      <div className="mb-4 pb-3.5 border-b border-border">
        <SectionHeader
          icon={TrendingDown}
          label="Fall Detection"
          colorClass="bg-orange/12 text-orange"
          enabled={rules.fall.enabled}
          onToggle={(v) => update('fall', { enabled: v })}
          collapsed={collapsed.fall}
          onToggleCollapse={() => toggle('fall')}
        />
        {!collapsed.fall && (
          <div className="mt-2.5">
            <div className="text-[10px] text-t3 font-semibold uppercase tracking-wide mb-1.5">
              Default Parameters
            </div>
            <div className="grid grid-cols-2 gap-1.5">
              <Field
                label="ratio_threshold"
                value={rules.fall.ratio_threshold}
                step={0.01}
                onChange={(v) => update('fall', { ratio_threshold: v })}
              />
              <Field
                label="min_ratio_change"
                value={rules.fall.min_ratio_change}
                step={0.01}
                onChange={(v) => update('fall', { min_ratio_change: v })}
              />
              <Field
                label="min_y_drop"
                value={rules.fall.min_y_drop}
                unit="px"
                onChange={(v) => update('fall', { min_y_drop: v })}
              />
              <Field
                label="min_hip_velocity"
                value={rules.fall.min_hip_velocity ?? 30}
                unit="px/f"
                step={1}
                onChange={(v) => update('fall', { min_hip_velocity: v })}
              />
              <Field
                label="spine_angle_threshold"
                value={rules.fall.spine_angle_threshold ?? 45}
                unit="°"
                step={1}
                onChange={(v) => update('fall', { spine_angle_threshold: v })}
              />
              <Field
                label="inactivity_frames"
                value={rules.fall.inactivity_frames ?? 3}
                onChange={(v) => update('fall', { inactivity_frames: v })}
              />
              <Field
                label="inactivity_threshold"
                value={rules.fall.inactivity_threshold ?? 15}
                unit="px"
                onChange={(v) => update('fall', { inactivity_threshold: v })}
              />
              <Field
                label="history_size"
                value={rules.fall.history_size ?? 10}
                onChange={(v) => update('fall', { history_size: v })}
              />
              <Field
                label="confirm_frames"
                value={rules.fall.confirm_frames}
                onChange={(v) => update('fall', { confirm_frames: v })}
              />
              <Field
                label="cooldown"
                value={rules.fall.cooldown}
                unit="s"
                onChange={(v) => update('fall', { cooldown: v })}
              />
            </div>
            <ScheduleEditor
              schedule={rules.fall.schedule ?? DEFAULT_SCHEDULE}
              onChange={(s) => update('fall', { schedule: s })}
            />
            <RuleRoiSection
              cameraId={cameraId}
              roi={rules.fall.roi ?? []}
              onChange={(roi) => update('fall', { roi })}
            />
            {cameraId && (
              <ZoneListSection
                zones={rules.fall.zones ?? []}
                zonesEnabled={rules.fall.zones_enabled ?? false}
                ruleType="fall"
                defaults={extractDefaults(rules.fall)}
                cameraId={cameraId}
                onChange={(zones) => update('fall', { zones })}
                onToggle={(zones_enabled) => update('fall', { zones_enabled })}
              />
            )}
          </div>
        )}
      </div>

      {/* ── Loiter Detection ── */}
      <div>
        <SectionHeader
          icon={Footprints}
          label="Loiter Detection"
          colorClass="bg-yellow/12 text-yellow"
          enabled={rules.loiter.enabled}
          onToggle={(v) => update('loiter', { enabled: v })}
          collapsed={collapsed.loiter}
          onToggleCollapse={() => toggle('loiter')}
        />
        {!collapsed.loiter && (
          <div className="mt-2.5">
            <div className="text-[10px] text-t3 font-semibold uppercase tracking-wide mb-1.5">
              Default Parameters
            </div>
            <div className="grid grid-cols-2 gap-1.5">
              <Field
                label="min_duration"
                value={rules.loiter.min_duration}
                unit="s"
                onChange={(v) => update('loiter', { min_duration: v })}
              />
              <Field
                label="max_distance"
                value={rules.loiter.max_distance}
                unit="px"
                onChange={(v) => update('loiter', { max_distance: v })}
              />
              <Field
                label="max_disp_ratio"
                value={rules.loiter.max_displacement_ratio}
                step={0.01}
                onChange={(v) => update('loiter', { max_displacement_ratio: v })}
              />
              <Field
                label="min_total_path"
                value={rules.loiter.min_total_path}
                unit="px"
                onChange={(v) => update('loiter', { min_total_path: v })}
              />
              <Field
                label="trajectory_window"
                value={rules.loiter.trajectory_window}
                unit="s"
                onChange={(v) => update('loiter', { trajectory_window: v })}
              />
              <Field
                label="inertia"
                value={rules.loiter.inertia}
                onChange={(v) => update('loiter', { inertia: v })}
              />
              <Field
                label="confirm_frames"
                value={rules.loiter.confirm_frames}
                onChange={(v) => update('loiter', { confirm_frames: v })}
              />
              <Field
                label="cooldown"
                value={rules.loiter.cooldown}
                unit="s"
                onChange={(v) => update('loiter', { cooldown: v })}
              />
            </div>
            <ScheduleEditor
              schedule={rules.loiter.schedule ?? DEFAULT_SCHEDULE}
              onChange={(s) => update('loiter', { schedule: s })}
            />
            <RuleRoiSection
              cameraId={cameraId}
              roi={rules.loiter.roi ?? []}
              onChange={(roi) => update('loiter', { roi })}
            />
            {cameraId && (
              <ZoneListSection
                zones={rules.loiter.zones ?? []}
                zonesEnabled={rules.loiter.zones_enabled ?? false}
                ruleType="loiter"
                defaults={extractDefaults(rules.loiter)}
                cameraId={cameraId}
                onChange={(zones) => update('loiter', { zones })}
                onToggle={(zones_enabled) => update('loiter', { zones_enabled })}
              />
            )}
          </div>
        )}
      </div>
    </div>
  )
}
