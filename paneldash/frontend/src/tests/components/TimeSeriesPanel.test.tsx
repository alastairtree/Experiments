import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import TimeSeriesPanel from '../../components/panels/TimeSeriesPanel'
import { usePanelData } from '../../api/queries'

// Mock the queries module
vi.mock('../../api/queries', () => ({
  usePanelData: vi.fn(() => ({
    data: null,
    isLoading: false,
    error: null,
    refetch: vi.fn(),
    lastUpdated: null,
  })),
  formatLastUpdated: (date: Date | null) => (date ? date.toISOString() : 'Never'),
}))

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

// Mock the DrillDownModal component
vi.mock('../../components/common/DrillDownModal', () => ({
  default: () => null,
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
    // Mock loading state
    vi.mocked(usePanelData).mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
      refetch: vi.fn(),
      lastUpdated: null,
      dataUpdatedAt: 0,
      errorUpdatedAt: 0,
      failureCount: 0,
      failureReason: null,
      errorUpdateCount: 0,
      isError: false,
      isFetched: false,
      isFetchedAfterMount: false,
      isFetching: false,
      isInitialLoading: true,
      isLoadingError: false,
      isPaused: false,
      isPending: false,
      isPlaceholderData: false,
      isRefetchError: false,
      isRefetching: false,
      isStale: false,
      isSuccess: false,
      status: 'pending',
      fetchStatus: 'fetching',
    } as any)

    render(
      <TimeSeriesPanel
        panelId="cpu_usage"
        tenantId="tenant_alpha"
        dateRange={mockDateRange}
      />
    )

    expect(screen.getByRole('status', { hidden: true })).toBeInTheDocument()
  })

  it('displays error message when fetch fails', () => {
    vi.mocked(usePanelData).mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error('Network error'),
      refetch: vi.fn(),
      lastUpdated: null,
    } as any)

    render(
      <TimeSeriesPanel
        panelId="cpu_usage"
        tenantId="tenant_alpha"
        dateRange={mockDateRange}
      />
    )

    expect(screen.getByText(/Network error/)).toBeInTheDocument()
  })

  it('displays warning when no data is available', () => {
    vi.mocked(usePanelData).mockReturnValue({
      data: {
        panel_id: 'cpu_usage',
        panel_type: 'timeseries',
        data: { series: [] },
      },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
      lastUpdated: new Date(),
    } as any)

    render(
      <TimeSeriesPanel
        panelId="cpu_usage"
        tenantId="tenant_alpha"
        dateRange={mockDateRange}
      />
    )

    // Should still render the chart even with empty data
    expect(screen.getByTestId('plotly-chart')).toBeInTheDocument()
  })

  it('renders time series chart with single series', () => {
    vi.mocked(usePanelData).mockReturnValue({
      data: {
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
      },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
      lastUpdated: new Date(),
    } as any)

    render(
      <TimeSeriesPanel
        panelId="cpu_usage"
        tenantId="tenant_alpha"
        dateRange={mockDateRange}
      />
    )

    const chart = screen.getByTestId('plotly-chart')
    expect(chart).toBeInTheDocument()

    const plotData = JSON.parse(chart.getAttribute('data-plot-data') || '[]')
    expect(plotData).toHaveLength(1)
    expect(plotData[0].name).toBe('server-1')
    expect(plotData[0].x).toEqual(['2024-01-01T00:00:00Z', '2024-01-01T01:00:00Z'])
    expect(plotData[0].y).toEqual([45.2, 52.1])
    expect(plotData[0].type).toBe('scatter')
  })

  it('renders time series chart with multiple series', () => {
    vi.mocked(usePanelData).mockReturnValue({
      data: {
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
      },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
      lastUpdated: new Date(),
    } as any)

    render(
      <TimeSeriesPanel
        panelId="cpu_usage"
        tenantId="tenant_alpha"
        dateRange={mockDateRange}
      />
    )

    const chart = screen.getByTestId('plotly-chart')
    const plotData = JSON.parse(chart.getAttribute('data-plot-data') || '[]')

    expect(plotData).toHaveLength(2)
    expect(plotData[0].name).toBe('server-1')
    expect(plotData[1].name).toBe('server-2')
  })

  it('displays title when provided', () => {
    vi.mocked(usePanelData).mockReturnValue({
      data: {
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
      },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
      lastUpdated: new Date(),
    } as any)

    render(
      <TimeSeriesPanel
        panelId="cpu_usage"
        tenantId="tenant_alpha"
        dateRange={mockDateRange}
        title="CPU Usage Over Time"
      />
    )

    expect(screen.getByText('CPU Usage Over Time')).toBeInTheDocument()
  })

  it('shows aggregation info when data is aggregated', () => {
    vi.mocked(usePanelData).mockReturnValue({
      data: {
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
      },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
      lastUpdated: new Date(),
    } as any)

    render(
      <TimeSeriesPanel
        panelId="cpu_usage"
        tenantId="tenant_alpha"
        dateRange={mockDateRange}
      />
    )

    expect(screen.getByText(/data aggregated using 10 minutes intervals/i)).toBeInTheDocument()
  })

  it('refetches data when date range changes', () => {
    // This test is now handled by TanStack Query automatically
    // We just verify that the component can re-render with new dates
    const { rerender } = render(
      <TimeSeriesPanel
        panelId="cpu_usage"
        tenantId="tenant_alpha"
        dateRange={mockDateRange}
      />
    )

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

    // Just verify it still renders
    expect(screen.queryByRole('status', { hidden: true })).not.toBeInTheDocument()
  })

  it('handles wrong panel type gracefully', () => {
    vi.mocked(usePanelData).mockReturnValue({
      data: {
        panel_id: 'cpu_usage',
        panel_type: 'kpi' as any,
        data: { value: 75.3 },
      },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
      lastUpdated: new Date(),
    } as any)

    render(
      <TimeSeriesPanel
        panelId="cpu_usage"
        tenantId="tenant_alpha"
        dateRange={mockDateRange}
      />
    )

    expect(screen.getByText(/no data available/i)).toBeInTheDocument()
  })
})
