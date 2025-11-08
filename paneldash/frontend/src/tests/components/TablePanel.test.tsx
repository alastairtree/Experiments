import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import TablePanel from '../../components/panels/TablePanel'
import { apiClient } from '../../api/client'

// Mock the API client
vi.mock('../../api/client', () => ({
  apiClient: {
    getPanelData: vi.fn(),
  },
}))

describe('TablePanel', () => {
  const mockDateRange = {
    from: new Date('2024-01-01T00:00:00Z'),
    to: new Date('2024-01-02T00:00:00Z'),
    preset: 'last_24h',
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows loading spinner while fetching data', () => {
    vi.mocked(apiClient.getPanelData).mockImplementation(
      () => new Promise(() => {}) // Never resolves
    )

    render(<TablePanel panelId="error_logs" tenantId="tenant_alpha" />)

    expect(screen.getByRole('status', { hidden: true })).toBeInTheDocument()
  })

  it('displays error message when fetch fails', async () => {
    vi.mocked(apiClient.getPanelData).mockRejectedValueOnce(new Error('Network error'))

    render(<TablePanel panelId="error_logs" tenantId="tenant_alpha" />)

    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument()
    })
  })

  it('displays warning when panel type is wrong', async () => {
    vi.mocked(apiClient.getPanelData).mockResolvedValueOnce({
      panel_id: 'error_logs',
      panel_type: 'kpi',
      data: { value: 75 },
    })

    render(<TablePanel panelId="error_logs" tenantId="tenant_alpha" />)

    await waitFor(() => {
      expect(screen.getByText(/no table data available/i)).toBeInTheDocument()
    })
  })

  it('displays table with data correctly', async () => {
    vi.mocked(apiClient.getPanelData).mockResolvedValueOnce({
      panel_id: 'error_logs',
      panel_type: 'table',
      data: {
        columns: [
          { name: 'timestamp', display: 'Time', format: 'datetime' },
          { name: 'message', display: 'Message' },
          { name: 'severity', display: 'Severity' },
        ],
        rows: [
          {
            timestamp: '2024-01-01T12:00:00Z',
            message: 'Error in API',
            severity: 'ERROR',
          },
          {
            timestamp: '2024-01-01T11:30:00Z',
            message: 'DB connection lost',
            severity: 'CRITICAL',
          },
        ],
        pagination: {
          current_page: 1,
          page_size: 25,
          total_rows: 2,
          total_pages: 1,
        },
      },
    })

    render(<TablePanel panelId="error_logs" tenantId="tenant_alpha" />)

    await waitFor(() => {
      expect(screen.getByTestId('data-table')).toBeInTheDocument()
      expect(screen.getAllByTestId('table-row')).toHaveLength(2)
    })
  })

  it('displays table headers correctly', async () => {
    vi.mocked(apiClient.getPanelData).mockResolvedValueOnce({
      panel_id: 'error_logs',
      panel_type: 'table',
      data: {
        columns: [
          { name: 'timestamp', display: 'Time' },
          { name: 'message', display: 'Message' },
        ],
        rows: [],
      },
    })

    render(<TablePanel panelId="error_logs" tenantId="tenant_alpha" />)

    await waitFor(() => {
      const headers = screen.getAllByTestId('table-header')
      expect(headers).toHaveLength(2)
      expect(headers[0]).toHaveTextContent('Time')
      expect(headers[1]).toHaveTextContent('Message')
    })
  })

  it('displays title when provided', async () => {
    vi.mocked(apiClient.getPanelData).mockResolvedValueOnce({
      panel_id: 'error_logs',
      panel_type: 'table',
      data: {
        columns: [{ name: 'message', display: 'Message' }],
        rows: [],
      },
    })

    render(
      <TablePanel
        panelId="error_logs"
        tenantId="tenant_alpha"
        title="Error Logs"
      />
    )

    await waitFor(() => {
      expect(screen.getByText('Error Logs')).toBeInTheDocument()
    })
  })

  it('displays empty message when no rows', async () => {
    vi.mocked(apiClient.getPanelData).mockResolvedValueOnce({
      panel_id: 'error_logs',
      panel_type: 'table',
      data: {
        columns: [{ name: 'message', display: 'Message' }],
        rows: [],
      },
    })

    render(<TablePanel panelId="error_logs" tenantId="tenant_alpha" />)

    await waitFor(() => {
      expect(screen.getByTestId('empty-message')).toBeInTheDocument()
      expect(screen.getByTestId('empty-message')).toHaveTextContent('No data available')
    })
  })

  it('allows sorting on columns', async () => {
    vi.mocked(apiClient.getPanelData).mockResolvedValue({
      panel_id: 'error_logs',
      panel_type: 'table',
      data: {
        columns: [
          { name: 'severity', display: 'Severity' },
          { name: 'message', display: 'Message' },
        ],
        rows: [
          { severity: 'ERROR', message: 'Error 1' },
          { severity: 'CRITICAL', message: 'Error 2' },
        ],
      },
    })

    render(<TablePanel panelId="error_logs" tenantId="tenant_alpha" />)

    await waitFor(() => {
      expect(screen.getAllByTestId('table-header')).toHaveLength(2)
    })

    // Click on header to sort
    const headers = screen.getAllByTestId('table-header')
    fireEvent.click(headers[0])

    await waitFor(() => {
      // Should show sort indicator
      expect(screen.getByTestId('sort-indicator')).toBeInTheDocument()
    })
  })

  it('displays pagination controls when multiple pages', async () => {
    vi.mocked(apiClient.getPanelData).mockResolvedValueOnce({
      panel_id: 'error_logs',
      panel_type: 'table',
      data: {
        columns: [{ name: 'message', display: 'Message' }],
        rows: [{ message: 'Error 1' }],
        pagination: {
          current_page: 1,
          page_size: 25,
          total_rows: 50,
          total_pages: 2,
        },
      },
    })

    render(<TablePanel panelId="error_logs" tenantId="tenant_alpha" />)

    await waitFor(() => {
      expect(screen.getByTestId('pagination-info')).toBeInTheDocument()
      expect(screen.getByTestId('prev-button')).toBeInTheDocument()
      expect(screen.getByTestId('next-button')).toBeInTheDocument()
    })
  })

  it('disables prev button on first page', async () => {
    vi.mocked(apiClient.getPanelData).mockResolvedValueOnce({
      panel_id: 'error_logs',
      panel_type: 'table',
      data: {
        columns: [{ name: 'message', display: 'Message' }],
        rows: [{ message: 'Error 1' }],
        pagination: {
          current_page: 1,
          page_size: 25,
          total_rows: 50,
          total_pages: 2,
        },
      },
    })

    render(<TablePanel panelId="error_logs" tenantId="tenant_alpha" />)

    await waitFor(() => {
      const prevButton = screen.getByTestId('prev-button')
      expect(prevButton).toBeDisabled()
    })
  })

  it('disables next button on last page', async () => {
    vi.mocked(apiClient.getPanelData).mockResolvedValueOnce({
      panel_id: 'error_logs',
      panel_type: 'table',
      data: {
        columns: [{ name: 'message', display: 'Message' }],
        rows: [{ message: 'Error 1' }],
        pagination: {
          current_page: 2,
          page_size: 25,
          total_rows: 50,
          total_pages: 2,
        },
      },
    })

    render(<TablePanel panelId="error_logs" tenantId="tenant_alpha" />)

    await waitFor(() => {
      const nextButton = screen.getByTestId('next-button')
      expect(nextButton).toBeDisabled()
    })
  })

  it('fetches new data when next page is clicked', async () => {
    vi.mocked(apiClient.getPanelData).mockResolvedValue({
      panel_id: 'error_logs',
      panel_type: 'table',
      data: {
        columns: [{ name: 'message', display: 'Message' }],
        rows: [{ message: 'Error 1' }],
        pagination: {
          current_page: 1,
          page_size: 25,
          total_rows: 50,
          total_pages: 2,
        },
      },
    })

    render(<TablePanel panelId="error_logs" tenantId="tenant_alpha" />)

    await waitFor(() => {
      expect(screen.getByTestId('next-button')).toBeInTheDocument()
    })

    // Click next button
    fireEvent.click(screen.getByTestId('next-button'))

    await waitFor(() => {
      expect(apiClient.getPanelData).toHaveBeenCalledWith(
        'tenant_alpha',
        'error_logs',
        expect.objectContaining({ page: 2 })
      )
    })
  })

  it('formats datetime columns correctly', async () => {
    vi.mocked(apiClient.getPanelData).mockResolvedValueOnce({
      panel_id: 'error_logs',
      panel_type: 'table',
      data: {
        columns: [{ name: 'timestamp', display: 'Time', format: 'datetime' }],
        rows: [{ timestamp: '2024-01-01T12:00:00Z' }],
      },
    })

    render(<TablePanel panelId="error_logs" tenantId="tenant_alpha" />)

    await waitFor(() => {
      // Should format the date (exact format depends on locale)
      const cells = screen.getAllByTestId('table-cell')
      expect(cells[0].textContent).toContain('2024')
    })
  })

  it('handles invalid data format gracefully', async () => {
    vi.mocked(apiClient.getPanelData).mockResolvedValueOnce({
      panel_id: 'error_logs',
      panel_type: 'table',
      data: {
        invalid: 'data',
      },
    })

    render(<TablePanel panelId="error_logs" tenantId="tenant_alpha" />)

    await waitFor(() => {
      expect(screen.getByText(/invalid table data format/i)).toBeInTheDocument()
    })
  })

  it('passes date range to API when provided', async () => {
    vi.mocked(apiClient.getPanelData).mockResolvedValueOnce({
      panel_id: 'error_logs',
      panel_type: 'table',
      data: {
        columns: [{ name: 'message', display: 'Message' }],
        rows: [],
      },
    })

    render(
      <TablePanel
        panelId="error_logs"
        tenantId="tenant_alpha"
        dateRange={mockDateRange}
      />
    )

    await waitFor(() => {
      expect(apiClient.getPanelData).toHaveBeenCalledWith(
        'tenant_alpha',
        'error_logs',
        expect.objectContaining({
          date_from: mockDateRange.from.toISOString(),
          date_to: mockDateRange.to.toISOString(),
        })
      )
    })
  })
})
