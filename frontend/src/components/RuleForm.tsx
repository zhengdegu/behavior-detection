import type { RulesConfig } from '../types'
import { Users, Zap, TrendingDown } from 'lucide-react'

interface RuleFormProps {
  rules: RulesConfig
  onChange: (rules: RulesConfig) => void
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
}: {
  icon: React.ComponentType<{ size?: number }>
  label: string
  colorClass: string
  enabled: boolean
  onToggle: (v: boolean) => void
}) {
  return (
    <div className="flex items-center justify-between mb-2.5">
      <div className="flex items-center gap-1.5 text-xs font-semibold">
        <span
          className={`w-[18px] h-[18px] rounded flex items-center justify-center ${colorClass}`}
        >
          <Icon size={10} />
        </span>
        {label}
      </div>
      <Toggle checked={enabled} onChange={onToggle} />
    </div>
  )
}

export default function RuleForm({ rules, onChange }: RuleFormProps) {
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
        />
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
      </div>

      {/* ── Fight Detection ── */}
      <div className="mb-4 pb-3.5 border-b border-border">
        <SectionHeader
          icon={Zap}
          label="Fight Detection"
          colorClass="bg-red/12 text-red"
          enabled={rules.fight.enabled}
          onToggle={(v) => update('fight', { enabled: v })}
        />
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
            label="cooldown"
            value={rules.fight.cooldown}
            unit="s"
            onChange={(v) => update('fight', { cooldown: v })}
          />
        </div>
      </div>

      {/* ── Fall Detection ── */}
      <div>
        <SectionHeader
          icon={TrendingDown}
          label="Fall Detection"
          colorClass="bg-orange/12 text-orange"
          enabled={rules.fall.enabled}
          onToggle={(v) => update('fall', { enabled: v })}
        />
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
            label="cooldown"
            value={rules.fall.cooldown}
            unit="s"
            onChange={(v) => update('fall', { cooldown: v })}
          />
        </div>
      </div>
    </div>
  )
}
