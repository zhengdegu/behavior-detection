import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import Config from '../Config'
import type { Camera, RulesConfig, ZoneConfig } from '../../types'

// ── Mocks ──

// Mock RoiEditor — canvas component that won't work in jsdom
vi.mock('../../components/RoiEditor', () => ({
  default: () => <div data-testid="roi-editor" />,
}))

// Mock RuleForm — we control its onChange callback to test data flow
let capturedRuleFormProps: { rules: RulesConfig; onChange: (r: RulesConfig) => void; cameraId: string } | null = null
vi.mock('../../components/RuleForm', () => ({
  default: (props: { rules: RulesConfig; onChange: (r: RulesConfig) => void; cameraId: string }) => {
    capturedRuleFormProps = props
    return <div data-testid="rule-form" data-rules={JSON.stringify(props.rules)} />
  },
}))

// Mock API module
const mockGetCameras = vi.fn<() => Promise<Camera[]>>()
const mockUpdateCamera = vi.fn<(id: string, data: unknown) => Promise<Camera>>()
const mockGetTimeSyncStatus = vi.fn()

vi.mock('../../api', () => ({
  getCameras: (...args: unknown[]) => mockGetCameras(...(args as [])),
  updateCamera: (...args: unknown[]) => mockUpdateCamera(...(args as [string, unknown])),
  deleteCamera: vi.fn(),
  createCamera: vi.fn(),
  getTimeSyncStatus: () => mockGetTimeSyncStatus(),
  setCameraTimezone: vi.fn(),
  triggerManualEvent: vi.fn(),
}))

// ── Helpers ──

const baseCameraNoZones: Camera = {
  id: 'cam-1',
  name: 'Test Camera',
  url: 'rtsp://example.com/stream',
  online: true,
  detect: { fps: 5, confidence: 0.5 },
  roi: [[[0.1, 0.1], [0.9, 0.1], [0.9, 0.9]]],
  rules: {
    crowd: { enabled: true, max_count: 10, radius: 50, confirm_frames: 5, cooldown: 30 },
    fight: { enabled: false, proximity_radius: 100, min_speed: 30, min_persons: 2, confirm_frames: 5, cooldown: 30 },
    fall: { enabled: false, ratio_threshold: 0.6, min_ratio_change: 0.3, min_y_drop: 30, confirm_frames: 3, cooldown: 30 },
    loiter: { enabled: false, min_duration: 60, max_distance: 150, max_displacement_ratio: 0.3, min_total_path: 100, trajectory_window: 30, inertia: 3, confirm_frames: 5, cooldown: 30 },
  },
}

const zonesData: ZoneConfig[] = [
  { roi: [[0.1, 0.1], [0.5, 0.1], [0.5, 0.5]], name: 'Entrance', max_count: 3 },
  { roi: [[0.5, 0.5], [0.9, 0.5], [0.9, 0.9]], name: 'Exit' },
]

const baseCameraWithZones: Camera = {
  ...baseCameraNoZones,
  rules: {
    ...baseCameraNoZones.rules!,
    crowd: { ...baseCameraNoZones.rules!.crowd, zones: zonesData },
  },
}

function setupMocks(cameras: Camera[] = [baseCameraNoZones]) {
  mockGetCameras.mockResolvedValue(cameras)
  mockGetTimeSyncStatus.mockResolvedValue({ enabled: false, cameras: [] })
  mockUpdateCamera.mockResolvedValue(cameras[0])
}

async function renderAndSelectCamera(cameras: Camera[] = [baseCameraNoZones]) {
  setupMocks(cameras)

  await act(async () => {
    render(<Config />)
  })

  // Wait for cameras to load and click the camera in the list
  const cameraItem = await screen.findByText('Test Camera')
  await act(async () => {
    fireEvent.click(cameraItem)
  })
}

// ── Tests ──

describe('Config Page zones data flow', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    capturedRuleFormProps = null
  })

  // ── Test 1: No zones field → editRules initializes zones as empty array ──
  // Validates: Requirement 10.4

  it('initializes zones as empty array when camera config has no zones field', async () => {
    await renderAndSelectCamera([baseCameraNoZones])

    // RuleForm should receive rules where each rule has zones: []
    expect(capturedRuleFormProps).not.toBeNull()
    const rules = capturedRuleFormProps!.rules
    expect(rules.crowd.zones).toEqual([])
    expect(rules.fight.zones).toEqual([])
    expect(rules.fall.zones).toEqual([])
    expect(rules.loiter.zones).toEqual([])
  })

  // ── Test 2: Camera config has zones data → editRules populates with that data ──
  // Validates: Requirement 10.1

  it('populates editRules with zones data from camera config', async () => {
    await renderAndSelectCamera([baseCameraWithZones])

    expect(capturedRuleFormProps).not.toBeNull()
    const rules = capturedRuleFormProps!.rules
    expect(rules.crowd.zones).toHaveLength(2)
    expect(rules.crowd.zones![0].name).toBe('Entrance')
    expect(rules.crowd.zones![0].max_count).toBe(3)
    expect(rules.crowd.zones![1].name).toBe('Exit')
    // Other rules without zones should still get []
    expect(rules.fight.zones).toEqual([])
    expect(rules.fall.zones).toEqual([])
    expect(rules.loiter.zones).toEqual([])
  })

  // ── Test 3: Save Configuration sends zones data to API ──
  // Validates: Requirement 10.3

  it('includes zones data in the API request when saving', async () => {
    await renderAndSelectCamera([baseCameraWithZones])

    // Click "Save Configuration" button
    const saveBtn = screen.getByRole('button', { name: /save configuration/i })
    await act(async () => {
      fireEvent.click(saveBtn)
    })

    await waitFor(() => {
      expect(mockUpdateCamera).toHaveBeenCalledTimes(1)
    })

    const [calledId, calledData] = mockUpdateCamera.mock.calls[0]
    expect(calledId).toBe('cam-1')
    // The rules in the request should contain zones
    expect(calledData.rules.crowd.zones).toHaveLength(2)
    expect(calledData.rules.crowd.zones[0].name).toBe('Entrance')
    expect(calledData.rules.crowd.zones[0].max_count).toBe(3)
    expect(calledData.rules.crowd.zones[1].name).toBe('Exit')
  })

  // ── Test 4: RuleForm onChange propagates zones changes to editRules state ──
  // Validates: Requirement 10.2

  it('propagates zones changes from RuleForm onChange to editRules state', async () => {
    await renderAndSelectCamera([baseCameraNoZones])

    // Simulate RuleForm calling onChange with new zones
    const newZone: ZoneConfig = { roi: [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8]], name: 'New Zone' }
    const updatedRules: RulesConfig = {
      ...capturedRuleFormProps!.rules,
      crowd: { ...capturedRuleFormProps!.rules.crowd, zones: [newZone] },
    }

    await act(async () => {
      capturedRuleFormProps!.onChange(updatedRules)
    })

    // After onChange, the RuleForm should be re-rendered with updated rules
    expect(capturedRuleFormProps!.rules.crowd.zones).toHaveLength(1)
    expect(capturedRuleFormProps!.rules.crowd.zones![0].name).toBe('New Zone')

    // Now save and verify the API gets the updated zones
    const saveBtn = screen.getByRole('button', { name: /save configuration/i })
    await act(async () => {
      fireEvent.click(saveBtn)
    })

    await waitFor(() => {
      expect(mockUpdateCamera).toHaveBeenCalledTimes(1)
    })

    const [, calledData] = mockUpdateCamera.mock.calls[0]
    expect(calledData.rules.crowd.zones).toHaveLength(1)
    expect(calledData.rules.crowd.zones[0].name).toBe('New Zone')
  })
})
