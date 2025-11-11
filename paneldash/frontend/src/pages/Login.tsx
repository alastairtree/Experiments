import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

const REDIRECT_COOLDOWN_KEY = 'keycloak_redirect_timestamp'
const REDIRECT_COOLDOWN_MS = 15 * 60 * 1000 // 15 minutes

export default function Login() {
  const { isAuthenticated, isLoading, login, keycloak } = useAuth()
  const navigate = useNavigate()

  console.log(`🔐 [Login] Page render: isLoading=${isLoading}, isAuthenticated=${isAuthenticated}, keycloak=${!!keycloak}`)

  useEffect(() => {
    console.log(`🔐 [Login] useEffect triggered: isAuthenticated=${isAuthenticated}, isLoading=${isLoading}, keycloak=${!!keycloak}`)

    // Redirect to dashboard if already authenticated
    if (isAuthenticated) {
      console.log('✅ [Login] Already authenticated, navigating to /dashboard')
      navigate('/dashboard')
      return
    }

    if (!isLoading && keycloak) {
      // Check redirect cooldown to prevent infinite loops
      const lastRedirectStr = localStorage.getItem(REDIRECT_COOLDOWN_KEY)
      const now = Date.now()

      if (lastRedirectStr) {
        const lastRedirect = parseInt(lastRedirectStr, 10)
        const timeSinceLastRedirect = now - lastRedirect

        if (timeSinceLastRedirect < REDIRECT_COOLDOWN_MS) {
          const minutesRemaining = Math.ceil((REDIRECT_COOLDOWN_MS - timeSinceLastRedirect) / 60000)
          console.log(`⏸️ [Login] Redirect cooldown active. ${minutesRemaining} minutes until auto-redirect enabled`)
          console.log(`⏸️ [Login] User must click the login button manually`)
          return
        }
      }

      // Automatically redirect to Keycloak when page loads (only once per cooldown period)
      console.log('🔐 [Login] Auto-redirecting to Keycloak login...')
      localStorage.setItem(REDIRECT_COOLDOWN_KEY, now.toString())
      keycloak.login({
        redirectUri: window.location.origin + '/dashboard'
      })
    }
  }, [isAuthenticated, isLoading, keycloak, navigate])

  const handleManualLogin = () => {
    console.log('🔐 [Login] Manual login button clicked')
    if (keycloak) {
      // Update cooldown timestamp
      localStorage.setItem(REDIRECT_COOLDOWN_KEY, Date.now().toString())
      keycloak.login({
        redirectUri: window.location.origin + '/dashboard'
      })
    }
  }

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
            onClick={handleManualLogin}
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
