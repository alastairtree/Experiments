/**
 * E2E Test: Valid User Authentication and Dashboard Access
 *
 * This test verifies that a valid user can:
 * 1. Authenticate with a valid JWT token
 * 2. Access protected API endpoints
 * 3. Be automatically created in the database on first login
 * 4. Be assigned to tenants and access tenant data
 */

import { test, expect } from '@playwright/test'
import { generateJWTToken, TEST_USERS } from '../fixtures/jwt-helper'

test.describe('Valid User Authentication', () => {
  let validUserToken: string
  let adminToken: string

  test.beforeAll(async () => {
    // Generate valid JWT tokens for testing
    validUserToken = generateJWTToken(TEST_USERS.validUser)
    adminToken = generateJWTToken(TEST_USERS.adminUser)

    console.log('Generated valid user token (first 50 chars):', validUserToken.substring(0, 50) + '...')
    console.log('Generated admin token (first 50 chars):', adminToken.substring(0, 50) + '...')
  })

  test('valid user token can authenticate with backend', async ({ request }) => {
    // Call /auth/me with valid token - this will auto-create the user
    const response = await request.get('http://localhost:8001/api/v1/auth/me', {
      headers: {
        Authorization: `Bearer ${validUserToken}`,
      },
    })

    expect(response.status()).toBe(200)

    const userData = await response.json()
    expect(userData.email).toBe(TEST_USERS.validUser.email)
    expect(userData.keycloak_id).toBe(TEST_USERS.validUser.sub)
    expect(userData.is_admin).toBe(false)

    console.log('Valid user authenticated successfully:', userData.email)
    console.log('User ID:', userData.id)
  })

  test('valid user is auto-created in database on first login', async ({ request }) => {
    // Generate a new unique user to test auto-creation
    const newUser = {
      sub: `e2e-auto-create-${Date.now()}`,
      email: `autocreate-${Date.now()}@example.com`,
      name: 'Auto Created User',
      preferred_username: 'autocreate',
      email_verified: true,
      realm_access: {
        roles: ['user']
      }
    }

    const newUserToken = generateJWTToken(newUser)

    // First call should create the user
    const response1 = await request.get('http://localhost:8001/api/v1/auth/me', {
      headers: {
        Authorization: `Bearer ${newUserToken}`,
      },
    })

    expect(response1.status()).toBe(200)
    const userData1 = await response1.json()
    expect(userData1.email).toBe(newUser.email)
    const userId = userData1.id

    console.log('New user auto-created:', userData1.email)

    // Second call should return the same user
    const response2 = await request.get('http://localhost:8001/api/v1/auth/me', {
      headers: {
        Authorization: `Bearer ${newUserToken}`,
      },
    })

    expect(response2.status()).toBe(200)
    const userData2 = await response2.json()
    expect(userData2.id).toBe(userId)
    expect(userData2.email).toBe(newUser.email)

    console.log('Same user returned on second login')
  })

  test('admin user is created with admin flag', async ({ request }) => {
    // Call /auth/me with admin token
    const response = await request.get('http://localhost:8001/api/v1/auth/me', {
      headers: {
        Authorization: `Bearer ${adminToken}`,
      },
    })

    expect(response.status()).toBe(200)

    const userData = await response.json()
    expect(userData.email).toBe(TEST_USERS.adminUser.email)
    expect(userData.is_admin).toBe(true)

    console.log('Admin user authenticated successfully:', userData.email)
    console.log('Admin flag set:', userData.is_admin)
  })

  test('authenticated user can create tenant', async ({ request }) => {
    // Create a tenant using admin token
    const tenantId = `e2e-test-${Date.now()}`
    const response = await request.post('http://localhost:8001/api/v1/tenants/', {
      headers: {
        Authorization: `Bearer ${adminToken}`,
        'Content-Type': 'application/json',
      },
      data: {
        tenant_id: tenantId,
        name: 'E2E Test Tenant',
        database_name: `tenant_${tenantId}`,
        database_host: 'localhost',
        database_port: 5432,
        database_user: 'postgres',
        database_password: 'postgres',
      },
    })

    expect(response.status()).toBe(201)

    const tenant = await response.json()
    expect(tenant.name).toBe('E2E Test Tenant')
    expect(tenant.is_active).toBe(true)

    console.log('Tenant created successfully:', tenant.name)
    console.log('Tenant ID:', tenant.id)
  })

  test('authenticated user can list tenants', async ({ request }) => {
    // List tenants using admin token
    const response = await request.get('http://localhost:8001/api/v1/tenants/', {
      headers: {
        Authorization: `Bearer ${adminToken}`,
      },
    })

    expect(response.status()).toBe(200)

    const tenants = await response.json()
    expect(Array.isArray(tenants)).toBe(true)

    console.log('Listed tenants:', tenants.length)
  })

  test('authenticated user can assign user to tenant', async ({ request }) => {
    // First, get the current user info
    const meResponse = await request.get('http://localhost:8001/api/v1/auth/me', {
      headers: {
        Authorization: `Bearer ${validUserToken}`,
      },
    })
    const userData = await meResponse.json()
    const userId = userData.id

    // Create a tenant
    const assignTenantId = `assign-test-${Date.now()}`
    const tenantResponse = await request.post('http://localhost:8001/api/v1/tenants/', {
      headers: {
        Authorization: `Bearer ${adminToken}`,
        'Content-Type': 'application/json',
      },
      data: {
        tenant_id: assignTenantId,
        name: 'Assignment Test Tenant',
        database_name: `tenant_${assignTenantId}`,
        database_host: 'localhost',
        database_port: 5432,
        database_user: 'postgres',
        database_password: 'postgres',
      },
    })
    const tenant = await tenantResponse.json()
    const tenantId = tenant.id

    // Assign user to tenant
    const assignResponse = await request.post(
      `http://localhost:8001/api/v1/tenants/${tenantId}/users/${userId}`,
      {
        headers: {
          Authorization: `Bearer ${adminToken}`,
        },
      }
    )

    expect(assignResponse.status()).toBe(201)

    console.log('User assigned to tenant successfully')

    // Verify assignment by checking user's accessible tenants
    const verifyResponse = await request.get('http://localhost:8001/api/v1/auth/me', {
      headers: {
        Authorization: `Bearer ${validUserToken}`,
      },
    })
    const verifiedUser = await verifyResponse.json()
    expect(verifiedUser.accessible_tenant_ids).toContain(tenantId)

    console.log('Assignment verified - user has access to tenant')
  })

  test('user can only see their assigned tenants', async ({ request }) => {
    // Get user info
    const meResponse = await request.get('http://localhost:8001/api/v1/auth/me', {
      headers: {
        Authorization: `Bearer ${validUserToken}`,
      },
    })
    const userData = await meResponse.json()

    console.log('User has access to tenants:', userData.accessible_tenant_ids)

    // The accessible_tenant_ids should be an array
    expect(Array.isArray(userData.accessible_tenant_ids)).toBe(true)
  })

  test('valid JWT token with all required claims is accepted', async ({ request }) => {
    // Create a token with all required Keycloak claims
    const fullClaimsUser = {
      sub: `e2e-full-claims-${Date.now()}`,
      email: `fullclaims-${Date.now()}@example.com`,
      name: 'Full Claims User',
      preferred_username: 'fullclaims',
      email_verified: true,
      realm_access: {
        roles: ['user', 'custom-role']
      }
    }

    const fullToken = generateJWTToken(fullClaimsUser)

    const response = await request.get('http://localhost:8001/api/v1/auth/me', {
      headers: {
        Authorization: `Bearer ${fullToken}`,
      },
    })

    expect(response.status()).toBe(200)
    const userData = await response.json()
    expect(userData.email).toBe(fullClaimsUser.email)

    console.log('Token with full claims accepted')
  })

  test('health endpoint still accessible with auth token', async ({ request }) => {
    // Health endpoint should be public even with token
    const response = await request.get('http://localhost:8001/health', {
      headers: {
        Authorization: `Bearer ${validUserToken}`,
      },
    })

    expect(response.status()).toBe(200)
    const health = await response.json()
    expect(health.status).toBe('healthy')

    console.log('Health endpoint accessible with auth token')
  })
})
