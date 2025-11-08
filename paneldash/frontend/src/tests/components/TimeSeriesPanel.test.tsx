import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import TimeSeriesPanel from '../../components/panels/TimeSeriesPanel'
import { apiClient } from '../../api/client'

// Mock the API client
vi.mock('../../api/client', () => ({
  apiClient: {
    getPanelData: vi.fn(),
  },
}))

// Mock react-plotly.js
vi.mock('react-plotly.js', () => ({
  default: ({ data, layout }: { data: unknown; layout: unknown }) => (
    <div data-testid="plotly-chart" data-plot-data={JSON.stringify(data)} data-plot-layout={JSON.stringify(layout)}>
      Plotly Chart
    </div>
  ),
}))

describe('TimeSeriesPanel', () => {
  const mockDateRange = {
    from: new Date('2024-01-01T00:00:00Z'),
    to: new Date('2024-01-02T00:00:00Z'),
    preset: 'last_24h',
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows loading spinner while fetching data', () => {
    // Mock a slow API response
    vi.mocked(apiClient.getPanelData).mockImplementation(
      () => new Promise(() => {}) // Never resolves
    )

    render(
      <TimeSeriesPanel
        panelId="cpu_usage"
        tenantId="tenant_alpha"
        dateRange={mockDateRange}
      />
    )

    expect(screen.getByRole('status', { hidden: true })).toBeInTheDocument()
  })

  it('displays error message when fetch fails', async () => {
    vi.mocked(apiClient.getPanelData).mockRejectedValueOnce(
      new Error('Network error')
    )

    render(
      <TimeSeriesPanel
        panelId="cpu_usage"
        tenantId="tenant_alpha"
        dateRange={mockDateRange}
      />
    )

    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument()
    })
  })

  it('displays warning when no data is available', async () => {
    vi.mocked(apiClient.getPanelData).mockResolvedValueOnce({
      panel_id: 'cpu_usage',
      panel_type: 'timeseries',
      data: { series: [] },
    })

    render(
      <TimeSeriesPanel
        panelId="cpu_usage"
        tenantId="tenant_alpha"
        dateRange={mockDateRange}
      />
    )

    // Wait for loading to complete
    await waitFor(() => {
      expect(screen.queryByRole('status', { hidden: true })).not.toBeInTheDocument()
    })

    // Should still render the chart even with empty data
    expect(screen.getByTestId('plotly-chart')).toBeInTheDocument()
  })

  it('renders time series chart with single series', async () => {
    vi.mocked(apiClient.getPanelData).mockResolvedValueOnce({
      panel_id: 'cpu_usage',
      panel_type: 'timeseries',
      data: {
        series: [
          {
            timestamps: ['2024-01-01T00:00:00Z', '2024-01-01T01:00:00Z'],
            values: [45.2, 52.1],
            label: 'server-1',
          },
        ],
      },
    })

    render(
      <TimeSeriesPanel
        panelId="cpu_usage"
        tenantId="tenant_alpha"
        dateRange={mockDateRange}
      />
    )

    await waitFor(() => {
      const chart = screen.getByTestId('plotly-chart')
      expect(chart).toBeInTheDocument()

      const plotData = JSON.parse(chart.getAttribute('data-plot-data') || '[]')
      expect(plotData).toHaveLength(1)
      expect(plotData[0].name).toBe('server-1')
      expect(plotData[0].x).toEqual(['2024-01-01T00:00:00Z', '2024-01-01T01:00:00Z'])
      expect(plotData[0].y).toEqual([45.2, 52.1])
      expect(plotData[0].type).toBe('scatter')
    })
  })

  it('renders time series chart with multiple series', async () => {
    vi.mocked(apiClient.getPanelData).mockResolvedValueOnce({
      panel_id: 'cpu_usage',
      panel_type: 'timeseries',
      data: {
        series: [
          {
            timestamps: ['2024-01-01T00:00:00Z', '2024-01-01T01:00:00Z'],
            values: [45.2, 52.1],
            label: 'server-1',
          },
          {
            timestamps: ['2024-01-01T00:00:00Z', '2024-01-01T01:00:00Z'],
            values: [38.5, 42.3],
            label: 'server-2',
          },
        ],
      },
    })

    render(
      <TimeSeriesPanel
        panelId="cpu_usage"
        tenantId="tenant_alpha"
        dateRange={mockDateRange}
      />
    )

    await waitFor(() => {
      const chart = screen.getByTestId('plotly-chart')
      const plotData = JSON.parse(chart.getAttribute('data-plot-data') || '[]')

      expect(plotData).toHaveLength(2)
      expect(plotData[0].name).toBe('server-1')
      expect(plotData[1].name).toBe('server-2')
    })
  })

  it('displays title when provided', async () => {
    vi.mocked(apiClient.getPanelData).mockResolvedValueOnce({
      panel_id: 'cpu_usage',
      panel_type: 'timeseries',
      data: {
        series: [
          {
            timestamps: ['2024-01-01T00:00:00Z'],
            values: [45.2],
            label: 'server-1',
          },
        ],
      },
    })

    render(
      <TimeSeriesPanel
        panelId="cpu_usage"
        tenantId="tenant_alpha"
        dateRange={mockDateRange}
        title="CPU Usage Over Time"
      />
    )

    await waitFor(() => {
      expect(screen.getByText('CPU Usage Over Time')).toBeInTheDocument()
    })
  })

  it('shows aggregation info when data is aggregated', async () => {
    vi.mocked(apiClient.getPanelData).mockResolvedValueOnce({
      panel_id: 'cpu_usage',
      panel_type: 'timeseries',
      data: {
        series: [
          {
            timestamps: ['2024-01-01T00:00:00Z'],
            values: [45.2],
            label: 'server-1',
          },
        ],
      },
      aggregation_info: {
        applied: true,
        bucket_interval: '10 minutes',
      },
    })

    render(
      <TimeSeriesPanel
        panelId="cpu_usage"
        tenantId="tenant_alpha"
        dateRange={mockDateRange}
      />
    )

    await waitFor(() => {
      expect(screen.getByText(/data aggregated using 10 minutes intervals/i)).toBeInTheDocument()
    })
  })

  it('refetches data when date range changes', async () => {
    const { rerender } = render(
      <TimeSeriesPanel
        panelId="cpu_usage"
        tenantId="tenant_alpha"
        dateRange={mockDateRange}
      />
    )

    await waitFor(() => {
      expect(apiClient.getPanelData).toHaveBeenCalledTimes(1)
    })

    // Change date range
    const newDateRange = {
      from: new Date('2024-01-02T00:00:00Z'),
      to: new Date('2024-01-03T00:00:00Z'),
      preset: 'custom',
    }

    rerender(
      <TimeSeriesPanel
        panelId="cpu_usage"
        tenantId="tenant_alpha"
        dateRange={newDateRange}
      />
    )

    await waitFor(() => {
      expect(apiClient.getPanelData).toHaveBeenCalledTimes(2)
      expect(apiClient.getPanelData).toHaveBeenLastCalledWith(
        'tenant_alpha',
        'cpu_usage',
        expect.objectContaining({
          date_from: newDateRange.from.toISOString(),
          date_to: newDateRange.to.toISOString(),
        })
      )
    })
  })

  it('handles wrong panel type gracefully', async () => {
    vi.mocked(apiClient.getPanelData).mockResolvedValueOnce({
      panel_id: 'cpu_usage',
      panel_type: 'kpi',
      data: { value: 75.3 },
    })

    render(
      <TimeSeriesPanel
        panelId="cpu_usage"
        tenantId="tenant_alpha"
        dateRange={mockDateRange}
      />
    )

    await waitFor(() => {
      expect(screen.getByText(/no data available/i)).toBeInTheDocument()
    })
  })
})
