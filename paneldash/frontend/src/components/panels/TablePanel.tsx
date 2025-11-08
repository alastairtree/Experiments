import { useEffect, useState, useMemo } from 'react'
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getPaginationRowModel,
  ColumnDef,
  flexRender,
  SortingState,
} from '@tanstack/react-table'
import { apiClient, PanelData } from '../../api/client'
import type { DateRange } from '../DateFilter'

interface TablePanelProps {
  panelId: string
  tenantId: string
  dateRange?: DateRange
  title?: string
}

interface ColumnConfig {
  name: string
  display: string
  format?: string
}

interface TableData {
  columns: ColumnConfig[]
  rows: Record<string, unknown>[]
  pagination?: {
    current_page: number
    page_size: number
    total_rows: number
    total_pages: number
  }
  sort?: {
    column: string | null
    order: string
  }
  query_executed?: string
}

/**
 * Table Panel Component
 *
 * Displays tabular data with:
 * - Sorting on all columns
 * - Pagination controls
 * - Responsive mobile view
 * - Loading and error states
 */
export default function TablePanel({
  panelId,
  tenantId,
  dateRange,
  title,
}: TablePanelProps) {
  const [data, setData] = useState<PanelData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sorting, setSorting] = useState<SortingState>([])
  const [currentPage, setCurrentPage] = useState(1)

  useEffect(() => {
    const fetchData = async () => {
      if (!tenantId) return

      setLoading(true)
      setError(null)

      try {
        const params = {
          date_from: dateRange?.from?.toISOString(),
          date_to: dateRange?.to?.toISOString(),
          page: currentPage,
          sort_column: sorting[0]?.id || undefined,
          sort_order: (sorting[0]?.desc ? 'desc' : 'asc') as 'asc' | 'desc',
        }

        const panelData = await apiClient.getPanelData(tenantId, panelId, params)
        setData(panelData)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load table data')
        console.error('Failed to fetch table data:', err)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [panelId, tenantId, dateRange, currentPage, sorting])

  // Type guard
  const isTableData = (d: unknown): d is TableData => {
    return (
      d !== null &&
      typeof d === 'object' &&
      'columns' in d &&
      'rows' in d &&
      Array.isArray((d as { columns: unknown }).columns) &&
      Array.isArray((d as { rows: unknown }).rows)
    )
  }

  // Extract table data safely
  const tableData = data && data.panel_type === 'table' && isTableData(data.data) ? data.data : null

  // Create column definitions from API response
  const columns: ColumnDef<Record<string, unknown>>[] = useMemo(() => {
    if (!tableData) return []

    return tableData.columns.map((col) => ({
      accessorKey: col.name,
      header: col.display,
      cell: (info) => {
        const value = info.getValue()
        // Format based on column format type
        if (col.format === 'datetime' && typeof value === 'string') {
          try {
            return new Date(value).toLocaleString()
          } catch {
            return String(value)
          }
        }
        return String(value ?? '')
      },
    }))
  }, [tableData])

  // Initialize table with empty data if not loaded yet
  const table = useReactTable({
    data: tableData?.rows ?? [],
    columns,
    state: {
      sorting,
    },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    manualPagination: true,
    pageCount: tableData?.pagination?.total_pages ?? 1,
  })

  // Render loading state
  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div
          className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"
          role="status"
          aria-label="Loading"
        ></div>
      </div>
    )
  }

  // Render error state
  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-md p-4">
        <p className="text-sm text-red-800">
          <strong>Error:</strong> {error}
        </p>
      </div>
    )
  }

  // Render invalid panel type
  if (!data || data.panel_type !== 'table') {
    return (
      <div className="bg-yellow-50 border border-yellow-200 rounded-md p-4">
        <p className="text-sm text-yellow-800">No table data available.</p>
      </div>
    )
  }

  // Render invalid data format
  if (!tableData) {
    return (
      <div className="bg-yellow-50 border border-yellow-200 rounded-md p-4">
        <p className="text-sm text-yellow-800">Invalid table data format.</p>
      </div>
    )
  }

  const pagination = tableData.pagination

  return (
    <div className="rounded-lg border border-gray-200 bg-white">
      {title && (
        <div className="px-4 py-3 border-b border-gray-200">
          <h3 className="text-lg font-medium text-gray-900">{title}</h3>
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200" data-testid="data-table">
          <thead className="bg-gray-50">
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <th
                    key={header.id}
                    className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                    onClick={header.column.getToggleSortingHandler()}
                    data-testid="table-header"
                  >
                    <div className="flex items-center space-x-1">
                      <span>
                        {flexRender(header.column.columnDef.header, header.getContext())}
                      </span>
                      {header.column.getIsSorted() && (
                        <span data-testid="sort-indicator">
                          {header.column.getIsSorted() === 'asc' ? '↑' : '↓'}
                        </span>
                      )}
                    </div>
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {table.getRowModel().rows.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length}
                  className="px-6 py-4 text-center text-sm text-gray-500"
                  data-testid="empty-message"
                >
                  No data available
                </td>
              </tr>
            ) : (
              table.getRowModel().rows.map((row) => (
                <tr key={row.id} className="hover:bg-gray-50" data-testid="table-row">
                  {row.getVisibleCells().map((cell) => (
                    <td
                      key={cell.id}
                      className="px-6 py-4 whitespace-nowrap text-sm text-gray-900"
                      data-testid="table-cell"
                    >
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {pagination && pagination.total_pages > 1 && (
        <div className="px-4 py-3 border-t border-gray-200 sm:px-6">
          <div className="flex items-center justify-between">
            <div className="flex-1 flex justify-between sm:hidden">
              <button
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                disabled={pagination.current_page === 1}
                className="relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                data-testid="prev-button-mobile"
              >
                Previous
              </button>
              <button
                onClick={() => setCurrentPage((p) => Math.min(pagination.total_pages, p + 1))}
                disabled={pagination.current_page === pagination.total_pages}
                className="ml-3 relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                data-testid="next-button-mobile"
              >
                Next
              </button>
            </div>
            <div className="hidden sm:flex-1 sm:flex sm:items-center sm:justify-between">
              <div>
                <p className="text-sm text-gray-700" data-testid="pagination-info">
                  Showing page <span className="font-medium">{pagination.current_page}</span> of{' '}
                  <span className="font-medium">{pagination.total_pages}</span> (
                  <span className="font-medium">{pagination.total_rows}</span> total rows)
                </p>
              </div>
              <div>
                <nav className="relative z-0 inline-flex rounded-md shadow-sm -space-x-px">
                  <button
                    onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                    disabled={pagination.current_page === 1}
                    className="relative inline-flex items-center px-2 py-2 rounded-l-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                    data-testid="prev-button"
                  >
                    Previous
                  </button>
                  <button
                    onClick={() => setCurrentPage((p) => Math.min(pagination.total_pages, p + 1))}
                    disabled={pagination.current_page === pagination.total_pages}
                    className="relative inline-flex items-center px-2 py-2 rounded-r-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                    data-testid="next-button"
                  >
                    Next
                  </button>
                </nav>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
