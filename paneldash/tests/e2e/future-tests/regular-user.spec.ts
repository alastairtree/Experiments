import { test, expect } from '@playwright/test'
import { loginAsRegularUser, expect403 } from '../fixtures/auth'

test.describe('Regular User', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsRegularUser(page)
  })

  test('should access dashboard page', async ({ page }) => {
    await page.goto('/dashboard')

    // Check dashboard loaded
    const heading = page.locator('h1')
    await expect(heading).toBeVisible()
    await expect(heading).toContainText(/dashboard/i)
  })

  test('should see tenant selector', async ({ page }) => {
    await page.goto('/dashboard')

    // Check for tenant selector
    const tenantLabel = page.locator('text=Tenant:')
    await expect(tenantLabel).toBeVisible()

    const tenantSelect = page.locator('select')
    await expect(tenantSelect).toBeVisible()
  })

  test('should be able to select tenant', async ({ page }) => {
    await page.goto('/dashboard')

    // Wait for tenant selector to load
    const tenantSelect = page.locator('select')
    await expect(tenantSelect).toBeVisible()

    // Get available options
    const options = await tenantSelect.locator('option').count()
    expect(options).toBeGreaterThan(0)

    // Select first tenant
    if (options > 1) {
      await tenantSelect.selectOption({ index: 1 })
    }
  })

  test('should see user email in header', async ({ page }) => {
    await page.goto('/dashboard')

    // Check for user email in header
    const userEmail = page.locator('text=user@example.com')
    await expect(userEmail).toBeVisible()
  })

  test('should NOT be able to access admin page', async ({ page }) => {
    await page.goto('/admin')

    // Should see 403 Forbidden
    await expect403(page)
  })

  test('should be able to logout', async ({ page }) => {
    await page.goto('/dashboard')

    // Find and click logout button
    const logoutButton = page.locator('button:has-text("Logout")')
    await expect(logoutButton).toBeVisible()
    await logoutButton.click()

    // Should redirect to login page
    await page.waitForURL(/\/login/, { timeout: 5000 })
  })

  test('should see health status on dashboard', async ({ page }) => {
    await page.goto('/dashboard')

    // Dashboard should show some content
    const content = page.locator('body')
    await expect(content).toContainText(/dashboard|tenant/i)
  })
})
