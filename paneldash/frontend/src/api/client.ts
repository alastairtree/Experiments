const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export interface HealthResponse {
  status: string
}

export class ApiClient {
  private baseUrl: string

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl
  }

  async getHealth(): Promise<HealthResponse> {
    const response = await fetch(`${this.baseUrl}/health`)
    if (!response.ok) {
      throw new Error(`Health check failed: ${response.statusText}`)
    }
    return response.json()
  }
}

export const apiClient = new ApiClient()
