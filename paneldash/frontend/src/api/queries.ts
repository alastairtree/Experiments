import { useQuery, UseQueryResult } from '@tanstack/react-query'
import { apiClient, PanelData } from './client'
import type { DateRange } from '../components/DateFilter'

export interface PanelQueryParams {
  panelId: string
  tenantId: string
  dateRange: DateRange
  disableAggregation?: boolean
}

/**
 * Custom hook for fetching panel data with auto-refresh
 *
 * @param params - Panel query parameters
 * @param refreshInterval - Refresh interval in seconds (from panel config), defaults to 300s (5 min)
 * @param enabled - Whether the query is enabled
 * @returns Query result with panel data
 */
export function usePanelData(
  params: PanelQueryParams,
  refreshInterval: number = 300,
  enabled: boolean = true
): UseQueryResult<PanelData> & { lastUpdated: Date | null } {
  const { panelId, tenantId, dateRange, disableAggregation } = params

  const queryResult = useQuery({
    queryKey: ['panel', panelId, tenantId, dateRange.from, dateRange.to, disableAggregation],
    queryFn: async () => {
      const fetchParams = {
        date_from: dateRange.from?.toISOString(),
        date_to: dateRange.to?.toISOString(),
        disable_aggregation: disableAggregation,
      }

      return await apiClient.getPanelData(tenantId, panelId, fetchParams)
    },
    enabled: enabled && !!tenantId,
    // Convert seconds to milliseconds for refetchInterval
    refetchInterval: refreshInterval * 1000,
    // Keep previous data while refetching to prevent flash
    placeholderData: (previousData) => previousData,
  })

  return {
    ...queryResult,
    lastUpdated: queryResult.dataUpdatedAt ? new Date(queryResult.dataUpdatedAt) : null,
  }
}

/**
 * Helper to format last updated time
 *
 * @param date - Date to format
 * @returns Formatted time string
 */
export function formatLastUpdated(date: Date | null): string {
  if (!date) return 'Never'

  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffSeconds = Math.floor(diffMs / 1000)

  if (diffSeconds < 60) {
    return `${diffSeconds}s ago`
  }

  const diffMinutes = Math.floor(diffSeconds / 60)
  if (diffMinutes < 60) {
    return `${diffMinutes}m ago`
  }

  const diffHours = Math.floor(diffMinutes / 60)
  if (diffHours < 24) {
    return `${diffHours}h ago`
  }

  return date.toLocaleString()
}
