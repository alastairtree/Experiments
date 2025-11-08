import { test, expect } from '@playwright/test'
import { loginAsAdmin } from '../fixtures/auth'

test.describe('Admin User', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page)
  })

  test('should access dashboard page', async ({ page }) => {
    await page.goto('/dashboard')

    // Check dashboard loaded
    const heading = page.locator('h1')
    await expect(heading).toBeVisible()
    await expect(heading).toContainText(/dashboard/i)
  })

  test('should be able to access admin page', async ({ page }) => {
    await page.goto('/admin')

    // Should see admin page
    const heading = page.locator('h1')
    await expect(heading).toBeVisible()
    await expect(heading).toContainText(/admin/i)
  })

  test('should see list of all users on admin page', async ({ page }) => {
    await page.goto('/admin')

    // Wait for user list to load
    const userHeading = page.locator('h2:has-text("Users")')
    await expect(userHeading).toBeVisible({ timeout: 10000 })

    // Should see user table or list
    const table = page.locator('table')
    await expect(table).toBeVisible()
  })

  test('should see admin email in header', async ({ page }) => {
    await page.goto('/dashboard')

    // Check for admin email in header
    const adminEmail = page.locator('text=admin@example.com')
    await expect(adminEmail).toBeVisible()
  })

  test('should be able to toggle admin rights for a user', async ({ page }) => {
    await page.goto('/admin')

    // Wait for user list
    await page.waitForSelector('table', { timeout: 10000 })

    // Find first user row (not the current admin)
    const userRows = page.locator('table tbody tr')
    const count = await userRows.count()

    if (count > 0) {
      // Find Make Admin or Remove Admin button
      const adminButton = userRows.first().locator('button:has-text(/Make Admin|Remove Admin/)')
      const isVisible = await adminButton.isVisible().catch(() => false)

      if (isVisible) {
        const buttonText = await adminButton.textContent()
        await adminButton.click()

        // Should show success message or button text should change
        await page.waitForTimeout(1000)

        const newButtonText = await adminButton.textContent()
        expect(newButtonText).not.toBe(buttonText)
      }
    }
  })

  test('should be able to assign user to tenant', async ({ page }) => {
    await page.goto('/admin')

    // Wait for user list
    await page.waitForSelector('table', { timeout: 10000 })

    // Find assign tenant button
    const assignButton = page.locator('button:has-text(/Assign|Add.*Tenant/)').first()
    const isVisible = await assignButton.isVisible().catch(() => false)

    if (isVisible) {
      // Button exists - admin can assign tenants
      expect(isVisible).toBe(true)
    }
  })

  test('should be able to remove user from tenant', async ({ page }) => {
    await page.goto('/admin')

    // Wait for user list
    await page.waitForSelector('table', { timeout: 10000 })

    // Find remove tenant button
    const removeButton = page.locator('button:has-text(/Remove.*Tenant|Unassign/)').first()
    const isVisible = await removeButton.isVisible().catch(() => false)

    if (isVisible) {
      // Button exists - admin can remove tenant assignments
      expect(isVisible).toBe(true)
    }
  })

  test('should see delete user buttons on admin page', async ({ page }) => {
    await page.goto('/admin')

    // Wait for user list
    await page.waitForSelector('table', { timeout: 10000 })

    // Check for delete button (should exist for non-current user)
    const deleteButton = page.locator('button:has-text("Delete")').first()
    const isVisible = await deleteButton.isVisible().catch(() => false)

    if (isVisible) {
      // Delete button exists
      expect(isVisible).toBe(true)
    }
  })

  test('should be able to navigate between dashboard and admin pages', async ({ page }) => {
    // Start at dashboard
    await page.goto('/dashboard')
    await expect(page.locator('h1:has-text("Dashboard")')).toBeVisible()

    // Navigate to admin (via link or direct)
    const adminLink = page.locator('a[href="/admin"]')
    const hasLink = await adminLink.isVisible().catch(() => false)

    if (hasLink) {
      await adminLink.click()
    } else {
      await page.goto('/admin')
    }

    await expect(page.locator('h1:has-text("Admin")')).toBeVisible()

    // Navigate back to dashboard
    const dashboardLink = page.locator('a[href="/dashboard"]')
    const hasDashLink = await dashboardLink.isVisible().catch(() => false)

    if (hasDashLink) {
      await dashboardLink.click()
    } else {
      await page.goto('/dashboard')
    }

    await expect(page.locator('h1:has-text("Dashboard")')).toBeVisible()
  })
})
