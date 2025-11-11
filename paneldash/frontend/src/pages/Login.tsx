import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

export default function Login() {
  const { isAuthenticated, isLoading, login, keycloak } = useAuth()
  const navigate = useNavigate()

  console.log(`🔐 Login page render: isLoading=${isLoading}, isAuthenticated=${isAuthenticated}, keycloak=${!!keycloak}`)

  useEffect(() => {
    console.log(`🔐 Login useEffect: isAuthenticated=${isAuthenticated}, isLoading=${isLoading}, keycloak=${!!keycloak}`)
    // Redirect to dashboard if already authenticated
    if (isAuthenticated) {
      console.log('🔐 Already authenticated, navigating to /dashboard')
      navigate('/dashboard')
    } else if (!isLoading && keycloak) {
      // Automatically redirect to Keycloak when page loads
      // This provides seamless authentication without requiring a button click
      console.log('🔐 Not authenticated, redirecting to Keycloak login...')
      keycloak.login({
        redirectUri: window.location.origin + '/dashboard'
      })
    }
  }, [isAuthenticated, isLoading, keycloak, navigate])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="text-center">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-blue-600 border-r-transparent"></div>
          <p className="mt-4 text-gray-600">Checking authentication...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-50">
      <div className="max-w-md w-full space-y-8 p-8 bg-white rounded-lg shadow-md">
        <div>
          <h1 className="text-3xl font-bold text-center text-gray-900">
            PanelDash
          </h1>
          <p className="mt-2 text-center text-gray-600">
            Multi-tenant Operations Dashboard
          </p>
        </div>
        <div className="mt-8 space-y-6">
          <button
            onClick={login}
            className="w-full flex justify-center py-3 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors"
          >
            Sign in with Keycloak
          </button>
          <p className="text-xs text-center text-gray-500">
            You will be redirected to Keycloak for authentication
          </p>
        </div>
      </div>
    </div>
  )
}
