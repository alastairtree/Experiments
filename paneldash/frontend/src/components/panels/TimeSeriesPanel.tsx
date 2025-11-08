import { useEffect, useState } from 'react'
import Plot from 'react-plotly.js'
import { Maximize2 } from 'lucide-react'
import { apiClient, PanelData } from '../../api/client'
import type { DateRange } from '../DateFilter'
import DrillDownModal from '../common/DrillDownModal'

interface TimeSeriesPanelProps {
  panelId: string
  tenantId: string
  dateRange: DateRange
  title?: string
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
}: TimeSeriesPanelProps) {
  const [data, setData] = useState<PanelData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showDrillDown, setShowDrillDown] = useState(false)

  useEffect(() => {
    const fetchData = async () => {
      if (!tenantId) return

      setLoading(true)
      setError(null)

      try {
        const params = {
          date_from: dateRange.from?.toISOString(),
          date_to: dateRange.to?.toISOString(),
        }

        const panelData = await apiClient.getPanelData(tenantId, panelId, params)
        setData(panelData)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load panel data')
        console.error('Failed to fetch time series data:', err)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [panelId, tenantId, dateRange])

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

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-md p-4">
        <p className="text-sm text-red-800">
          <strong>Error:</strong> {error}
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
          {title && <h3 className="text-lg font-medium text-gray-900">{title}</h3>}
          <button
            onClick={() => setShowDrillDown(true)}
            className="flex items-center gap-1 px-3 py-1 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-md transition-colors"
            aria-label="Expand panel"
          >
            <Maximize2 size={16} />
            <span>Expand</span>
          </button>
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
