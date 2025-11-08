import { useEffect, useState } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { useTenant } from '../contexts/TenantContext'
import Header from '../components/Header'
import DashboardGrid from '../components/DashboardGrid'
import DateFilter, { DateRange } from '../components/DateFilter'
import { apiClient, Dashboard as DashboardType } from '../api/client'

export default function Dashboard() {
  const { user: _user } = useAuth()
  const { selectedTenant } = useTenant()
  const [dashboard, setDashboard] = useState<DashboardType | null>(null)
  const [dateRange, setDateRange] = useState<DateRange>({
    from: new Date(Date.now() - 24 * 60 * 60 * 1000),
    to: new Date(),
    preset: 'last_24h',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Load dashboard configuration
  useEffect(() => {
    if (!selectedTenant) {
      setDashboard(null)
      return
    }

    const loadDashboard = async () => {
      setLoading(true)
      setError(null)
      try {
        const data = await apiClient.getDashboard(selectedTenant.tenant_id)
        setDashboard(data)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load dashboard')
        console.error('Failed to load dashboard:', err)
      } finally {
        setLoading(false)
      }
    }

    loadDashboard()
  }, [selectedTenant])

  const handleDateChange = (range: DateRange) => {
    setDateRange(range)
    // Date range change will trigger panel data refresh via useEffect in panel components
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 sm:px-0">
          {!selectedTenant ? (
            <div className="border-4 border-dashed border-gray-200 rounded-lg p-8">
              <p className="text-gray-600">
                No tenant selected. Please select a tenant from the dropdown above.
              </p>
            </div>
          ) : loading ? (
            <div className="flex items-center justify-center p-12">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
            </div>
          ) : error ? (
            <div className="bg-red-50 border border-red-200 rounded-md p-4">
              <p className="text-sm text-red-800">
                <strong>Error:</strong> {error}
              </p>
            </div>
          ) : dashboard ? (
            <>
              {/* Dashboard header */}
              <div className="mb-6">
                <h1 className="text-2xl font-bold text-gray-900 mb-2">{dashboard.name}</h1>
                {dashboard.description && (
                  <p className="text-gray-600">{dashboard.description}</p>
                )}
              </div>

              {/* Date filter */}
              <div className="mb-6">
                <DateFilter onChange={handleDateChange} defaultPreset="last_24h" />
              </div>

              {/* Dashboard grid with panels */}
              {dashboard.panels.length > 0 ? (
                <DashboardGrid
                  panels={dashboard.panels}
                  columns={dashboard.layout?.columns || 12}
                >
                  {panelRef => (
                    <div>
                      <h3 className="text-lg font-medium text-gray-900 mb-2">{panelRef.id}</h3>
                      <p className="text-sm text-gray-500 mb-4">Config: {panelRef.config_file}</p>
                      <div className="bg-gray-100 rounded p-4 text-center">
                        <p className="text-sm text-gray-600">
                          Panel component will render here
                        </p>
                        <p className="text-xs text-gray-500 mt-2">
                          Date range: {dateRange.from?.toLocaleString()} -{' '}
                          {dateRange.to?.toLocaleString()}
                        </p>
                      </div>
                    </div>
                  )}
                </DashboardGrid>
              ) : (
                <div className="bg-blue-50 border border-blue-200 rounded-md p-4">
                  <p className="text-sm text-blue-800">
                    This dashboard has no panels configured yet.
                  </p>
                </div>
              )}
            </>
          ) : (
            <div className="bg-yellow-50 border border-yellow-200 rounded-md p-4">
              <p className="text-sm text-yellow-800">
                No dashboard found for this tenant.
              </p>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
