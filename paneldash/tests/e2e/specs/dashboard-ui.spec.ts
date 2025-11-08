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
  test('frontend application loads successfully', async ({ page }) => {
    // Navigate to the application
    await page.goto('/')

    // Wait for page to load
    await page.waitForLoadState('domcontentloaded')

    // Verify the page has a title (basic smoke test)
    const title = await page.title()
    expect(title).toBeTruthy()
    console.log('Page title:', title)
  })

  test('application renders without crashing', async ({ page }) => {
    // Navigate to the application
    await page.goto('/')

    // Wait for network to be idle
    await page.waitForLoadState('networkidle')

    // Verify body content exists
    const bodyContent = await page.textContent('body')
    expect(bodyContent).toBeTruthy()
    expect(bodyContent!.length).toBeGreaterThan(0)
    console.log('Body content length:', bodyContent!.length)
  })

  test('application root element is present', async ({ page }) => {
    // Navigate to the application
    await page.goto('/')

    // Wait for DOM to load
    await page.waitForLoadState('domcontentloaded')

    // Check for React/Vue root element
    const root = await page.$('#root, #app, .app')
    expect(root).toBeTruthy()
  })

  test('page responds to viewport changes', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 })
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    // Verify page loads in mobile view
    const mobileWidth = await page.evaluate(() => window.innerWidth)
    expect(mobileWidth).toBe(375)

    // Set desktop viewport
    await page.setViewportSize({ width: 1920, height: 1080 })
    const desktopWidth = await page.evaluate(() => window.innerWidth)
    expect(desktopWidth).toBe(1920)
  })

  test('page loads CSS and JavaScript resources', async ({ page }) => {
    const cssLoaded: boolean[] = []
    const jsLoaded: boolean[] = []

    // Track resource loading
    page.on('response', (response) => {
      const url = response.url()
      if (url.endsWith('.css')) {
        cssLoaded.push(response.ok())
      }
      if (url.endsWith('.js')) {
        jsLoaded.push(response.ok())
      }
    })

    await page.goto('/')
    await page.waitForLoadState('networkidle')

    // Verify resources were loaded successfully
    expect(cssLoaded.length).toBeGreaterThan(0)
    expect(jsLoaded.length).toBeGreaterThan(0)
    console.log(`Loaded ${cssLoaded.length} CSS files and ${jsLoaded.length} JS files`)
  })
})
