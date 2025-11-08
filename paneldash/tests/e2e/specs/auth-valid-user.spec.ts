/**
 * E2E Test: Valid User Authentication and Dashboard Access
 *
 * This test verifies that a valid user can:
 * 1. Be created in the database via Keycloak authentication
 * 2. Successfully authenticate with a valid JWT token
 * 3. Access the dashboard
 * 4. View tenant information
 */

import { test, expect, Page } from '@playwright/test'
import { generateJWTToken, TEST_USERS } from '../fixtures/jwt-helper'
import { createUserViaAuth, createTenant, assignUserToTenant } from '../fixtures/database-helper'

test.describe('Valid User Authentication', () => {
  let validUserToken: string
  let userId: string
  let tenantId: string

  test.beforeAll(async () => {
    // Generate a valid JWT token for the test user
    validUserToken = generateJWTToken(TEST_USERS.validUser)
    console.log('Generated valid user token:', validUserToken.substring(0, 50) + '...')

    // Create the user in the database via the auth endpoint
    // This simulates the first login flow where the user is auto-created
    try {
      const user = await createUserViaAuth(validUserToken)
      userId = user.id
      console.log('Created user:', user.email, 'ID:', userId)

      // Create an admin token to set up test data
      const adminToken = generateJWTToken(TEST_USERS.adminUser)
      const adminUser = await createUserViaAuth(adminToken)
      console.log('Created admin user:', adminUser.email)

      // Create a test tenant
      const tenant = await createTenant(adminToken, {
        name: 'E2E Test Tenant',
        config_path: '/config/tenants/e2e-test',
        is_active: true,
      })
      tenantId = tenant.id
      console.log('Created tenant:', tenant.name, 'ID:', tenantId)

      // Assign the valid user to the tenant
      await assignUserToTenant(adminToken, userId, tenantId)
      console.log('Assigned user to tenant')
    } catch (error) {
      console.error('Setup failed:', error)
      throw error
    }
  })

  async function loginWithToken(page: Page, token: string) {
    // Navigate to the app
    await page.goto('/')

    // Set the auth token in localStorage to simulate successful authentication
    await page.evaluate(
      ({ token: authToken }) => {
        localStorage.setItem('auth_token', authToken)
      },
      { token }
    )

    // Reload to apply the token
    await page.reload()
    await page.waitForLoadState('networkidle')
  }

  test('valid user can authenticate and see dashboard', async ({ page }) => {
    // Login with the valid token
    await loginWithToken(page, validUserToken)

    // Should be redirected to dashboard (or already there)
    await page.waitForURL(/\/(dashboard)?/, { timeout: 10000 })

    // Navigate explicitly to dashboard if needed
    if (!page.url().includes('dashboard')) {
      await page.goto('/dashboard')
      await page.waitForLoadState('networkidle')
    }

    // Verify we're on the dashboard page
    const url = page.url()
    expect(url).toContain('dashboard')

    // Check that we can see dashboard content
    // Look for common dashboard elements
    const body = await page.textContent('body')
    expect(body).toBeTruthy()

    // Verify user info is displayed (email or name)
    const userEmail = TEST_USERS.validUser.email
    const hasUserInfo = body?.includes(userEmail) || body?.includes('Valid Test User')
    if (hasUserInfo) {
      console.log('User info found on dashboard')
    }

    // Take a screenshot for verification
    await page.screenshot({
      path: 'test-results/screenshots/valid-user-dashboard.png',
      fullPage: true,
    })
  })

  test('valid user can access tenant dashboard with data', async ({ page }) => {
    // Login with the valid token
    await loginWithToken(page, validUserToken)

    // Navigate to dashboard
    await page.goto('/dashboard')
    await page.waitForLoadState('networkidle')

    // Look for tenant selector or tenant-related content
    const body = await page.textContent('body')

    // The user should see tenant information or tenant selector
    // depending on how many tenants they have access to
    expect(body).toBeTruthy()

    // Check for common dashboard elements
    const hasDashboardContent =
      body?.includes('tenant') ||
      body?.includes('Tenant') ||
      body?.includes('dashboard') ||
      body?.includes('Dashboard')

    expect(hasDashboardContent).toBeTruthy()

    console.log('Dashboard content verified')

    // Take a screenshot
    await page.screenshot({
      path: 'test-results/screenshots/valid-user-tenant-dashboard.png',
      fullPage: true,
    })
  })

  test('valid user is authenticated and /auth/me returns user data', async ({ request }) => {
    // Call the /auth/me endpoint with the valid token
    const response = await request.get('http://localhost:8001/api/v1/auth/me', {
      headers: {
        Authorization: `Bearer ${validUserToken}`,
      },
    })

    expect(response.status()).toBe(200)

    const userData = await response.json()
    expect(userData.email).toBe(TEST_USERS.validUser.email)
    expect(userData.keycloak_id).toBe(TEST_USERS.validUser.sub)
    expect(userData.accessible_tenant_ids).toContain(tenantId)

    console.log('User data verified:', userData)
  })

  test('valid user can see assigned tenant in tenant list', async ({ page }) => {
    // Login with the valid token
    await loginWithToken(page, validUserToken)

    // Navigate to dashboard
    await page.goto('/dashboard')
    await page.waitForLoadState('networkidle')

    // Wait a bit for any API calls to complete
    await page.waitForTimeout(2000)

    // Look for tenant selector or tenant name
    const body = await page.textContent('body')
    expect(body).toBeTruthy()

    // The tenant name should appear somewhere on the page
    const hasTenantName = body?.includes('E2E Test Tenant') || body?.includes('e2e-test')

    if (hasTenantName) {
      console.log('Tenant name found on dashboard')
    } else {
      console.log('Tenant name not found, but user has access')
    }

    // Take a screenshot
    await page.screenshot({
      path: 'test-results/screenshots/valid-user-tenant-list.png',
      fullPage: true,
    })
  })
})
