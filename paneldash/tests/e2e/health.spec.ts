import { test, expect } from '@playwright/test'

test.describe('Health Check', () => {
  test('backend health endpoint returns healthy', async ({ request }) => {
    const response = await request.get('http://localhost:8000/health')

    expect(response.ok()).toBeTruthy()
    expect(response.status()).toBe(200)

    const data = await response.json()
    expect(data).toEqual({ status: 'healthy' })
  })

  test('frontend health page displays backend status', async ({ page }) => {
    await page.goto('/health')

    // Wait for the page to load and query to complete
    await page.waitForSelector('[data-testid="health-success"]', { timeout: 10000 })

    // Check that success message is displayed
    const successDiv = page.locator('[data-testid="health-success"]')
    await expect(successDiv).toBeVisible()

    // Verify the status text
    await expect(successDiv).toContainText('Backend Status: healthy')

    // Verify the checkmarks are present
    await expect(successDiv).toContainText('✅ API is responding')
    await expect(successDiv).toContainText('✅ Connection successful')

    // Verify the health status in the summary section
    await expect(page.locator('text=Healthy')).toBeVisible()
  })

  test('frontend health page shows error when backend is unreachable', async ({ page, context }) => {
    // Block requests to the backend to simulate it being down
    await context.route('http://localhost:8000/health', route => {
      route.abort('failed')
    })

    await page.goto('/health')

    // Wait for the error to appear
    await page.waitForSelector('[data-testid="health-error"]', { timeout: 10000 })

    // Check that error message is displayed
    const errorDiv = page.locator('[data-testid="health-error"]')
    await expect(errorDiv).toBeVisible()
    await expect(errorDiv).toContainText('Backend Unreachable')
  })

  test('frontend health page title is correct', async ({ page }) => {
    await page.goto('/health')

    await expect(page.locator('h1')).toContainText('System Health Check')
  })
})
