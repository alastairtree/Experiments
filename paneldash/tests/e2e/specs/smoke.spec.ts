import { test, expect } from '@playwright/test'

test.describe('E2E Smoke Tests - Service Health', () => {
  test('backend health endpoint returns healthy', async ({ request }) => {
    const response = await request.get('http://localhost:8001/health')
    expect(response.ok()).toBeTruthy()
    const data = await response.json()
    expect(data.status).toBe('healthy')
  })

  test('backend API is accessible', async ({ request }) => {
    const response = await request.get('http://localhost:8001/health')
    expect(response.status()).toBe(200)
  })

  test('backend API returns JSON', async ({ request }) => {
    const response = await request.get('http://localhost:8001/health')
    const contentType = response.headers()['content-type']
    expect(contentType).toContain('application/json')
  })

  test('frontend server is running', async ({ request }) => {
    const response = await request.get('http://localhost:5174')
    expect(response.status()).toBeLessThan(400)
  })

  test('frontend serves HTML', async ({ request }) => {
    const response = await request.get('http://localhost:5174')
    const contentType = response.headers()['content-type']
    expect(contentType).toContain('text/html')
  })

  test('backend API v1 prefix is accessible', async ({ request }) => {
    // This will return 401 but confirms the endpoint exists
    const response = await request.get('http://localhost:8001/api/v1/tenants')
    // Should return 401 Unauthorized (not 404)
    expect([401, 403]).toContain(response.status())
  })

  test('backend serves OpenAPI docs', async ({ request }) => {
    const response = await request.get('http://localhost:8001/docs')
    expect(response.status()).toBe(200)
  })

  test('backend OpenAPI spec is accessible', async ({ request }) => {
    const response = await request.get('http://localhost:8001/openapi.json')
    expect(response.status()).toBe(200)
    const spec = await response.json()
    expect(spec.info).toBeDefined()
    expect(spec.info.title).toContain('PanelDash')
  })
})
