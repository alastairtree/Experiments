import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import TenantSelector from '../../components/TenantSelector'
import * as TenantContext from '../../contexts/TenantContext'

// Mock the useTenant hook
vi.mock('../../contexts/TenantContext', () => ({
  useTenant: vi.fn(),
  TenantProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

describe('TenantSelector', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should show loading state while tenants are being fetched', () => {
    vi.mocked(TenantContext.useTenant).mockReturnValue({
      selectedTenant: null,
      setSelectedTenant: vi.fn(),
      tenants: [],
      isLoadingTenants: true,
    })

    render(<TenantSelector />)

    expect(screen.getByText('Loading tenants...')).toBeInTheDocument()
  })

  it('should show "No tenants available" when tenant list is empty', () => {
    vi.mocked(TenantContext.useTenant).mockReturnValue({
      selectedTenant: null,
      setSelectedTenant: vi.fn(),
      tenants: [],
      isLoadingTenants: false,
    })

    render(<TenantSelector />)

    expect(screen.getByText('No tenants available')).toBeInTheDocument()
  })

  it('should render select dropdown with tenants', () => {
    const mockTenants = [
      { id: '1', tenant_id: 't1', name: 'Tenant 1', is_active: true },
      { id: '2', tenant_id: 't2', name: 'Tenant 2', is_active: true },
    ]

    vi.mocked(TenantContext.useTenant).mockReturnValue({
      selectedTenant: mockTenants[0],
      setSelectedTenant: vi.fn(),
      tenants: mockTenants,
      isLoadingTenants: false,
    })

    render(<TenantSelector />)

    expect(screen.getByText('Tenant:')).toBeInTheDocument()
    expect(screen.getByRole('combobox')).toBeInTheDocument()
  })

  it('should call setSelectedTenant when selection changes', async () => {
    const mockSetSelectedTenant = vi.fn()
    const mockTenants = [
      { id: '1', tenant_id: 't1', name: 'Tenant 1', is_active: true },
      { id: '2', tenant_id: 't2', name: 'Tenant 2', is_active: true },
    ]

    vi.mocked(TenantContext.useTenant).mockReturnValue({
      selectedTenant: mockTenants[0],
      setSelectedTenant: mockSetSelectedTenant,
      tenants: mockTenants,
      isLoadingTenants: false,
    })

    const user = userEvent.setup()
    render(<TenantSelector />)

    const select = screen.getByRole('combobox')
    await user.selectOptions(select, '2')

    expect(mockSetSelectedTenant).toHaveBeenCalledWith(mockTenants[1])
  })

  it('should show "Inactive" badge for inactive tenants', () => {
    const mockTenants = [
      { id: '1', tenant_id: 't1', name: 'Tenant 1', is_active: false },
    ]

    vi.mocked(TenantContext.useTenant).mockReturnValue({
      selectedTenant: mockTenants[0],
      setSelectedTenant: vi.fn(),
      tenants: mockTenants,
      isLoadingTenants: false,
    })

    render(<TenantSelector />)

    expect(screen.getByText('Inactive')).toBeInTheDocument()
  })
})
