import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import DateFilter, { DateRange } from '../../components/DateFilter'

describe('DateFilter', () => {
  it('renders all preset buttons', () => {
    const onChange = vi.fn()
    render(<DateFilter onChange={onChange} />)

    expect(screen.getByText('Last 1 hour')).toBeInTheDocument()
    expect(screen.getByText('Last 24 hours')).toBeInTheDocument()
    expect(screen.getByText('Last 7 days')).toBeInTheDocument()
    expect(screen.getByText('Last 30 days')).toBeInTheDocument()
    expect(screen.getByText('Custom')).toBeInTheDocument()
  })

  it('highlights the default preset', () => {
    const onChange = vi.fn()
    render(<DateFilter onChange={onChange} defaultPreset="last_7d" />)

    const last7dButton = screen.getByText('Last 7 days')
    expect(last7dButton).toHaveClass('bg-blue-600')
  })

  it('calls onChange when preset is selected', () => {
    const onChange = vi.fn()
    render(<DateFilter onChange={onChange} />)

    const last1hButton = screen.getByText('Last 1 hour')
    fireEvent.click(last1hButton)

    expect(onChange).toHaveBeenCalledTimes(1)
    const call = onChange.mock.calls[0][0] as DateRange
    expect(call.preset).toBe('last_1h')
    expect(call.from).toBeInstanceOf(Date)
    expect(call.to).toBeInstanceOf(Date)

    // Verify the time range is approximately 1 hour
    if (call.from && call.to) {
      const hourDiff = (call.to.getTime() - call.from.getTime()) / (1000 * 60 * 60)
      expect(hourDiff).toBeCloseTo(1, 0)
    }
  })

  it('shows custom date inputs when Custom is selected', () => {
    const onChange = vi.fn()
    render(<DateFilter onChange={onChange} />)

    const customButton = screen.getByText('Custom')
    fireEvent.click(customButton)

    expect(screen.getByLabelText('From:')).toBeInTheDocument()
    expect(screen.getByLabelText('To:')).toBeInTheDocument()
    expect(screen.getByText('Apply')).toBeInTheDocument()
  })

  it('applies custom date range when Apply is clicked', () => {
    const onChange = vi.fn()
    render(<DateFilter onChange={onChange} />)

    // Click Custom
    const customButton = screen.getByText('Custom')
    fireEvent.click(customButton)

    // Set custom dates
    const fromInput = screen.getByLabelText('From:') as HTMLInputElement
    const toInput = screen.getByLabelText('To:') as HTMLInputElement

    fireEvent.change(fromInput, { target: { value: '2024-01-01T00:00' } })
    fireEvent.change(toInput, { target: { value: '2024-01-02T00:00' } })

    // Click Apply
    const applyButton = screen.getByText('Apply')
    fireEvent.click(applyButton)

    expect(onChange).toHaveBeenCalledWith({
      from: new Date('2024-01-01T00:00'),
      to: new Date('2024-01-02T00:00'),
      preset: 'custom',
    })
  })

  it('disables Apply button when dates are not set', () => {
    const onChange = vi.fn()
    render(<DateFilter onChange={onChange} />)

    // Click Custom
    const customButton = screen.getByText('Custom')
    fireEvent.click(customButton)

    const applyButton = screen.getByText('Apply') as HTMLButtonElement
    expect(applyButton).toBeDisabled()
  })

  it('switches between presets correctly', () => {
    const onChange = vi.fn()
    render(<DateFilter onChange={onChange} defaultPreset="last_24h" />)

    const last24hButton = screen.getByText('Last 24 hours')
    expect(last24hButton).toHaveClass('bg-blue-600')

    const last7dButton = screen.getByText('Last 7 days')
    fireEvent.click(last7dButton)

    expect(last7dButton).toHaveClass('bg-blue-600')
    expect(last24hButton).not.toHaveClass('bg-blue-600')
    expect(onChange).toHaveBeenCalled()
  })
})
