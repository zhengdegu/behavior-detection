import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import ZoneCard from '../ZoneCard'
import type { ZoneConfig } from '../../types'

// Mock RoiEditor — it's a complex canvas component
vi.mock('../RoiEditor', () => ({
  default: (props: Record<string, unknown>) => (
    <div data-testid="roi-editor" data-single-mode={String(props.singleMode)} />
  ),
}))

describe('ZoneCard', () => {
  const defaultZone: ZoneConfig = {
    roi: [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9]],
    name: 'Entrance',
  }

  const defaults: Record<string, number> = {
    max_count: 10,
    radius: 50,
    confirm_frames: 5,
    cooldown: 30,
  }

  const baseProps = {
    index: 0,
    zone: defaultZone,
    ruleType: 'crowd' as const,
    defaults,
    cameraId: 'cam-1',
    onChange: vi.fn(),
    onDelete: vi.fn(),
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  // ── Test 1: Renders zone name input with correct value ──
  it('renders zone name input with correct value', () => {
    render(<ZoneCard {...baseProps} />)
    const nameInput = screen.getByPlaceholderText('Zone name (optional)')
    expect(nameInput).toHaveValue('Entrance')
  })

  // ── Test 2: Renders parameter fields for the given ruleType ──
  it('renders parameter fields for crowd ruleType', () => {
    render(<ZoneCard {...baseProps} />)
    // crowd params: max_count, radius + common: confirm_frames, cooldown
    expect(screen.getByTestId('zone-field-max_count')).toBeInTheDocument()
    expect(screen.getByTestId('zone-field-radius')).toBeInTheDocument()
    expect(screen.getByTestId('zone-field-confirm_frames')).toBeInTheDocument()
    expect(screen.getByTestId('zone-field-cooldown')).toBeInTheDocument()
  })

  // ── Test 3: Parameter fields show placeholder (default value) when zone param is undefined ──
  it('shows placeholder with default value when zone param is undefined (inheritance)', () => {
    render(<ZoneCard {...baseProps} />)
    const maxCountField = screen.getByTestId('zone-field-max_count') as HTMLInputElement
    expect(maxCountField.value).toBe('')
    expect(maxCountField.placeholder).toBe('10')
    expect(maxCountField.dataset.inherited).toBe('true')
  })

  // ── Test 4: Parameter fields show actual value when zone param is set (override state) ──
  it('shows actual value when zone param is set (override)', () => {
    const overriddenZone: ZoneConfig = {
      ...defaultZone,
      max_count: 20,
    }
    render(<ZoneCard {...baseProps} zone={overriddenZone} />)
    const maxCountField = screen.getByTestId('zone-field-max_count') as HTMLInputElement
    expect(maxCountField.value).toBe('20')
    expect(maxCountField.dataset.inherited).toBe('false')
  })

  // ── Test 5: Clearing a parameter field calls onChange with that param as undefined ──
  it('clearing a parameter field calls onChange with param as undefined (restore inheritance)', () => {
    const overriddenZone: ZoneConfig = {
      ...defaultZone,
      max_count: 20,
    }
    const onChange = vi.fn()
    render(<ZoneCard {...baseProps} zone={overriddenZone} onChange={onChange} />)
    const maxCountField = screen.getByTestId('zone-field-max_count')
    fireEvent.change(maxCountField, { target: { value: '' } })
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ max_count: undefined })
    )
  })

  // ── Test 6: Typing a value in parameter field calls onChange with numeric value ──
  it('typing a value in parameter field calls onChange with numeric value (override)', () => {
    const onChange = vi.fn()
    render(<ZoneCard {...baseProps} onChange={onChange} />)
    const maxCountField = screen.getByTestId('zone-field-max_count')
    fireEvent.change(maxCountField, { target: { value: '15' } })
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ max_count: 15 })
    )
  })

  // ── Test 7: Delete button calls onDelete ──
  it('delete button calls onDelete', () => {
    const onDelete = vi.fn()
    render(<ZoneCard {...baseProps} onDelete={onDelete} />)
    const deleteBtn = screen.getByRole('button', { name: /delete zone 1/i })
    fireEvent.click(deleteBtn)
    expect(onDelete).toHaveBeenCalledOnce()
  })

  // ── Test 8: RoiEditor renders in singleMode ──
  it('renders RoiEditor in singleMode', () => {
    render(<ZoneCard {...baseProps} />)
    const roiEditor = screen.getByTestId('roi-editor')
    expect(roiEditor.dataset.singleMode).toBe('true')
  })

  // ── Test 9: Name input change triggers onChange with updated name ──
  it('name input change triggers onChange with updated name', () => {
    const onChange = vi.fn()
    render(<ZoneCard {...baseProps} onChange={onChange} />)
    const nameInput = screen.getByPlaceholderText('Zone name (optional)')
    fireEvent.change(nameInput, { target: { value: 'Exit Gate' } })
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ name: 'Exit Gate' })
    )
  })
})
