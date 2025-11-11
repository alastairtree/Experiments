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
          onLoad: 'login-required',
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
        }
      } catch (error) {
        console.error('Keycloak initialization failed:', error)
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
