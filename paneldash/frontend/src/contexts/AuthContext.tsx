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
      const kc = new Keycloak(keycloakConfig)

      try {
        const authenticated = await kc.init({
          onLoad: 'check-sso',
          silentCheckSsoRedirectUri: window.location.origin + '/silent-check-sso.html',
          pkceMethod: 'S256',
        })

        setKeycloak(kc)

        if (authenticated && kc.token) {
          // Set token in API client
          apiClient.setToken(kc.token)

          // Fetch user info from backend
          try {
            const userData = await apiClient.getMe()
            setUser(userData)
            setIsAuthenticated(true)
          } catch (error) {
            console.error('Failed to fetch user info:', error)
            // Token might be invalid, try to logout
            await kc.logout()
          }

          // Set up token refresh
          kc.onTokenExpired = () => {
            kc
              .updateToken(30)
              .then((refreshed) => {
                if (refreshed && kc.token) {
                  apiClient.setToken(kc.token)
                  console.log('Token refreshed')
                }
              })
              .catch((error) => {
                console.error('Failed to refresh token:', error)
                setIsAuthenticated(false)
                setUser(null)
              })
          }
        } else {
          // Keycloak not authenticated - check for E2E test token in localStorage
          const existingToken = localStorage.getItem('auth_token')
          if (existingToken) {
            console.log('Found existing auth token in localStorage, attempting to authenticate for E2E testing')
            apiClient.setToken(existingToken)

            try {
              const userData = await apiClient.getMe()
              setUser(userData)
              setIsAuthenticated(true)
              console.log('Successfully authenticated with localStorage token (E2E mode)')
            } catch (error) {
              console.error('Failed to authenticate with localStorage token:', error)
              // Clear invalid token
              localStorage.removeItem('auth_token')
              apiClient.setToken(null)
            }
          }
        }
      } catch (error) {
        console.error('Keycloak initialization failed:', error)

        // Fallback: try localStorage token for E2E testing
        const existingToken = localStorage.getItem('auth_token')
        if (existingToken) {
          console.log('Keycloak failed, attempting localStorage token for E2E testing')
          apiClient.setToken(existingToken)

          try {
            const userData = await apiClient.getMe()
            setUser(userData)
            setIsAuthenticated(true)
            console.log('Successfully authenticated with localStorage token (E2E mode)')
          } catch (error) {
            console.error('Failed to authenticate with localStorage token:', error)
            localStorage.removeItem('auth_token')
            apiClient.setToken(null)
          }
        }
      } finally {
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
      // Call backend logout endpoint
      if (isAuthenticated) {
        await apiClient.logout()
      }
    } catch (error) {
      console.error('Backend logout failed:', error)
    } finally {
      // Always logout from Keycloak
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
