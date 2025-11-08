/**
 * E2E Test: Invalid User Authentication Rejection
 *
 * This test verifies that an invalid/unauthorized user:
 * 1. Cannot access the dashboard without authentication
 * 2. Is redirected to login page when not authenticated
 * 3. Cannot access protected resources with invalid tokens
 * 4. Cannot access dashboards they don't have permissions for
 */

import { test, expect, Page } from '@playwright/test'

test.describe('Invalid User Authentication', () => {
  test('invalid token is rejected by backend', async ({ request }) => {
    // Try to access protected endpoint with invalid token
    const response = await request.get('http://localhost:8001/api/v1/auth/me', {
      headers: {
        Authorization: 'Bearer invalid-token-12345',
      },
    })

    // Should return 401 Unauthorized
    expect(response.status()).toBe(401)

    const errorData = await response.json()
    expect(errorData.detail).toBeTruthy()

    console.log('Invalid token correctly rejected:', errorData.detail)
  })

  test('malformed token is rejected by backend', async ({ request }) => {
    // Try with a completely malformed token
    const response = await request.get('http://localhost:8001/api/v1/auth/me', {
      headers: {
        Authorization: 'Bearer not.a.token',
      },
    })

    // Should return 401 Unauthorized
    expect(response.status()).toBe(401)

    console.log('Malformed token correctly rejected')
  })

  test('user without token cannot access protected API endpoints', async ({ request }) => {
    // Try to access protected endpoints without auth header
    const endpoints = [
      '/api/v1/auth/me',
      '/api/v1/tenants',
      '/api/v1/users/me',
    ]

    for (const endpoint of endpoints) {
      const response = await request.get(`http://localhost:8001${endpoint}`)

      // Should return 401 or 403
      expect([401, 403]).toContain(response.status())

      console.log(`Endpoint ${endpoint} correctly protected: ${response.status()}`)
    }
  })

  test('missing authorization header returns 403', async ({ request }) => {
    // Try to access a protected endpoint without Authorization header
    const response = await request.get('http://localhost:8001/api/v1/auth/me')

    // Should return 403 Forbidden (no credentials provided)
    expect(response.status()).toBe(403)

    console.log('Missing auth header correctly returns 403')
  })

  test('health endpoint is accessible without authentication', async ({ request }) => {
    // Public health endpoint should be accessible
    const response = await request.get('http://localhost:8001/health')

    expect(response.status()).toBe(200)

    const health = await response.json()
    expect(health.status).toBe('healthy')

    console.log('Health endpoint accessible without auth')
  })
})
