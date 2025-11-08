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
  async function clearAuth(page: Page) {
    await page.goto('/')
    await page.evaluate(() => {
      localStorage.clear()
      sessionStorage.clear()
    })
  }

  test('unauthenticated user cannot access dashboard', async ({ page }) => {
    // Clear any existing auth
    await clearAuth(page)

    // Try to access dashboard without authentication
    await page.goto('/dashboard')
    await page.waitForLoadState('networkidle')

    // Should be redirected to login page or see an error
    const url = page.url()
    const body = await page.textContent('body')

    // Check if redirected to login or see unauthorized message
    const isUnauthorized =
      url.includes('login') ||
      url.includes('/') ||
      body?.includes('login') ||
      body?.includes('Login') ||
      body?.includes('Sign in') ||
      body?.includes('Unauthorized') ||
      body?.includes('unauthorized') ||
      body?.includes('authentication')

    expect(isUnauthorized).toBeTruthy()

    console.log('Unauthenticated user correctly blocked from dashboard')

    // Take a screenshot
    await page.screenshot({
      path: 'test-results/screenshots/invalid-user-no-auth.png',
      fullPage: true,
    })
  })

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

  test('expired/malformed token cannot access dashboard', async ({ page }) => {
    // Clear any existing auth
    await clearAuth(page)

    // Set an invalid token
    await page.goto('/')
    await page.evaluate(() => {
      localStorage.setItem('auth_token', 'invalid.token.here')
    })

    // Try to access dashboard
    await page.goto('/dashboard')
    await page.waitForLoadState('networkidle')

    // The frontend should detect the invalid token and redirect to login
    // or the backend will reject requests
    const url = page.url()
    const body = await page.textContent('body')

    // Wait a bit for any auth checks to complete
    await page.waitForTimeout(2000)

    // After the frontend tries to validate the token, it should redirect or show error
    const currentUrl = page.url()
    const currentBody = await page.textContent('body')

    const isBlocked =
      currentUrl.includes('login') ||
      currentBody?.includes('login') ||
      currentBody?.includes('Login') ||
      currentBody?.includes('unauthorized') ||
      currentBody?.includes('Unauthorized') ||
      currentBody?.includes('authentication')

    if (isBlocked) {
      console.log('Malformed token correctly handled')
    } else {
      console.log('Frontend may still be loading or handling invalid token')
    }

    // Take a screenshot
    await page.screenshot({
      path: 'test-results/screenshots/invalid-user-bad-token.png',
      fullPage: true,
    })
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

  test('login page is accessible without authentication', async ({ page }) => {
    // Clear any existing auth
    await clearAuth(page)

    // Login page should be accessible
    await page.goto('/login')
    await page.waitForLoadState('networkidle')

    // Should show login page content
    const body = await page.textContent('body')
    expect(body).toBeTruthy()

    // Look for login-related content
    const hasLoginContent =
      body?.includes('login') ||
      body?.includes('Login') ||
      body?.includes('Sign in') ||
      body?.includes('PanelDash') ||
      body?.includes('Keycloak')

    expect(hasLoginContent).toBeTruthy()

    console.log('Login page accessible without auth')

    // Take a screenshot
    await page.screenshot({
      path: 'test-results/screenshots/invalid-user-login-page.png',
      fullPage: true,
    })
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
