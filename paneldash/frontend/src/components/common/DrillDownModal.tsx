import { useState, useEffect } from 'react'
import { X, Download } from 'lucide-react'
import Plot from 'react-plotly.js'
import { apiClient, PanelData } from '../../api/client'
import type { DateRange } from '../DateFilter'

interface DrillDownModalProps {
  isOpen: boolean
  onClose: () => void
  panelId: string
  panelType: string
  tenantId: string
  dateRange: DateRange
  title: string
}

interface TimeSeriesData {
  series: Array<{
    timestamps: string[]
    values: number[]
    label: string
  }>
  query_executed?: string
}

interface TableRow {
  [key: string]: string | number | null
}

/**
 * Drill Down Modal Component
 *
 * Full-screen modal for expanded panel view with:
 * - Larger chart display
 * - Data table view
 * - Aggregation toggle (for time series)
 * - CSV export functionality
 */
export default function DrillDownModal({
  isOpen,
  onClose,
  panelId,
  panelType,
  tenantId,
  dateRange,
  title,
}: DrillDownModalProps) {
  const [data, setData] = useState<PanelData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [disableAggregation, setDisableAggregation] = useState(false)
  const [showTable, setShowTable] = useState(false)

  useEffect(() => {
    if (!isOpen || !tenantId) return

    const fetchData = async () => {
      setLoading(true)
      setError(null)

      try {
        const params = {
          date_from: dateRange.from?.toISOString(),
          date_to: dateRange.to?.toISOString(),
          disable_aggregation: disableAggregation,
        }

        const panelData = await apiClient.getPanelData(tenantId, panelId, params)
        setData(panelData)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load panel data')
        console.error('Failed to fetch drill-down data:', err)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [panelId, tenantId, dateRange, isOpen, disableAggregation])

  const exportToCSV = () => {
    if (!data) return

    let csvContent = ''
    let filename = `${panelId}-export.csv`

    if (panelType === 'timeseries' && isTimeSeriesData(data.data)) {
      const timeSeriesData = data.data
      // CSV header
      const headers = ['timestamp', 'value', 'series']
      csvContent = headers.join(',') + '\n'

      // CSV rows
      timeSeriesData.series.forEach((series) => {
        series.timestamps.forEach((timestamp, idx) => {
          const row = [timestamp, series.values[idx], series.label]
          csvContent += row.join(',') + '\n'
        })
      })
    } else if (panelType === 'table' && Array.isArray((data.data as any).rows)) {
      const tableData = data.data as { rows: TableRow[]; columns: any[] }
      // CSV header
      const headers = tableData.columns.map((col) => col.name)
      csvContent = headers.join(',') + '\n'

      // CSV rows
      tableData.rows.forEach((row) => {
        const values = headers.map((header) => {
          const val = row[header]
          // Escape commas and quotes
          if (typeof val === 'string' && (val.includes(',') || val.includes('"'))) {
            return `"${val.replace(/"/g, '""')}"`
          }
          return val ?? ''
        })
        csvContent += values.join(',') + '\n'
      })
    } else {
      // Generic JSON export for other panel types
      csvContent = JSON.stringify(data.data, null, 2)
      filename = `${panelId}-export.json`
    }

    // Create download link
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const link = document.createElement('a')
    const url = URL.createObjectURL(blob)
    link.setAttribute('href', url)
    link.setAttribute('download', filename)
    link.style.visibility = 'hidden'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  const isTimeSeriesData = (d: unknown): d is TimeSeriesData => {
    return (
      d !== null &&
      typeof d === 'object' &&
      'series' in d &&
      Array.isArray((d as { series: unknown }).series)
    )
  }

  const renderChart = () => {
    if (!data) return null

    if (panelType === 'timeseries' && isTimeSeriesData(data.data)) {
      const timeSeriesData = data.data

      const plotData = timeSeriesData.series.map((series) => ({
        x: series.timestamps,
        y: series.values,
        name: series.label,
        type: 'scatter' as const,
        mode: 'lines+markers' as const,
        marker: { size: 4 },
        line: { width: 2 },
      }))

      return (
        <Plot
          data={plotData}
          layout={{
            autosize: true,
            margin: { l: 60, r: 40, t: 40, b: 60 },
            xaxis: {
              title: 'Time',
              type: 'date',
            },
            yaxis: {
              title: 'Value',
            },
            hovermode: 'closest',
            showlegend: timeSeriesData.series.length > 1,
            legend: {
              orientation: 'h',
              yanchor: 'bottom',
              y: 1.02,
              xanchor: 'right',
              x: 1,
            },
          }}
          config={{
            responsive: true,
            displayModeBar: true,
            displaylogo: false,
          }}
          useResizeHandler
          style={{ width: '100%', height: '500px' }}
        />
      )
    }

    return (
      <div className="bg-gray-50 border border-gray-200 rounded-md p-4">
        <p className="text-sm text-gray-600">Chart preview not available for this panel type.</p>
      </div>
    )
  }

  const renderTable = () => {
    if (!data || !showTable) return null

    if (panelType === 'timeseries' && isTimeSeriesData(data.data)) {
      const timeSeriesData = data.data

      // Flatten series data into table format
      const rows: Array<{ timestamp: string; value: number; series: string }> = []
      timeSeriesData.series.forEach((series) => {
        series.timestamps.forEach((timestamp, idx) => {
          rows.push({
            timestamp,
            value: series.values[idx],
            series: series.label,
          })
        })
      })

      return (
        <div className="mt-6 overflow-x-auto">
          <h3 className="text-lg font-medium text-gray-900 mb-3">Data Table</h3>
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Timestamp
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Value
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Series
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {rows.slice(0, 100).map((row, idx) => (
                <tr key={idx}>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {new Date(row.timestamp).toLocaleString()}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {row.value.toFixed(2)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{row.series}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {rows.length > 100 && (
            <p className="text-sm text-gray-500 mt-2">
              Showing first 100 of {rows.length} rows. Export to CSV for complete data.
            </p>
          )}
        </div>
      )
    }

    return null
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black bg-opacity-50 transition-opacity" onClick={onClose} />

      {/* Modal */}
      <div className="flex min-h-full items-center justify-center p-4">
        <div className="relative bg-white rounded-lg shadow-xl max-w-7xl w-full max-h-[90vh] overflow-y-auto">
          {/* Header */}
          <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
            <h2 className="text-2xl font-bold text-gray-900">{title}</h2>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 transition-colors"
              aria-label="Close"
            >
              <X size={24} />
            </button>
          </div>

          {/* Content */}
          <div className="px-6 py-4">
            {loading && (
              <div className="flex items-center justify-center h-64">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600" />
              </div>
            )}

            {error && (
              <div className="bg-red-50 border border-red-200 rounded-md p-4">
                <p className="text-sm text-red-800">
                  <strong>Error:</strong> {error}
                </p>
              </div>
            )}

            {!loading && !error && data && (
              <>
                {/* Controls */}
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-4">
                    {panelType === 'timeseries' && (
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={disableAggregation}
                          onChange={(e) => setDisableAggregation(e.target.checked)}
                          className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                        />
                        <span className="text-sm text-gray-700">Disable Aggregation</span>
                      </label>
                    )}
                    {panelType === 'timeseries' && (
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={showTable}
                          onChange={(e) => setShowTable(e.target.checked)}
                          className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                        />
                        <span className="text-sm text-gray-700">Show Data Table</span>
                      </label>
                    )}
                  </div>

                  <button
                    onClick={exportToCSV}
                    className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
                  >
                    <Download size={16} />
                    <span>Export CSV</span>
                  </button>
                </div>

                {/* Chart */}
                {renderChart()}

                {/* Aggregation info */}
                {(() => {
                  const info = data.aggregation_info
                  if (
                    info &&
                    typeof info === 'object' &&
                    'applied' in info &&
                    info.applied &&
                    'bucket_interval' in info
                  ) {
                    return (
                      <p className="text-sm text-gray-500 mt-2">
                        Data aggregated using {String(info.bucket_interval)} intervals
                      </p>
                    )
                  }
                  return null
                })()}

                {/* Data Table */}
                {renderTable()}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
