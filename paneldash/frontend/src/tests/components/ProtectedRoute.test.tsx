import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import ProtectedRoute from '../../components/ProtectedRoute'
import { AuthProvider } from '../../contexts/AuthContext'

// Mock the useAuth hook
vi.mock('../../contexts/AuthContext', async () => {
  const actual = await vi.importActual('../../contexts/AuthContext')
  return {
    ...actual,
    useAuth: vi.fn(),
  }
})

describe('ProtectedRoute', () => {
  it('should show loading state while authenticating', () => {
    const { useAuth } = require('../../contexts/AuthContext')
    useAuth.mockReturnValue({
      isAuthenticated: false,
      isLoading: true,
      user: null,
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
    const { useAuth } = require('../../contexts/AuthContext')
    useAuth.mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      user: { id: '1', email: 'test@example.com', is_admin: false },
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
    const { useAuth } = require('../../contexts/AuthContext')
    useAuth.mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      user: { id: '1', email: 'test@example.com', is_admin: false },
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
    const { useAuth } = require('../../contexts/AuthContext')
    useAuth.mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      user: { id: '1', email: 'admin@example.com', is_admin: true },
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
