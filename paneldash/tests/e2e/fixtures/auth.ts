import { Page } from '@playwright/test'

// Mock JWT tokens for different user types
const MOCK_TOKENS = {
  regular: 'mock-regular-user-token',
  admin: 'mock-admin-user-token',
}

// Mock user data that matches token claims
const MOCK_USERS = {
  regular: {
    id: 'e2e-user-1',
    email: 'user@example.com',
    full_name: 'Regular User',
    keycloak_id: 'kc-user-1',
    is_admin: false,
    accessible_tenant_ids: ['tenant-1'],
  },
  admin: {
    id: 'e2e-admin-1',
    email: 'admin@example.com',
    full_name: 'Admin User',
    keycloak_id: 'kc-admin-1',
    is_admin: true,
    accessible_tenant_ids: ['tenant-1', 'tenant-2'],
  },
}

/**
 * Set up a logged-in regular user session
 */
export async function loginAsRegularUser(page: Page): Promise<void> {
  await page.goto('/')

  // Set mock authentication token in localStorage
  await page.evaluate(
    ({ token, user }) => {
      localStorage.setItem('auth_token', token)
      localStorage.setItem('user', JSON.stringify(user))
    },
    { token: MOCK_TOKENS.regular, user: MOCK_USERS.regular }
  )

  // Navigate to dashboard to trigger auth
  await page.goto('/dashboard')
}

/**
 * Set up a logged-in admin user session
 */
export async function loginAsAdmin(page: Page): Promise<void> {
  await page.goto('/')

  // Set mock authentication token in localStorage
  await page.evaluate(
    ({ token, user }) => {
      localStorage.setItem('auth_token', token)
      localStorage.setItem('user', JSON.stringify(user))
    },
    { token: MOCK_TOKENS.admin, user: MOCK_USERS.admin }
  )

  // Navigate to dashboard to trigger auth
  await page.goto('/dashboard')
}

/**
 * Clear authentication (simulate logged out user)
 */
export async function logout(page: Page): Promise<void> {
  await page.goto('/')

  await page.evaluate(() => {
    localStorage.removeItem('auth_token')
    localStorage.removeItem('user')
    localStorage.clear()
  })

  await page.goto('/')
}

/**
 * Check if user is on login page
 */
export async function expectLoginPage(page: Page): Promise<void> {
  await page.waitForURL(/\/login/, { timeout: 5000 })
}

/**
 * Check if user is on dashboard
 */
export async function expectDashboard(page: Page): Promise<void> {
  await page.waitForURL(/\/dashboard/, { timeout: 5000 })
}

/**
 * Check if user sees 403 forbidden
 */
export async function expect403(page: Page): Promise<void> {
  const heading = page.locator('h1')
  await heading.waitFor({ state: 'visible', timeout: 5000 })
  const text = await heading.textContent()
  if (!text?.includes('403') && !text?.includes('Forbidden')) {
    throw new Error(`Expected 403 page, but got: ${text}`)
  }
}
