import { useState } from 'react'
import Plot from 'react-plotly.js'
import { Maximize2, RefreshCw } from 'lucide-react'
import type { DateRange } from '../DateFilter'
import DrillDownModal from '../common/DrillDownModal'
import { usePanelData, formatLastUpdated } from '../../api/queries'

interface TimeSeriesPanelProps {
  panelId: string
  tenantId: string
  dateRange: DateRange
  title?: string
  refreshInterval?: number // in seconds, defaults to 300 (5 min)
}

interface TimeSeriesData {
  series: Array<{
    timestamps: string[]
    values: number[]
    label: string
  }>
  query_executed?: string
}

/**
 * Time Series Panel Component
 *
 * Displays time-based line charts using Plotly.js
 * - Supports multiple series with different colors
 * - Interactive hover tooltips
 * - Loading and error states
 * - Responsive layout
 */
export default function TimeSeriesPanel({
  panelId,
  tenantId,
  dateRange,
  title,
  refreshInterval = 300,
}: TimeSeriesPanelProps) {
  const [showDrillDown, setShowDrillDown] = useState(false)

  // Use TanStack Query for data fetching with auto-refresh
  const { data, isLoading, error, refetch, lastUpdated } = usePanelData(
    { panelId, tenantId, dateRange },
    refreshInterval
  )

  const handleManualRefresh = () => {
    refetch()
  }

  if (isLoading) {
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

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-md p-4">
        <p className="text-sm text-red-800">
          <strong>Error:</strong> {error instanceof Error ? error.message : 'Failed to load panel data'}
        </p>
      </div>
    )
  }

  if (!data || data.panel_type !== 'timeseries') {
    return (
      <div className="bg-yellow-50 border border-yellow-200 rounded-md p-4">
        <p className="text-sm text-yellow-800">No data available for this panel.</p>
      </div>
    )
  }

  // Type guard to check if data has the expected structure
  const isTimeSeriesData = (d: unknown): d is TimeSeriesData => {
    return (
      d !== null &&
      typeof d === 'object' &&
      'series' in d &&
      Array.isArray((d as { series: unknown }).series)
    )
  }

  if (!isTimeSeriesData(data.data)) {
    return (
      <div className="bg-yellow-50 border border-yellow-200 rounded-md p-4">
        <p className="text-sm text-yellow-800">Invalid data format for time series panel.</p>
      </div>
    )
  }

  const timeSeriesData = data.data

  // Convert data to Plotly format
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
    <>
      <div className="w-full">
        <div className="flex items-center justify-between mb-4">
          <div>
            {title && <h3 className="text-lg font-medium text-gray-900">{title}</h3>}
            <p className="text-xs text-gray-500 mt-1">
              Last updated: {formatLastUpdated(lastUpdated)}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleManualRefresh}
              className="flex items-center gap-1 px-3 py-1 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-md transition-colors"
              aria-label="Refresh data"
              title="Refresh data"
            >
              <RefreshCw size={16} />
            </button>
            <button
              onClick={() => setShowDrillDown(true)}
              className="flex items-center gap-1 px-3 py-1 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-md transition-colors"
              aria-label="Expand panel"
            >
              <Maximize2 size={16} />
              <span>Expand</span>
            </button>
          </div>
        </div>
        <Plot
        data={plotData}
        layout={{
          autosize: true,
          margin: { l: 50, r: 20, t: 20, b: 40 },
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
          modeBarButtonsToRemove: ['lasso2d', 'select2d'],
        }}
        useResizeHandler
        style={{ width: '100%', height: '400px' }}
      />
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
            <p className="text-xs text-gray-500 mt-2">
              Data aggregated using {String(info.bucket_interval)} intervals
            </p>
          )
        }
        return null
      })()}
      </div>

      <DrillDownModal
        isOpen={showDrillDown}
        onClose={() => setShowDrillDown(false)}
        panelId={panelId}
        panelType="timeseries"
        tenantId={tenantId}
        dateRange={dateRange}
        title={title || 'Time Series'}
      />
    </>
  )
}
