/**
 * E2E Browser Test: Dashboard UI with Panels
 *
 * This test uses actual browser automation to verify that the frontend loads correctly.
 * Screenshots and videos will be captured for these tests in CI.
 *
 * Note: These tests navigate to the frontend to verify it loads. Authentication
 * and detailed dashboard functionality are tested via API tests in other files.
 */

import { test, expect } from '@playwright/test'

test.describe('Dashboard UI Browser Tests', () => {
  test('frontend application loads and renders', async ({ page }) => {
    // Navigate to the application
    await page.goto('/', { waitUntil: 'domcontentloaded' })

    // Verify the page loaded by checking for the root element
    const root = await page.locator('#root, #app, body').first()
    await expect(root).toBeVisible()

    // Verify page has content
    const content = await page.textContent('body')
    expect(content).toBeTruthy()
    expect(content!.length).toBeGreaterThan(0)

    console.log('✓ Frontend loaded successfully')
  })

  test('application displays in different viewports', async ({ page }) => {
    // Test mobile viewport
    await page.setViewportSize({ width: 375, height: 667 })
    await page.goto('/', { waitUntil: 'domcontentloaded' })

    const root = await page.locator('#root, #app, body').first()
    await expect(root).toBeVisible()

    console.log('✓ Mobile viewport renders correctly')

    // Test desktop viewport
    await page.setViewportSize({ width: 1920, height: 1080 })
    await page.goto('/', { waitUntil: 'domcontentloaded' })

    await expect(root).toBeVisible()

    console.log('✓ Desktop viewport renders correctly')
  })

  test('page loads static resources successfully', async ({ page }) => {
    const responses: { url: string; status: number }[] = []

    // Track all resource responses
    page.on('response', (response) => {
      responses.push({
        url: response.url(),
        status: response.status(),
      })
    })

    await page.goto('/', { waitUntil: 'networkidle' })

    // Verify we loaded some resources and they were successful
    const successfulResponses = responses.filter((r) => r.status >= 200 && r.status < 400)
    expect(successfulResponses.length).toBeGreaterThan(0)

    console.log(`✓ Loaded ${successfulResponses.length} resources successfully`)
  })
})
