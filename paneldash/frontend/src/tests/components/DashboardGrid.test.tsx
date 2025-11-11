import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import DashboardGrid from '../../components/DashboardGrid'
import type { DashboardPanelReference } from '../../api/client'

describe('DashboardGrid', () => {
  const mockPanels: DashboardPanelReference[] = [
    { id: 'panel-1', config_file: 'panels/cpu.yaml' },
    { id: 'panel-2', config_file: 'panels/memory.yaml' },
    { id: 'panel-3', config_file: 'panels/disk.yaml' },
  ]

  it('renders panel placeholders when no children function provided', () => {
    render(<DashboardGrid panels={mockPanels} />)

    expect(screen.getByText('Panel: panel-1')).toBeInTheDocument()
    expect(screen.getByText('Panel: panel-2')).toBeInTheDocument()
    expect(screen.getByText('Panel: panel-3')).toBeInTheDocument()
  })

  it('renders custom content when children function provided', () => {
    render(
      <DashboardGrid panels={mockPanels}>
        {panelRef => <div>Custom content for {panelRef.id}</div>}
      </DashboardGrid>
    )

    expect(screen.getByText('Custom content for panel-1')).toBeInTheDocument()
    expect(screen.getByText('Custom content for panel-2')).toBeInTheDocument()
    expect(screen.getByText('Custom content for panel-3')).toBeInTheDocument()
  })

  it('applies correct data attributes to panel containers', () => {
    const { container } = render(<DashboardGrid panels={mockPanels} />)

    const panel1 = container.querySelector('[data-panel-id="panel-1"]')
    const panel2 = container.querySelector('[data-panel-id="panel-2"]')

    expect(panel1).toBeInTheDocument()
    expect(panel2).toBeInTheDocument()
  })

  it('handles empty panels array', () => {
    const { container } = render(<DashboardGrid panels={[]} />)
    const grid = container.querySelector('[class*="grid"]')

    expect(grid).toBeInTheDocument()
    expect(grid?.children.length).toBe(0)
  })

  it('uses custom columns value', () => {
    const { container } = render(<DashboardGrid panels={mockPanels} columns={6} />)
    const grid = container.querySelector('[class*="grid"]')

    expect(grid).toHaveStyle({ gridTemplateColumns: 'repeat(6, minmax(0, 1fr))' })
  })

  it('uses default 12 columns when not specified', () => {
    const { container } = render(<DashboardGrid panels={mockPanels} />)
    const grid = container.querySelector('[class*="grid"]')

    expect(grid).toHaveStyle({ gridTemplateColumns: 'repeat(12, minmax(0, 1fr))' })
  })
})
