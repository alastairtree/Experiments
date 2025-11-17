import { useEffect, useState } from 'react'
import { apiClient, PanelData } from '../../api/client'
import { DateRange } from '../DateFilter'

interface KPIPanelProps {
  panelId: string
  tenantId: string
  dateRange: DateRange
  title?: string
}

interface KPIData {
  value: number
  unit?: string
  decimals?: number
  threshold_status?: string
  threshold_color?: string
  query_executed?: string
}

/**
 * KPI Panel Component
 *
 * Displays a single key performance indicator with:
 * - Large, prominent metric value
 * - Color-coding based on thresholds
 * - Unit and label display
 * - Loading and error states
 */
export default function KPIPanel({ panelId, tenantId, dateRange, title }: KPIPanelProps) {
  const [data, setData] = useState<PanelData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchData = async () => {
      if (!tenantId) return

      setLoading(true)
      setError(null)

      try {
        const fetchParams = {
          date_from: dateRange.from?.toISOString(),
          date_to: dateRange.to?.toISOString(),
          disable_aggregation: true,
        }
        const panelData = await apiClient.getPanelData(tenantId, panelId, fetchParams)
        setData(panelData)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load KPI data')
        console.error('Failed to fetch KPI data:', err)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [panelId, tenantId])

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

  if (!data || data.panel_type !== 'kpi') {
    return (
      <div className="bg-yellow-50 border border-yellow-200 rounded-md p-4">
        <p className="text-sm text-yellow-800">No KPI data available for this panel.</p>
      </div>
    )
  }

  // Type guard to check if data has the expected structure
  const isKPIData = (d: unknown): d is KPIData => {
    return (
      d !== null &&
      typeof d === 'object' &&
      'value' in d &&
      typeof (d as { value: unknown }).value === 'number'
    )
  }

  if (!isKPIData(data.data)) {
    return (
      <div className="bg-yellow-50 border border-yellow-200 rounded-md p-4">
        <p className="text-sm text-yellow-800">Invalid KPI data format.</p>
      </div>
    )
  }

  const kpiData = data.data

  // Format the value with appropriate decimals
  const formattedValue = kpiData.value.toFixed(kpiData.decimals ?? 1)

  // Determine background color based on threshold
  const getBgColorClass = (color?: string) => {
    if (!color) return 'bg-gray-50'

    // Convert hex color to Tailwind-like classes or use inline style
    // For simplicity, we'll use predefined colors
    const colorMap: Record<string, string> = {
      '#10B981': 'bg-green-50',
      '#F59E0B': 'bg-amber-50',
      '#EF4444': 'bg-red-50',
    }

    return colorMap[color] || 'bg-gray-50'
  }

  const getTextColorClass = (color?: string) => {
    if (!color) return 'text-gray-900'

    const colorMap: Record<string, string> = {
      '#10B981': 'text-green-700',
      '#F59E0B': 'text-amber-700',
      '#EF4444': 'text-red-700',
    }

    return colorMap[color] || 'text-gray-900'
  }

  const getBorderColorClass = (color?: string) => {
    if (!color) return 'border-gray-200'

    const colorMap: Record<string, string> = {
      '#10B981': 'border-green-200',
      '#F59E0B': 'border-amber-200',
      '#EF4444': 'border-red-200',
    }

    return colorMap[color] || 'border-gray-200'
  }

  const bgColor = getBgColorClass(kpiData.threshold_color)
  const textColor = getTextColorClass(kpiData.threshold_color)
  const borderColor = getBorderColorClass(kpiData.threshold_color)

  return (
    <div className={`rounded-lg border-2 ${borderColor} ${bgColor} p-6`}>
      {title && (
        <h3 className="text-sm font-medium text-gray-600 mb-2 uppercase tracking-wide">
          {title}
        </h3>
      )}
      <div className="flex items-baseline justify-center">
        <span className={`text-5xl font-bold ${textColor}`} data-testid="kpi-value">
          {formattedValue}
        </span>
        {kpiData.unit && (
          <span className={`text-2xl font-medium ${textColor} ml-2`} data-testid="kpi-unit">
            {kpiData.unit}
          </span>
        )}
      </div>
      {kpiData.threshold_status && (
        <div className="mt-4 text-center">
          <span
            className={`inline-block px-3 py-1 rounded-full text-xs font-medium ${textColor} ${bgColor} border ${borderColor}`}
            data-testid="kpi-status"
          >
            {kpiData.threshold_status}
          </span>
        </div>
      )}
    </div>
  )
}
