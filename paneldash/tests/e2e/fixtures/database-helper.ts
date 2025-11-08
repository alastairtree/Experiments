/**
 * Database Helper for E2E Tests
 *
 * Provides functions to setup and teardown test data in the database
 */

import { request } from '@playwright/test'

const API_URL = process.env.VITE_API_URL || 'http://localhost:8001'

interface User {
  id: string
  keycloak_id: string
  email: string
  full_name?: string
  is_admin: boolean
}

interface Tenant {
  id: string
  name: string
  config_path: string
  is_active: boolean
}

/**
 * Create a user directly in the database via API
 * Note: This uses the auto-creation feature when a valid token is presented
 */
export async function createUserViaAuth(token: string): Promise<User> {
  const apiContext = await request.newContext()

  try {
    const response = await apiContext.get(`${API_URL}/api/v1/auth/me`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    })

    if (!response.ok()) {
      throw new Error(`Failed to create user: ${response.status()} ${await response.text()}`)
    }

    const user = await response.json()
    return user
  } finally {
    await apiContext.dispose()
  }
}

/**
 * Create a tenant in the database
 */
export async function createTenant(token: string, tenant: Partial<Tenant>): Promise<Tenant> {
  const apiContext = await request.newContext()

  try {
    const response = await apiContext.post(`${API_URL}/api/v1/tenants`, {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      data: {
        name: tenant.name || 'Test Tenant',
        config_path: tenant.config_path || `/config/tenants/test-tenant`,
        is_active: tenant.is_active !== undefined ? tenant.is_active : true,
      },
    })

    if (!response.ok()) {
      throw new Error(`Failed to create tenant: ${response.status()} ${await response.text()}`)
    }

    return await response.json()
  } finally {
    await apiContext.dispose()
  }
}

/**
 * Assign a user to a tenant
 */
export async function assignUserToTenant(
  token: string,
  userId: string,
  tenantId: string
): Promise<void> {
  const apiContext = await request.newContext()

  try {
    const response = await apiContext.post(`${API_URL}/api/v1/users/${userId}/tenants/${tenantId}`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    })

    if (!response.ok()) {
      throw new Error(
        `Failed to assign user to tenant: ${response.status()} ${await response.text()}`
      )
    }
  } finally {
    await apiContext.dispose()
  }
}

/**
 * Clean up test data (this is a simple version, may need enhancement)
 */
export async function cleanupTestData(): Promise<void> {
  // For now, E2E tests use separate database instances
  // Cleanup happens automatically when test database is torn down
  // This function can be extended if needed for more specific cleanup
}
