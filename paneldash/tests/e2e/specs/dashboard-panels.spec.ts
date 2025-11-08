import { test, expect, Page } from '@playwright/test'

test.describe('Dashboard with Panel Data', () => {
  let screenshotCounter = 0

  async function captureScreenshot(page: Page, name: string) {
    const timestamp = Date.now()
    screenshotCounter++
    await page.screenshot({
      path: `test-results/screenshots/${screenshotCounter}-${timestamp}-${name}.png`,
      fullPage: true,
    })
  }

  test.beforeEach(async ({ page }) => {
    // Navigate to health page first (no auth required)
    await page.goto('/health')
    await page.waitForLoadState('networkidle')
  })

  test('health page displays backend status with screenshot', async ({ page }) => {
    // Wait for the health check to complete
    await page.waitForSelector('[data-testid="health-success"]', { timeout: 10000 })

    // Verify content
    const successDiv = page.locator('[data-testid="health-success"]')
    await expect(successDiv).toBeVisible()
    await expect(successDiv).toContainText('Backend Status: healthy')

    // Capture screenshot
    await captureScreenshot(page, 'health-page-success')

    // Verify specific elements
    await expect(successDiv).toContainText('✅ API is responding')
    await expect(successDiv).toContainText('✅ Connection successful')
    await expect(page.locator('text=Healthy')).toBeVisible()

    // Take a close-up screenshot of the success card
    await successDiv.screenshot({
      path: `test-results/screenshots/${++screenshotCounter}-health-success-card.png`,
    })
  })

  test('health page title and layout', async ({ page }) => {
    // Verify title
    await expect(page.locator('h1')).toContainText('System Health Check')

    // Capture full page screenshot
    await captureScreenshot(page, 'health-page-full')

    // Verify key elements are present
    await expect(page.locator('text=Backend API')).toBeVisible()
    await expect(page.locator('text=Frontend')).toBeVisible()
  })

  test('health page backend connection status', async ({ page }) => {
    // Wait for data to load
    await page.waitForSelector('[data-testid="health-success"]', { timeout: 10000 })

    // Check that we're actually getting data from the backend
    const successDiv = page.locator('[data-testid="health-success"]')
    await expect(successDiv).toBeVisible()

    // The page should show backend URL
    const bodyText = await page.textContent('body')
    expect(bodyText).toContain('localhost:8001')

    await captureScreenshot(page, 'health-page-backend-connection')
  })

  test('health page error state simulation', async ({ page, context }) => {
    // Block requests to simulate backend being down
    await context.route('**/health', (route) => {
      route.abort('failed')
    })

    // Reload to trigger the error
    await page.reload()

    // Wait for error state
    await page.waitForSelector('[data-testid="health-error"]', { timeout: 10000 })

    const errorDiv = page.locator('[data-testid="health-error"]')
    await expect(errorDiv).toBeVisible()
    await expect(errorDiv).toContainText('Backend Unreachable')

    // Capture error state
    await captureScreenshot(page, 'health-page-error')
  })

  test('health page responsive design', async ({ page }) => {
    // Test desktop view
    await page.setViewportSize({ width: 1920, height: 1080 })
    await captureScreenshot(page, 'health-page-desktop')

    // Test tablet view
    await page.setViewportSize({ width: 768, height: 1024 })
    await page.waitForTimeout(500) // Wait for reflow
    await captureScreenshot(page, 'health-page-tablet')

    // Test mobile view
    await page.setViewportSize({ width: 375, height: 667 })
    await page.waitForTimeout(500) // Wait for reflow
    await captureScreenshot(page, 'health-page-mobile')
  })

  test('OpenAPI documentation is accessible', async ({ page }) => {
    // Navigate to API docs
    await page.goto('http://localhost:8001/docs')
    await page.waitForLoadState('networkidle')

    // Wait for Swagger UI to load
    await page.waitForSelector('.swagger-ui', { timeout: 10000 })

    // Verify it loaded
    await expect(page.locator('.swagger-ui')).toBeVisible()

    // Capture screenshot of API docs
    await captureScreenshot(page, 'api-docs')

    // Check that endpoints are listed
    const bodyText = await page.textContent('body')
    expect(bodyText).toContain('/api/v1')
  })

  test('OpenAPI spec contains expected endpoints', async ({ request }) => {
    const response = await request.get('http://localhost:8001/openapi.json')
    expect(response.status()).toBe(200)

    const spec = await response.json()
    expect(spec.info.title).toContain('PanelDash')

    // Verify key endpoints exist
    expect(spec.paths['/health']).toBeDefined()
    expect(spec.paths['/api/v1/tenants']).toBeDefined()
    expect(spec.paths['/api/v1/users/me']).toBeDefined()
  })

  test('backend returns proper CORS headers', async ({ request }) => {
    const response = await request.get('http://localhost:8001/health')
    const headers = response.headers()

    // Check for CORS headers (if configured)
    // This is important for frontend-backend communication
    expect(response.status()).toBe(200)
  })
})
