import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import RuleForm from '../RuleForm'
import type { RulesConfig } from '../../types'

// Mock RoiEditor — complex canvas component
vi.mock('../RoiEditor', () => ({
  default: (props: Record<string, unknown>) => (
    <div data-testid="roi-editor" data-single-mode={String(props.singleMode)} />
  ),
}))

describe('RuleForm Zone List Integration', () => {
  const baseRules: RulesConfig = {
    crowd: {
      enabled: true,
      max_count: 10,
      radius: 50,
      confirm_frames: 5,
      cooldown: 30,
      zones: [],
    },
    fight: {
      enabled: false,
      proximity_radius: 100,
      min_speed: 30,
      min_persons: 2,
      confirm_frames: 5,
      cooldown: 30,
    },
    fall: {
      enabled: false,
      ratio_threshold: 0.6,
      min_ratio_change: 0.3,
      min_y_drop: 30,
      confirm_frames: 3,
      cooldown: 30,
    },
    loiter: {
      enabled: false,
      min_duration: 60,
      max_distance: 150,
      max_displacement_ratio: 0.3,
      min_total_path: 100,
      trajectory_window: 30,
      inertia: 3,
      confirm_frames: 5,
      cooldown: 30,
    },
  }

  let onChange: ReturnType<typeof vi.fn>

  beforeEach(() => {
    vi.clearAllMocks()
    onChange = vi.fn()
  })

  /**
   * Helper: expand the Crowd Detection section by clicking its header.
   */
  function expandCrowdSection() {
    const header = screen.getByText('Crowd Detection')
    fireEvent.click(header)
  }

  // ── Test 1: Renders "Default Parameters" section header when rule panel is expanded ──
  // Validates: Requirement 9.1

  it('renders "Default Parameters" section header when rule panel is expanded', () => {
    render(<RuleForm rules={baseRules} onChange={onChange} cameraId="cam-1" />)
    expandCrowdSection()
    expect(screen.getByText('Default Parameters')).toBeInTheDocument()
  })

  // ── Test 2: Renders "添加 Zone" button when cameraId is provided ──
  // Validates: Requirement 8.6

  it('renders "添加 Zone" button when cameraId is provided', () => {
    render(<RuleForm rules={baseRules} onChange={onChange} cameraId="cam-1" />)
    expandCrowdSection()
    expect(screen.getByText('添加 Zone')).toBeInTheDocument()
  })

  // ── Test 3: Clicking "添加 Zone" adds a new empty zone ──
  // Validates: Requirement 8.6

  it('clicking "添加 Zone" adds a new empty zone (onChange called with zones updated)', () => {
    render(<RuleForm rules={baseRules} onChange={onChange} cameraId="cam-1" />)
    expandCrowdSection()

    const addBtn = screen.getByText('添加 Zone')
    fireEvent.click(addBtn)

    expect(onChange).toHaveBeenCalledTimes(1)
    const updatedRules = onChange.mock.calls[0][0] as RulesConfig
    expect(updatedRules.crowd.zones).toHaveLength(1)
    expect(updatedRules.crowd.zones![0]).toEqual({ roi: [] })
  })

  // ── Test 4: Zone cards are rendered for each zone in the rules config ──
  // Validates: Requirement 8.1

  it('renders zone cards for each zone in the rules config', () => {
    const rulesWithZones: RulesConfig = {
      ...baseRules,
      crowd: {
        ...baseRules.crowd,
        zones: [
          { roi: [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9]], name: 'Zone A' },
          { roi: [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8]], name: 'Zone B' },
        ],
      },
    }
    render(<RuleForm rules={rulesWithZones} onChange={onChange} cameraId="cam-1" />)
    expandCrowdSection()

    // Each ZoneCard renders a name input with the zone name
    expect(screen.getByDisplayValue('Zone A')).toBeInTheDocument()
    expect(screen.getByDisplayValue('Zone B')).toBeInTheDocument()
  })

  // ── Test 5: Deleting a zone card removes it from the list ──
  // Validates: Requirement 8.1

  it('deleting a zone card removes it from the list (onChange called with updated zones)', () => {
    const rulesWithZones: RulesConfig = {
      ...baseRules,
      crowd: {
        ...baseRules.crowd,
        zones: [
          { roi: [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9]], name: 'Zone A' },
          { roi: [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8]], name: 'Zone B' },
        ],
      },
    }
    render(<RuleForm rules={rulesWithZones} onChange={onChange} cameraId="cam-1" />)
    expandCrowdSection()

    // Click the delete button for Zone 1 (first zone)
    const deleteBtn = screen.getByRole('button', { name: /delete zone 1/i })
    fireEvent.click(deleteBtn)

    expect(onChange).toHaveBeenCalledTimes(1)
    const updatedRules = onChange.mock.calls[0][0] as RulesConfig
    expect(updatedRules.crowd.zones).toHaveLength(1)
    expect(updatedRules.crowd.zones![0].name).toBe('Zone B')
  })

  // ── Test 6: Modifying a zone triggers onChange with updated zone data ──
  // Validates: Requirement 9.2

  it('modifying a zone (name change) triggers onChange with updated zone data', () => {
    const rulesWithZones: RulesConfig = {
      ...baseRules,
      crowd: {
        ...baseRules.crowd,
        zones: [
          { roi: [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9]], name: 'Zone A' },
        ],
      },
    }
    render(<RuleForm rules={rulesWithZones} onChange={onChange} cameraId="cam-1" />)
    expandCrowdSection()

    const nameInput = screen.getByDisplayValue('Zone A')
    fireEvent.change(nameInput, { target: { value: 'Lobby' } })

    expect(onChange).toHaveBeenCalledTimes(1)
    const updatedRules = onChange.mock.calls[0][0] as RulesConfig
    expect(updatedRules.crowd.zones![0].name).toBe('Lobby')
  })

  // ── Test 7: Default parameter fields remain functional (changing max_count triggers onChange) ──
  // Validates: Requirement 9.3

  it('default parameter fields remain functional (changing max_count triggers onChange)', () => {
    render(<RuleForm rules={baseRules} onChange={onChange} cameraId="cam-1" />)
    expandCrowdSection()

    // The default parameters section has a "max_count" field with value 10
    const maxCountInput = screen.getByDisplayValue('10')
    fireEvent.change(maxCountInput, { target: { value: '15' } })

    expect(onChange).toHaveBeenCalledTimes(1)
    const updatedRules = onChange.mock.calls[0][0] as RulesConfig
    expect(updatedRules.crowd.max_count).toBe(15)
  })
})
