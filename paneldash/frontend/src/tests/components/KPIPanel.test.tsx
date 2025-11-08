import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import KPIPanel from '../../components/panels/KPIPanel'
import { apiClient } from '../../api/client'

// Mock the API client
vi.mock('../../api/client', () => ({
  apiClient: {
    getPanelData: vi.fn(),
  },
}))

describe('KPIPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows loading spinner while fetching data', () => {
    // Mock a slow API response
    vi.mocked(apiClient.getPanelData).mockImplementation(
      () => new Promise(() => {}) // Never resolves
    )

    render(<KPIPanel panelId="cpu_kpi" tenantId="tenant_alpha" />)

    expect(screen.getByRole('status', { hidden: true })).toBeInTheDocument()
  })

  it('displays error message when fetch fails', async () => {
    vi.mocked(apiClient.getPanelData).mockRejectedValueOnce(new Error('Network error'))

    render(<KPIPanel panelId="cpu_kpi" tenantId="tenant_alpha" />)

    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument()
    })
  })

  it('displays warning when panel type is wrong', async () => {
    vi.mocked(apiClient.getPanelData).mockResolvedValueOnce({
      panel_id: 'cpu_kpi',
      panel_type: 'timeseries',
      data: { series: [] },
    })

    render(<KPIPanel panelId="cpu_kpi" tenantId="tenant_alpha" />)

    await waitFor(() => {
      expect(screen.getByText(/no kpi data available/i)).toBeInTheDocument()
    })
  })

  it('displays KPI value prominently', async () => {
    vi.mocked(apiClient.getPanelData).mockResolvedValueOnce({
      panel_id: 'cpu_kpi',
      panel_type: 'kpi',
      data: {
        value: 75.3,
        unit: '%',
        decimals: 1,
        threshold_status: 'good',
        threshold_color: '#10B981',
      },
    })

    render(<KPIPanel panelId="cpu_kpi" tenantId="tenant_alpha" title="CPU Usage" />)

    await waitFor(() => {
      const valueElement = screen.getByTestId('kpi-value')
      expect(valueElement).toBeInTheDocument()
      expect(valueElement).toHaveTextContent('75.3')
    })
  })

  it('displays unit next to value', async () => {
    vi.mocked(apiClient.getPanelData).mockResolvedValueOnce({
      panel_id: 'cpu_kpi',
      panel_type: 'kpi',
      data: {
        value: 75.3,
        unit: '%',
        decimals: 1,
      },
    })

    render(<KPIPanel panelId="cpu_kpi" tenantId="tenant_alpha" />)

    await waitFor(() => {
      const unitElement = screen.getByTestId('kpi-unit')
      expect(unitElement).toBeInTheDocument()
      expect(unitElement).toHaveTextContent('%')
    })
  })

  it('displays title when provided', async () => {
    vi.mocked(apiClient.getPanelData).mockResolvedValueOnce({
      panel_id: 'cpu_kpi',
      panel_type: 'kpi',
      data: {
        value: 75.3,
        decimals: 1,
      },
    })

    render(<KPIPanel panelId="cpu_kpi" tenantId="tenant_alpha" title="CPU Usage" />)

    await waitFor(() => {
      expect(screen.getByText('CPU Usage')).toBeInTheDocument()
    })
  })

  it('displays threshold status badge', async () => {
    vi.mocked(apiClient.getPanelData).mockResolvedValueOnce({
      panel_id: 'cpu_kpi',
      panel_type: 'kpi',
      data: {
        value: 85.0,
        unit: '%',
        decimals: 1,
        threshold_status: 'warning',
        threshold_color: '#F59E0B',
      },
    })

    render(<KPIPanel panelId="cpu_kpi" tenantId="tenant_alpha" />)

    await waitFor(() => {
      const statusElement = screen.getByTestId('kpi-status')
      expect(statusElement).toBeInTheDocument()
      expect(statusElement).toHaveTextContent('warning')
    })
  })

  it('applies correct color classes for green threshold', async () => {
    vi.mocked(apiClient.getPanelData).mockResolvedValueOnce({
      panel_id: 'cpu_kpi',
      panel_type: 'kpi',
      data: {
        value: 45.0,
        unit: '%',
        decimals: 1,
        threshold_status: 'good',
        threshold_color: '#10B981',
      },
    })

    render(<KPIPanel panelId="cpu_kpi" tenantId="tenant_alpha" />)

    await waitFor(() => {
      const valueElement = screen.getByTestId('kpi-value')
      expect(valueElement).toHaveClass('text-green-700')
    })
  })

  it('applies correct color classes for amber threshold', async () => {
    vi.mocked(apiClient.getPanelData).mockResolvedValueOnce({
      panel_id: 'cpu_kpi',
      panel_type: 'kpi',
      data: {
        value: 75.0,
        unit: '%',
        decimals: 1,
        threshold_status: 'warning',
        threshold_color: '#F59E0B',
      },
    })

    render(<KPIPanel panelId="cpu_kpi" tenantId="tenant_alpha" />)

    await waitFor(() => {
      const valueElement = screen.getByTestId('kpi-value')
      expect(valueElement).toHaveClass('text-amber-700')
    })
  })

  it('applies correct color classes for red threshold', async () => {
    vi.mocked(apiClient.getPanelData).mockResolvedValueOnce({
      panel_id: 'cpu_kpi',
      panel_type: 'kpi',
      data: {
        value: 95.0,
        unit: '%',
        decimals: 1,
        threshold_status: 'critical',
        threshold_color: '#EF4444',
      },
    })

    render(<KPIPanel panelId="cpu_kpi" tenantId="tenant_alpha" />)

    await waitFor(() => {
      const valueElement = screen.getByTestId('kpi-value')
      expect(valueElement).toHaveClass('text-red-700')
    })
  })

  it('formats value with correct decimals', async () => {
    vi.mocked(apiClient.getPanelData).mockResolvedValueOnce({
      panel_id: 'memory_kpi',
      panel_type: 'kpi',
      data: {
        value: 1234.5678,
        decimals: 2,
      },
    })

    render(<KPIPanel panelId="memory_kpi" tenantId="tenant_alpha" />)

    await waitFor(() => {
      const valueElement = screen.getByTestId('kpi-value')
      expect(valueElement).toHaveTextContent('1234.57')
    })
  })

  it('handles invalid data format gracefully', async () => {
    vi.mocked(apiClient.getPanelData).mockResolvedValueOnce({
      panel_id: 'cpu_kpi',
      panel_type: 'kpi',
      data: {
        invalid: 'data',
      },
    })

    render(<KPIPanel panelId="cpu_kpi" tenantId="tenant_alpha" />)

    await waitFor(() => {
      expect(screen.getByText(/invalid kpi data format/i)).toBeInTheDocument()
    })
  })

  it('works without optional fields', async () => {
    vi.mocked(apiClient.getPanelData).mockResolvedValueOnce({
      panel_id: 'simple_kpi',
      panel_type: 'kpi',
      data: {
        value: 42,
      },
    })

    render(<KPIPanel panelId="simple_kpi" tenantId="tenant_alpha" />)

    await waitFor(() => {
      const valueElement = screen.getByTestId('kpi-value')
      expect(valueElement).toBeInTheDocument()
      expect(valueElement).toHaveTextContent('42.0') // Default 1 decimal
      expect(screen.queryByTestId('kpi-unit')).not.toBeInTheDocument()
      expect(screen.queryByTestId('kpi-status')).not.toBeInTheDocument()
    })
  })
})
