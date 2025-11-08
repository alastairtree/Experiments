import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import HealthStatusPanel from '../../components/panels/HealthStatusPanel'
import { apiClient } from '../../api/client'

// Mock the API client
vi.mock('../../api/client', () => ({
  apiClient: {
    getPanelData: vi.fn(),
  },
}))

// Mock date-fns
vi.mock('date-fns', () => ({
  formatDistanceToNow: vi.fn((_date: Date) => {
    // Simple mock implementation
    return '5 minutes ago'
  }),
}))

describe('HealthStatusPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows loading spinner while fetching data', () => {
    vi.mocked(apiClient.getPanelData).mockImplementation(
      () => new Promise(() => {}) // Never resolves
    )

    render(<HealthStatusPanel panelId="system_health" tenantId="tenant_alpha" />)

    expect(screen.getByRole('status', { hidden: true })).toBeInTheDocument()
  })

  it('displays error message when fetch fails', async () => {
    vi.mocked(apiClient.getPanelData).mockRejectedValueOnce(new Error('Network error'))

    render(<HealthStatusPanel panelId="system_health" tenantId="tenant_alpha" />)

    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument()
    })
  })

  it('displays warning when panel type is wrong', async () => {
    vi.mocked(apiClient.getPanelData).mockResolvedValueOnce({
      panel_id: 'system_health',
      panel_type: 'kpi',
      data: { value: 75 },
    })

    render(<HealthStatusPanel panelId="system_health" tenantId="tenant_alpha" />)

    await waitFor(() => {
      expect(screen.getByText(/no health status data available/i)).toBeInTheDocument()
    })
  })

  it('displays list of services with status', async () => {
    vi.mocked(apiClient.getPanelData).mockResolvedValueOnce({
      panel_id: 'system_health',
      panel_type: 'health_status',
      data: {
        services: [
          {
            service_name: 'API Server',
            status_value: 0,
            status_label: 'healthy',
            status_color: '#10B981',
          },
          {
            service_name: 'Database',
            status_value: 1,
            status_label: 'degraded',
            status_color: '#F59E0B',
          },
        ],
      },
    })

    render(<HealthStatusPanel panelId="system_health" tenantId="tenant_alpha" />)

    await waitFor(() => {
      const serviceNames = screen.getAllByTestId('service-name')
      expect(serviceNames).toHaveLength(2)
      expect(serviceNames[0]).toHaveTextContent('API Server')
      expect(serviceNames[1]).toHaveTextContent('Database')
    })
  })

  it('displays correct status colors', async () => {
    vi.mocked(apiClient.getPanelData).mockResolvedValueOnce({
      panel_id: 'system_health',
      panel_type: 'health_status',
      data: {
        services: [
          {
            service_name: 'Healthy Service',
            status_value: 0,
            status_label: 'healthy',
            status_color: '#10B981',
          },
        ],
      },
    })

    render(<HealthStatusPanel panelId="system_health" tenantId="tenant_alpha" />)

    await waitFor(() => {
      const statusDot = screen.getByTestId('status-dot')
      expect(statusDot).toHaveClass('bg-green-500')
    })
  })

  it('displays status labels with correct styling', async () => {
    vi.mocked(apiClient.getPanelData).mockResolvedValueOnce({
      panel_id: 'system_health',
      panel_type: 'health_status',
      data: {
        services: [
          {
            service_name: 'Test Service',
            status_value: 0,
            status_label: 'healthy',
            status_color: '#10B981',
          },
        ],
      },
    })

    render(<HealthStatusPanel panelId="system_health" tenantId="tenant_alpha" />)

    await waitFor(() => {
      const statusLabel = screen.getByTestId('status-label')
      expect(statusLabel).toHaveTextContent('healthy')
      expect(statusLabel).toHaveClass('bg-green-100', 'text-green-700')
    })
  })

  it('displays human-readable timestamps', async () => {
    vi.mocked(apiClient.getPanelData).mockResolvedValueOnce({
      panel_id: 'system_health',
      panel_type: 'health_status',
      data: {
        services: [
          {
            service_name: 'API Server',
            status_value: 0,
            status_label: 'healthy',
            status_color: '#10B981',
            last_check: '2024-01-01T12:00:00Z',
          },
        ],
      },
    })

    render(<HealthStatusPanel panelId="system_health" tenantId="tenant_alpha" />)

    await waitFor(() => {
      const lastCheck = screen.getByTestId('last-check')
      expect(lastCheck).toHaveTextContent('Checked 5 minutes ago')
    })
  })

  it('displays error icon when service has error message', async () => {
    vi.mocked(apiClient.getPanelData).mockResolvedValueOnce({
      panel_id: 'system_health',
      panel_type: 'health_status',
      data: {
        services: [
          {
            service_name: 'Failing Service',
            status_value: 2,
            status_label: 'critical',
            status_color: '#EF4444',
            error_message: 'Connection timeout',
          },
        ],
      },
    })

    render(<HealthStatusPanel panelId="system_health" tenantId="tenant_alpha" />)

    await waitFor(() => {
      expect(screen.getByTestId('error-icon')).toBeInTheDocument()
    })
  })

  it('displays title when provided', async () => {
    vi.mocked(apiClient.getPanelData).mockResolvedValueOnce({
      panel_id: 'system_health',
      panel_type: 'health_status',
      data: {
        services: [],
      },
    })

    render(
      <HealthStatusPanel
        panelId="system_health"
        tenantId="tenant_alpha"
        title="System Health"
      />
    )

    await waitFor(() => {
      expect(screen.getByText('System Health')).toBeInTheDocument()
    })
  })

  it('displays message when no services available', async () => {
    vi.mocked(apiClient.getPanelData).mockResolvedValueOnce({
      panel_id: 'system_health',
      panel_type: 'health_status',
      data: {
        services: [],
      },
    })

    render(<HealthStatusPanel panelId="system_health" tenantId="tenant_alpha" />)

    await waitFor(() => {
      expect(screen.getByText('No services to display')).toBeInTheDocument()
    })
  })

  it('handles all status colors correctly', async () => {
    vi.mocked(apiClient.getPanelData).mockResolvedValueOnce({
      panel_id: 'system_health',
      panel_type: 'health_status',
      data: {
        services: [
          {
            service_name: 'Green Service',
            status_value: 0,
            status_label: 'healthy',
            status_color: '#10B981',
          },
          {
            service_name: 'Amber Service',
            status_value: 1,
            status_label: 'degraded',
            status_color: '#F59E0B',
          },
          {
            service_name: 'Red Service',
            status_value: 2,
            status_label: 'critical',
            status_color: '#EF4444',
          },
          {
            service_name: 'Gray Service',
            status_value: 3,
            status_label: 'unknown',
            status_color: '#6B7280',
          },
        ],
      },
    })

    render(<HealthStatusPanel panelId="system_health" tenantId="tenant_alpha" />)

    await waitFor(() => {
      const statusDots = screen.getAllByTestId('status-dot')
      expect(statusDots).toHaveLength(4)
      expect(statusDots[0]).toHaveClass('bg-green-500')
      expect(statusDots[1]).toHaveClass('bg-amber-500')
      expect(statusDots[2]).toHaveClass('bg-red-500')
      expect(statusDots[3]).toHaveClass('bg-gray-500')
    })
  })

  it('handles invalid data format gracefully', async () => {
    vi.mocked(apiClient.getPanelData).mockResolvedValueOnce({
      panel_id: 'system_health',
      panel_type: 'health_status',
      data: {
        invalid: 'data',
      },
    })

    render(<HealthStatusPanel panelId="system_health" tenantId="tenant_alpha" />)

    await waitFor(() => {
      expect(screen.getByText(/invalid health status data format/i)).toBeInTheDocument()
    })
  })

  it('displays error tooltip on hover', async () => {
    vi.mocked(apiClient.getPanelData).mockResolvedValueOnce({
      panel_id: 'system_health',
      panel_type: 'health_status',
      data: {
        services: [
          {
            service_name: 'Failing Service',
            status_value: 2,
            status_label: 'critical',
            status_color: '#EF4444',
            error_message: 'Database connection lost',
          },
        ],
      },
    })

    render(<HealthStatusPanel panelId="system_health" tenantId="tenant_alpha" />)

    await waitFor(() => {
      const tooltip = screen.getByTestId('error-tooltip')
      expect(tooltip).toHaveTextContent('Database connection lost')
    })
  })
})
