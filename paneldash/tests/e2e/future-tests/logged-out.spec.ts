import { test, expect } from '@playwright/test'
import { logout, expectLoginPage } from '../fixtures/auth'

test.describe('Logged Out User', () => {
  test.beforeEach(async ({ page }) => {
    await logout(page)
  })

  test('should redirect to /login when accessing root', async ({ page }) => {
    await page.goto('/')
    await expectLoginPage(page)
  })

  test('should redirect to /login when accessing /dashboard', async ({ page }) => {
    await page.goto('/dashboard')
    await expectLoginPage(page)
  })

  test('should redirect to /login when accessing /admin', async ({ page }) => {
    await page.goto('/admin')
    await expectLoginPage(page)
  })

  test('should show login page with Keycloak login button', async ({ page }) => {
    await page.goto('/login')

    // Check for login page elements
    const heading = page.locator('h1')
    await expect(heading).toBeVisible()
    await expect(heading).toContainText(/login|sign in/i)

    // Check for login button
    const loginButton = page.locator('button:has-text("Login")')
    await expect(loginButton).toBeVisible()
  })

  test('should show health check endpoint is accessible', async ({ page }) => {
    await page.goto('/health')

    // Health page should be accessible without authentication
    const healthStatus = page.locator('text=healthy')
    await expect(healthStatus).toBeVisible({ timeout: 10000 })
  })
})
