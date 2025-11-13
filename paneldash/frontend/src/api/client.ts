const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export interface HealthResponse {
  status: string
}

export interface User {
  id: string
  email: string
  full_name: string
  keycloak_id: string
  is_admin: boolean
  accessible_tenant_ids: string[]
}

export interface Tenant {
  id: string
  tenant_id: string
  name: string
  is_active: boolean
}

export interface DashboardPanelReference {
  id: string
  config_file: string
  position?: {
    row: number
    col: number
    width: number
    height: number
  },
  type: string
}

export interface Dashboard {
  name: string
  description: string | null
  refresh_interval: number
  layout: { columns: number } | null
  panels: DashboardPanelReference[]
}

export interface PanelData {
  panel_id: string
  panel_type: 'timeseries' | 'kpi' | 'health_status' | 'table'
  data: Record<string, unknown>
  aggregation_info?: Record<string, unknown> | null
}

export class ApiClient {
  private baseUrl: string
  private token: string | null = null

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl
    // Try to load token from localStorage on initialization
    this.token = localStorage.getItem('auth_token')
  }

  setToken(token: string | null): void {
    this.token = token
    if (token) {
      localStorage.setItem('auth_token', token)
    } else {
      localStorage.removeItem('auth_token')
    }
  }

  getToken(): string | null {
    return this.token
  }

  private getHeaders(includeAuth: boolean = true): HeadersInit {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    }
    if (includeAuth && this.token) {
      headers['Authorization'] = `Bearer ${this.token}`
    }
    return headers
  }

  async getHealth(): Promise<HealthResponse> {
    const response = await fetch(`${this.baseUrl}/health`, {
      headers: this.getHeaders(false), // Health check doesn't need auth
    })
    if (!response.ok) {
      throw new Error(`Health check failed: ${response.statusText}`)
    }
    return response.json()
  }

  // Authentication endpoints
  async getMe(): Promise<User> {
    const response = await fetch(`${this.baseUrl}/api/v1/auth/me`, {
      headers: this.getHeaders(),
    })
    if (!response.ok) {
      if (response.status === 401) {
        throw new Error('Unauthorized')
      }
      throw new Error(`Failed to get user info: ${response.statusText}`)
    }
    return response.json()
  }

  async logout(): Promise<void> {
    const response = await fetch(`${this.baseUrl}/api/v1/auth/logout`, {
      method: 'POST',
      headers: this.getHeaders(),
    })
    if (!response.ok) {
      throw new Error(`Logout failed: ${response.statusText}`)
    }
    this.setToken(null)
  }

  // Tenant endpoints
  async getTenants(): Promise<Tenant[]> {
    const response = await fetch(`${this.baseUrl}/api/v1/tenants/`, {
      headers: this.getHeaders(),
    })
    if (!response.ok) {
      throw new Error(`Failed to get tenants: ${response.statusText}`)
    }
    return response.json()
  }

  async getTenant(tenantId: string): Promise<Tenant> {
    const response = await fetch(`${this.baseUrl}/api/v1/tenants/${tenantId}`, {
      headers: this.getHeaders(),
    })
    if (!response.ok) {
      throw new Error(`Failed to get tenant: ${response.statusText}`)
    }
    return response.json()
  }

  // User management endpoints (admin only)
  async getUsers(): Promise<User[]> {
    const response = await fetch(`${this.baseUrl}/api/v1/users/`, {
      headers: this.getHeaders(),
    })
    if (!response.ok) {
      throw new Error(`Failed to get users: ${response.statusText}`)
    }
    return response.json()
  }

  async getUser(userId: string): Promise<User> {
    const response = await fetch(`${this.baseUrl}/api/v1/users/${userId}`, {
      headers: this.getHeaders(),
    })
    if (!response.ok) {
      throw new Error(`Failed to get user: ${response.statusText}`)
    }
    return response.json()
  }

  async updateUser(userId: string, data: Partial<User>): Promise<User> {
    const response = await fetch(`${this.baseUrl}/api/v1/users/${userId}`, {
      method: 'PATCH',
      headers: this.getHeaders(),
      body: JSON.stringify(data),
    })
    if (!response.ok) {
      throw new Error(`Failed to update user: ${response.statusText}`)
    }
    return response.json()
  }

  async deleteUser(userId: string): Promise<void> {
    const response = await fetch(`${this.baseUrl}/api/v1/users/${userId}`, {
      method: 'DELETE',
      headers: this.getHeaders(),
    })
    if (!response.ok) {
      throw new Error(`Failed to delete user: ${response.statusText}`)
    }
  }

  async assignUserToTenant(tenantId: string, userId: string): Promise<void> {
    const response = await fetch(
      `${this.baseUrl}/api/v1/tenants/${tenantId}/users/${userId}`,
      {
        method: 'POST',
        headers: this.getHeaders(),
      }
    )
    if (!response.ok) {
      throw new Error(`Failed to assign user to tenant: ${response.statusText}`)
    }
  }

  async removeUserFromTenant(tenantId: string, userId: string): Promise<void> {
    const response = await fetch(
      `${this.baseUrl}/api/v1/tenants/${tenantId}/users/${userId}`,
      {
        method: 'DELETE',
        headers: this.getHeaders(),
      }
    )
    if (!response.ok) {
      throw new Error(`Failed to remove user from tenant: ${response.statusText}`)
    }
  }

  // Dashboard endpoints
  async getDashboards(tenantId: string): Promise<{ dashboards: string[] }> {
    const response = await fetch(
      `${this.baseUrl}/api/v1/dashboards?tenant_id=${encodeURIComponent(tenantId)}`,
      {
        headers: this.getHeaders(),
      }
    )
    if (!response.ok) {
      throw new Error(`Failed to get dashboards: ${response.statusText}`)
    }
    return response.json()
  }

  async getDashboard(tenantId: string, dashboardName: string = 'default'): Promise<Dashboard> {
    const response = await fetch(
      `${this.baseUrl}/api/v1/dashboards/${encodeURIComponent(dashboardName)}?tenant_id=${encodeURIComponent(tenantId)}`,
      {
        headers: this.getHeaders(),
      }
    )
    if (!response.ok) {
      throw new Error(`Failed to get dashboard: ${response.statusText}`)
    }
    return response.json()
  }

  // Panel data endpoints
  async getPanelData(
    tenantId: string,
    panelId: string,
    params?: {
      date_from?: string
      date_to?: string
      disable_aggregation?: boolean
      sort_column?: string
      sort_order?: 'asc' | 'desc'
      page?: number
    }
  ): Promise<PanelData> {
    const queryParams = new URLSearchParams({ tenant_id: tenantId })
    if (params) {
      if (params.date_from) queryParams.append('date_from', params.date_from)
      if (params.date_to) queryParams.append('date_to', params.date_to)
      if (params.disable_aggregation !== undefined)
        queryParams.append('disable_aggregation', String(params.disable_aggregation))
      if (params.sort_column) queryParams.append('sort_column', params.sort_column)
      if (params.sort_order) queryParams.append('sort_order', params.sort_order)
      if (params.page) queryParams.append('page', String(params.page))
    }

    const response = await fetch(
      `${this.baseUrl}/api/v1/panels/${encodeURIComponent(panelId)}/data?${queryParams}`,
      {
        headers: this.getHeaders(),
      }
    )
    if (!response.ok) {
      throw new Error(`Failed to get panel data: ${response.statusText}`)
    }
    return response.json()
  }
}

export const apiClient = new ApiClient()
