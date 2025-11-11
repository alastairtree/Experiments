import { useTenant } from '../contexts/TenantContext'

export default function TenantSelector() {
  const { selectedTenant, setSelectedTenant, tenants, isLoadingTenants } =
    useTenant()

  if (isLoadingTenants) {
    return (
      <div className="flex items-center space-x-2">
        <div className="h-4 w-4 animate-spin rounded-full border-2 border-solid border-blue-600 border-r-transparent"></div>
        <span className="text-sm text-gray-600">Loading tenants...</span>
      </div>
    )
  }

  if (tenants.length === 0) {
    return (
      <div className="text-sm text-gray-600">
        No tenants available
      </div>
    )
  }

  return (
    <div className="flex items-center space-x-2">
      <label htmlFor="tenant-select" className="text-sm font-medium text-gray-700">
        Tenant:
      </label>
      <select
        id="tenant-select"
        value={selectedTenant?.id || ''}
        onChange={(e) => {
          const tenant = tenants.find((t) => t.id === e.target.value)
          setSelectedTenant(tenant || null)
        }}
        className="block w-64 rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
      >
        {tenants.map((tenant) => (
          <option key={tenant.id} value={tenant.id}>
            {tenant.name} ({tenant.tenant_id})
          </option>
        ))}
      </select>
      {selectedTenant && !selectedTenant.is_active && (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800">
          Inactive
        </span>
      )}
    </div>
  )
}
