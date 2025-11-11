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
      console.log('Initializing Keycloak...')
      const kc = new Keycloak(keycloakConfig)

      try {
        const authenticated = await kc.init({
          onLoad: 'check-sso',
          pkceMethod: 'S256',
          checkLoginIframe: false,
        })

        console.log('Keycloak initialized. Authenticated:', authenticated)
        setKeycloak(kc)

        if (authenticated && kc.token) {
          apiClient.setToken(kc.token)

          try {
            const userData = await apiClient.getMe()
            setUser(userData)
            setIsAuthenticated(true)
          } catch (error) {
            console.error('Failed to fetch user info:', error)
          }
        }

        setIsLoading(false)
      } catch (error) {
        console.error('Keycloak initialization failed:', error)
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
