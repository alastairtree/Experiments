import { useAuth } from '../contexts/AuthContext'
import { useTenant } from '../contexts/TenantContext'
import Header from '../components/Header'

export default function Dashboard() {
  const { user } = useAuth()
  const { selectedTenant } = useTenant()

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          <div className="border-4 border-dashed border-gray-200 rounded-lg p-8">
            <h1 className="text-2xl font-bold text-gray-900 mb-4">
              Welcome, {user?.full_name}!
            </h1>
            {selectedTenant ? (
              <>
                <p className="text-gray-600 mb-4">
                  Viewing data for <strong>{selectedTenant.name}</strong>
                </p>
                <div className="bg-white rounded-lg shadow p-6 mb-6">
                  <h2 className="text-lg font-semibold text-gray-900 mb-3">
                    Tenant Information
                  </h2>
                  <dl className="grid grid-cols-2 gap-4">
                    <div>
                      <dt className="text-sm font-medium text-gray-500">Name</dt>
                      <dd className="mt-1 text-sm text-gray-900">{selectedTenant.name}</dd>
                    </div>
                    <div>
                      <dt className="text-sm font-medium text-gray-500">Tenant ID</dt>
                      <dd className="mt-1 text-sm text-gray-900">{selectedTenant.tenant_id}</dd>
                    </div>
                    <div>
                      <dt className="text-sm font-medium text-gray-500">Status</dt>
                      <dd className="mt-1">
                        <span
                          className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                            selectedTenant.is_active
                              ? 'bg-green-100 text-green-800'
                              : 'bg-red-100 text-red-800'
                          }`}
                        >
                          {selectedTenant.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </dd>
                    </div>
                  </dl>
                </div>
                <div className="bg-blue-50 border border-blue-200 rounded-md p-4">
                  <p className="text-sm text-blue-800">
                    <strong>Coming soon:</strong> Panels and dashboards will be displayed here.
                  </p>
                </div>
              </>
            ) : (
              <p className="text-gray-600">
                No tenant selected. Please select a tenant from the dropdown above.
              </p>
            )}
          </div>
        </div>
      </main>
    </div>
  )
}
