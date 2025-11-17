import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Health from '../../pages/Health'

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })

  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
}

describe('Health Component', () => {
  it('renders the health check title', () => {
    render(<Health />, { wrapper: createWrapper() })
    expect(screen.getByText('System Health Check')).toBeInTheDocument()
  })

  it('displays endpoint information', () => {
    render(<Health />, { wrapper: createWrapper() })
    expect(screen.getByText('Endpoint')).toBeInTheDocument()
    expect(screen.getByText('/health')).toBeInTheDocument()
  })
})
