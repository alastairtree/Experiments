import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import ProtectedRoute from '../../components/ProtectedRoute'
import * as AuthContext from '../../contexts/AuthContext'

// Mock the useAuth hook
vi.mock('../../contexts/AuthContext', () => ({
  useAuth: vi.fn(),
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

describe('ProtectedRoute', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should show loading state while authenticating', () => {
    vi.mocked(AuthContext.useAuth).mockReturnValue({
      isAuthenticated: false,
      isLoading: true,
      user: null,
      keycloak: null,
      login: vi.fn(),
      logout: vi.fn(),
    })

    render(
      <BrowserRouter>
        <ProtectedRoute>
          <div>Protected Content</div>
        </ProtectedRoute>
      </BrowserRouter>
    )

    expect(screen.getByText('Loading...')).toBeInTheDocument()
  })

  it('should render children when authenticated', () => {
    vi.mocked(AuthContext.useAuth).mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      user: {
        id: '1',
        email: 'test@example.com',
        full_name: 'Test User',
        keycloak_id: 'kc-1',
        is_admin: false,
        accessible_tenant_ids: [],
      },
      keycloak: null,
      login: vi.fn(),
      logout: vi.fn(),
    })

    render(
      <BrowserRouter>
        <ProtectedRoute>
          <div>Protected Content</div>
        </ProtectedRoute>
      </BrowserRouter>
    )

    expect(screen.getByText('Protected Content')).toBeInTheDocument()
  })

  it('should show 403 error for non-admin users when requireAdmin is true', () => {
    vi.mocked(AuthContext.useAuth).mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      user: {
        id: '1',
        email: 'test@example.com',
        full_name: 'Test User',
        keycloak_id: 'kc-1',
        is_admin: false,
        accessible_tenant_ids: [],
      },
      keycloak: null,
      login: vi.fn(),
      logout: vi.fn(),
    })

    render(
      <BrowserRouter>
        <ProtectedRoute requireAdmin>
          <div>Admin Content</div>
        </ProtectedRoute>
      </BrowserRouter>
    )

    expect(screen.getByText('403 Forbidden')).toBeInTheDocument()
    expect(
      screen.getByText("You don't have permission to access this page.")
    ).toBeInTheDocument()
  })

  it('should render children for admin users when requireAdmin is true', () => {
    vi.mocked(AuthContext.useAuth).mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      user: {
        id: '1',
        email: 'admin@example.com',
        full_name: 'Admin User',
        keycloak_id: 'kc-1',
        is_admin: true,
        accessible_tenant_ids: [],
      },
      keycloak: null,
      login: vi.fn(),
      logout: vi.fn(),
    })

    render(
      <BrowserRouter>
        <ProtectedRoute requireAdmin>
          <div>Admin Content</div>
        </ProtectedRoute>
      </BrowserRouter>
    )

    expect(screen.getByText('Admin Content')).toBeInTheDocument()
  })
})
