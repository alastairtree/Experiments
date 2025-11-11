import { createContext, useContext, useEffect, useState, ReactNode } from 'react'
import Keycloak from 'keycloak-js'
import { apiClient, User } from '../api/client'

interface AuthContextType {
  isAuthenticated: boolean
  isLoading: boolean
  user: User | null
  keycloak: Keycloak | null
  login: () => void
  logout: () => void
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

// Keycloak configuration
const keycloakConfig = {
  url: import.meta.env.VITE_KEYCLOAK_URL || 'http://localhost:8080',
  realm: import.meta.env.VITE_KEYCLOAK_REALM || 'paneldash',
  clientId: import.meta.env.VITE_KEYCLOAK_CLIENT_ID || 'paneldash-frontend',
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [user, setUser] = useState<User | null>(null)
  const [keycloak, setKeycloak] = useState<Keycloak | null>(null)

  useEffect(() => {
    const initKeycloak = async () => {
      console.log('🔐 [AuthContext] Initializing Keycloak...')
      console.log('🔐 [AuthContext] Current URL:', window.location.href)
      console.log('🔐 [AuthContext] URL hash:', window.location.hash)

      const kc = new Keycloak(keycloakConfig)

      // Set up Keycloak event handlers
      kc.onReady = (authenticated) => {
        console.log('🔐 [Keycloak Event] onReady - authenticated:', authenticated)
      }

      kc.onAuthSuccess = () => {
        console.log('✅ [Keycloak Event] onAuthSuccess - Authentication successful!')
        console.log('✅ [Keycloak Event] Token:', kc.token?.substring(0, 50) + '...')
        console.log('✅ [Keycloak Event] Refresh token:', kc.refreshToken?.substring(0, 50) + '...')
      }

      kc.onAuthError = (errorData) => {
        console.error('❌ [Keycloak Event] onAuthError:', errorData)
      }

      kc.onAuthRefreshSuccess = () => {
        console.log('🔄 [Keycloak Event] onAuthRefreshSuccess - Token refreshed')
      }

      kc.onAuthRefreshError = () => {
        console.error('❌ [Keycloak Event] onAuthRefreshError - Failed to refresh token')
      }

      kc.onAuthLogout = () => {
        console.log('🚪 [Keycloak Event] onAuthLogout - User logged out')
      }

      kc.onTokenExpired = () => {
        console.log('⏰ [Keycloak Event] onTokenExpired - Token has expired')
      }

      try {
        console.log('🔐 [AuthContext] Calling kc.init() with check-sso...')
        const authenticated = await kc.init({
          onLoad: 'check-sso',
          pkceMethod: 'S256',
          checkLoginIframe: false,
          enableLogging: true, // Enable Keycloak's internal logging
        })

        console.log('🔐 [AuthContext] kc.init() completed. Authenticated:', authenticated)
        console.log('🔐 [AuthContext] Has token:', !!kc.token)
        console.log('🔐 [AuthContext] Has refresh token:', !!kc.refreshToken)

        setKeycloak(kc)

        if (authenticated && kc.token) {
          console.log('✅ [AuthContext] User authenticated, setting token in API client')
          apiClient.setToken(kc.token)

          try {
            console.log('📡 [AuthContext] Fetching user data from backend...')
            const userData = await apiClient.getMe()
            console.log('✅ [AuthContext] User data fetched:', userData)
            setUser(userData)
            setIsAuthenticated(true)
          } catch (error) {
            console.error('❌ [AuthContext] Failed to fetch user info:', error)
          }
        } else {
          console.log('❌ [AuthContext] Not authenticated after init')
        }

        setIsLoading(false)
        console.log('🔐 [AuthContext] Initialization complete, isLoading set to false')
      } catch (error) {
        console.error('❌ [AuthContext] Keycloak initialization failed:', error)
        console.error('❌ [AuthContext] Error details:', JSON.stringify(error, null, 2))
        setIsLoading(false)
      }
    }

    initKeycloak()
  }, [])

  const login = () => {
    keycloak?.login()
  }

  const logout = async () => {
    try {
      if (isAuthenticated) {
        await apiClient.logout()
      }
    } catch (error) {
      console.error('Backend logout failed:', error)
    } finally {
      keycloak?.logout()
      setIsAuthenticated(false)
      setUser(null)
    }
  }

  return (
    <AuthContext.Provider
      value={{
        isAuthenticated,
        isLoading,
        user,
        keycloak,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
