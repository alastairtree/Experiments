import {
  createContext,
  useContext,
  useState,
  useEffect,
  ReactNode,
} from 'react'
import { useQuery } from '@tanstack/react-query'
import { apiClient, Tenant } from '../api/client'
import { useAuth } from './AuthContext'

interface TenantContextType {
  selectedTenant: Tenant | null
  setSelectedTenant: (tenant: Tenant | null) => void
  tenants: Tenant[]
  isLoadingTenants: boolean
}

const TenantContext = createContext<TenantContextType | undefined>(undefined)

export function TenantProvider({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth()
  const [selectedTenant, setSelectedTenant] = useState<Tenant | null>(null)

  // Fetch tenants when authenticated
  const {
    data: tenants = [],
    isLoading: isLoadingTenants,
  } = useQuery({
    queryKey: ['tenants'],
    queryFn: () => apiClient.getTenants(),
    enabled: isAuthenticated,
  })

  // Auto-select first tenant if available and none selected
  useEffect(() => {
    if (tenants.length > 0 && !selectedTenant) {
      // Try to restore from localStorage
      const savedTenantId = localStorage.getItem('selected_tenant_id')
      if (savedTenantId) {
        const savedTenant = tenants.find((t) => t.id === savedTenantId)
        if (savedTenant) {
          setSelectedTenant(savedTenant)
          return
        }
      }
      // Otherwise, select first tenant
      setSelectedTenant(tenants[0])
    }
  }, [tenants, selectedTenant])

  // Save selected tenant to localStorage
  useEffect(() => {
    if (selectedTenant) {
      localStorage.setItem('selected_tenant_id', selectedTenant.id)
    } else {
      localStorage.removeItem('selected_tenant_id')
    }
  }, [selectedTenant])

  return (
    <TenantContext.Provider
      value={{
        selectedTenant,
        setSelectedTenant,
        tenants,
        isLoadingTenants,
      }}
    >
      {children}
    </TenantContext.Provider>
  )
}

export function useTenant() {
  const context = useContext(TenantContext)
  if (context === undefined) {
    throw new Error('useTenant must be used within a TenantProvider')
  }
  return context
}
