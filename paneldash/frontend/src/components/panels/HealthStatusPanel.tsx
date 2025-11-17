import { useEffect, useState } from 'react'
import { formatDistanceToNow } from 'date-fns'
import { apiClient, PanelData } from '../../api/client'
import { DateRange } from '../DateFilter'

interface HealthStatusPanelProps {
  panelId: string
  tenantId: string
  title?: string
  dateRange: DateRange
}

interface ServiceStatus {
  service_name: string
  status_value: number
  status_label: string
  status_color: string
  last_check?: string
  error_message?: string
}

interface HealthStatusData {
  services: ServiceStatus[]
  query_executed?: string
}

/**
 * Health Status Panel Component
 *
 * Displays health status for multiple services with:
 * - Color-coded status dots (red/amber/green)
 * - Service names
 * - Human-readable timestamps
 * - Error messages on hover
 * - Loading and error states
 */
export default function HealthStatusPanel({
  panelId, tenantId, dateRange, 
}: HealthStatusPanelProps) {
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
        const panelData = await apiClient.getPanelData(tenantId, panelId)
        // TODO: Consider date range in future if needed
        // const panelData = await apiClient.getPanelData(tenantId, panelId, fetchParams)

        setData(panelData)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load health status')
        console.error('Failed to fetch health status:', err)
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

  if (!data || data.panel_type !== 'health_status') {
    return (
      <div className="bg-yellow-50 border border-yellow-200 rounded-md p-4">
        <p className="text-sm text-yellow-800">No health status data available.</p>
      </div>
    )
  }

  // Type guard
  const isHealthStatusData = (d: unknown): d is HealthStatusData => {
    return (
      d !== null &&
      typeof d === 'object' &&
      'services' in d &&
      Array.isArray((d as { services: unknown }).services)
    )
  }

  if (!isHealthStatusData(data.data)) {
    return (
      <div className="bg-yellow-50 border border-yellow-200 rounded-md p-4">
        <p className="text-sm text-yellow-800">Invalid health status data format.</p>
      </div>
    )
  }

  const healthData = data.data

  const formatTimestamp = (timestamp?: string) => {
    if (!timestamp) return 'Unknown'
    try {
      const date = new Date(timestamp)
      return formatDistanceToNow(date, { addSuffix: true })
    } catch {
      return 'Invalid date'
    }
  }

  const getStatusDotColor = (color: string) => {
    // Map hex colors to Tailwind classes
    const colorMap: Record<string, string> = {
      '#10B981': 'bg-green-500',
      '#F59E0B': 'bg-amber-500',
      '#EF4444': 'bg-red-500',
      '#6B7280': 'bg-gray-500',
    }

    return colorMap[color] || 'bg-gray-500'
  }

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      {data.title && <h3 className="text-lg font-medium text-gray-900 mb-4">{data.title}</h3>}

      {healthData.services.length === 0 ? (
        <p className="text-sm text-gray-500 text-center py-8">No services to display</p>
      ) : (
        <div className="space-y-3">
          {healthData.services.map((service, index) => (
            <div
              key={index}
              className="flex items-center justify-between p-3 rounded-md border border-gray-100 hover:bg-gray-50 transition-colors group"
              data-testid="service-status"
              title={service.error_message || ''}
            >
              <div className="flex items-center space-x-3">
                <div
                  className={`w-3 h-3 rounded-full ${getStatusDotColor(service.status_color)}`}
                  data-testid="status-dot"
                  aria-label={`Status: ${service.status_label}`}
                ></div>
                <div>
                  <p className="text-sm font-medium text-gray-900" data-testid="service-name">
                    {service.service_name}
                  </p>
                  {service.last_check && (
                    <p className="text-xs text-gray-500" data-testid="last-check">
                      Checked {formatTimestamp(service.last_check)}
                    </p>
                  )}
                </div>
              </div>
              <div className="flex items-center space-x-2">
                <span
                  className={`text-xs font-medium px-2 py-1 rounded ${
                    service.status_color === '#10B981'
                      ? 'bg-green-100 text-green-700'
                      : service.status_color === '#F59E0B'
                        ? 'bg-amber-100 text-amber-700'
                        : service.status_color === '#EF4444'
                          ? 'bg-red-100 text-red-700'
                          : 'bg-gray-100 text-gray-700'
                  }`}
                  data-testid="status-label"
                >
                  {service.status_label}
                </span>
                {service.error_message && (
                  <div className="relative group">
                    <svg
                      className="w-4 h-4 text-gray-400"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                      data-testid="error-icon"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                      />
                    </svg>
                    <div
                      className="absolute right-0 bottom-full mb-2 hidden group-hover:block w-64 p-2 bg-gray-900 text-white text-xs rounded shadow-lg z-10"
                      data-testid="error-tooltip"
                    >
                      {service.error_message}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}
          <small className="text-gray-400">NOTE: This is the latest data and is not filtered based on the date range.</small>
        </div>
      )}
    </div>
  )
}
