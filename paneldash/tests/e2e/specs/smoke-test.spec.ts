/**
 * Smoke Tests - Basic sanity checks
 *
 * These tests verify basic functionality and always capture screenshots
 * to ensure artifacts are created even if other tests fail.
 */

import { test, expect } from '@playwright/test'

test.describe('Smoke Tests', () => {
  test('frontend application loads', async ({ page }) => {
    // Navigate to the application
    await page.goto('/', { waitUntil: 'domcontentloaded' })

    // Take screenshot
    await page.screenshot({
      path: 'tests/e2e/test-results/smoke-test-homepage.png',
      fullPage: true
    })

    // Verify page loaded
    const body = page.locator('body')
    await expect(body).toBeVisible()

    console.log('✓ Frontend loaded successfully')
  })

  test('login page is accessible', async ({ page }) => {
    // Navigate to login
    await page.goto('/login', { waitUntil: 'domcontentloaded' })

    // Take screenshot
    await page.screenshot({
      path: 'tests/e2e/test-results/smoke-test-login-page.png',
      fullPage: true
    })

    // Verify login elements
    const title = page.getByRole('heading', { name: /paneldash/i })
    await expect(title).toBeVisible()

    console.log('✓ Login page loaded successfully')
  })

  test('health page is accessible', async ({ page }) => {
    // Navigate to health
    await page.goto('/health', { waitUntil: 'domcontentloaded' })

    // Take screenshot
    await page.screenshot({
      path: 'tests/e2e/test-results/smoke-test-health-page.png',
      fullPage: true
    })

    // Verify health page loaded
    await page.waitForSelector('text=/healthy|status/i', { timeout: 5000 })

    console.log('✓ Health page loaded successfully')
  })
})
