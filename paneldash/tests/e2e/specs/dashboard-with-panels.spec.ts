/**
 * E2E tests for viewing dashboards with panels
 *
 * These tests verify that a logged-in user can view their dashboard
 * with panels containing charts and visualizations.
 */

import { test, expect, request } from '@playwright/test'
import { mkdirSync, writeFileSync, rmSync, existsSync } from 'fs'
import { join } from 'path'
import { generateJWTToken, TEST_USERS } from '../fixtures/jwt-helper'
import { assignUserToTenant } from '../fixtures/database-helper'

const API_URL = process.env.VITE_API_URL || 'http://localhost:8001'

// Use a fixed tenant ID that we'll reuse for all tests
const TEST_TENANT_ID = 'e2e-test-tenant'
const TEST_TENANT_CONFIG_PATH = join(process.cwd(), 'tenants', TEST_TENANT_ID)

test.describe('Dashboard with Panel Data', () => {
  let adminToken: string
  let validUserToken: string
  let userId: string
  let tenantId: string

  test.beforeAll(async () => {
    // Generate tokens
    adminToken = generateJWTToken(TEST_USERS.adminUser)
    validUserToken = generateJWTToken(TEST_USERS.validUser)

    // Create test user
    const apiContext = await request.newContext()
    const userResponse = await apiContext.get(`${API_URL}/api/v1/auth/me`, {
      headers: { Authorization: `Bearer ${validUserToken}` },
    })
    const user = await userResponse.json()
    userId = user.id

    // Create tenant configuration directory structure
    mkdirSync(join(TEST_TENANT_CONFIG_PATH, 'dashboards'), { recursive: true })
    mkdirSync(join(TEST_TENANT_CONFIG_PATH, 'panels'), { recursive: true })

    // Create panel configuration (CPU usage time series)
    const panelConfig = `panel:
  type: "timeseries"
  title: "CPU Usage Over Time"
  description: "Server CPU utilization percentage"

  data_source:
    table: "metrics"
    columns:
      timestamp: "recorded_at"
      value: "cpu_percent"
      series_label: "server_name"

    query:
      where: "metric_type = 'cpu'"
      order_by: "recorded_at DESC"

  display:
    y_axis_label: "CPU %"
    y_axis_range: [0, 100]
    line_color: "#3B82F6"
    fill_area: true

  refresh_interval: 300

  drill_down:
    enabled: true
    show_table: true
    disable_aggregation: true
`

    writeFileSync(join(TEST_TENANT_CONFIG_PATH, 'panels', 'cpu_usage.yaml'), panelConfig)

    // Create dashboard configuration
    const dashboardConfig = `dashboard:
  name: "E2E Test Dashboard"
  description: "Dashboard for E2E testing"
  refresh_interval: 21600

  layout:
    columns: 12

  panels:
    - id: "cpu_usage"
      config_file: "panels/cpu_usage.yaml"
      position:
        row: 1
        col: 1
        width: 8
        height: 2
`

    writeFileSync(join(TEST_TENANT_CONFIG_PATH, 'dashboards', 'default.yaml'), dashboardConfig)

    // Create tenant in database (only if it doesn't exist)
    const existingTenantsResponse = await apiContext.get(`${API_URL}/api/v1/tenants/`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    })
    const existingTenants = await existingTenantsResponse.json()
    const existingTenant = existingTenants.find((t: any) => t.tenant_id === TEST_TENANT_ID)

    if (existingTenant) {
      tenantId = existingTenant.id
      console.log(`Using existing test tenant: ${TEST_TENANT_ID} (ID: ${tenantId})`)
    } else {
      const tenantResponse = await apiContext.post(`${API_URL}/api/v1/tenants/`, {
        headers: {
          Authorization: `Bearer ${adminToken}`,
          'Content-Type': 'application/json',
        },
        data: {
          tenant_id: TEST_TENANT_ID,
          name: 'E2E Test Tenant',
          database_name: `tenant_${TEST_TENANT_ID.replace(/-/g, '_')}`,
          database_host: 'localhost',
          database_port: 5432,
          database_user: 'postgres',
          database_password: 'postgres',
        },
      })

      expect(tenantResponse.status()).toBe(201)
      const tenant = await tenantResponse.json()
      tenantId = tenant.id
      console.log(`Created new test tenant: ${TEST_TENANT_ID} (ID: ${tenantId})`)
    }

    // Assign user to tenant
    try {
      await assignUserToTenant(adminToken, userId, tenantId)
      console.log(`Assigned user ${userId} to tenant ${tenantId}`)
    } catch (error: any) {
      // Ignore if user is already assigned
      if (!error.message.includes('already assigned')) {
        throw error
      }
      console.log(`User ${userId} already assigned to tenant ${tenantId}`)
    }

    await apiContext.dispose()
  })

  test.afterAll(async () => {
    // Clean up tenant configuration directory
    try {
      if (existsSync(TEST_TENANT_CONFIG_PATH)) {
        rmSync(TEST_TENANT_CONFIG_PATH, { recursive: true, force: true })
        console.log(`Cleaned up test tenant config: ${TEST_TENANT_CONFIG_PATH}`)
      }
    } catch (error) {
      console.error(`Failed to clean up test tenant config:`, error)
    }
  })

  test('user can list their accessible tenants including the test tenant', async ({
    request,
  }) => {
    const response = await request.get(`${API_URL}/api/v1/tenants/`, {
      headers: {
        Authorization: `Bearer ${validUserToken}`,
      },
    })

    expect(response.status()).toBe(200)
    const tenants = await response.json()

    console.log(`User has access to ${tenants.length} tenant(s)`)

    // Verify test tenant is in the list
    const testTenant = tenants.find((t: any) => t.tenant_id === TEST_TENANT_ID)
    expect(testTenant).toBeDefined()
    expect(testTenant.name).toBe('E2E Test Tenant')
    expect(testTenant.is_active).toBe(true)

    console.log(`Test tenant found in user's accessible tenants: ${testTenant.tenant_id}`)
  })

  test('user can get panel data for CPU usage', async ({ request }) => {
    const response = await request.get(
      `${API_URL}/api/v1/panels/cpu_usage/data?tenant_id=${TEST_TENANT_ID}`,
      {
        headers: {
          Authorization: `Bearer ${validUserToken}`,
        },
      }
    )

    expect(response.status()).toBe(200)
    const panelData = await response.json()

    console.log('Panel data response:', JSON.stringify(panelData, null, 2))

    // Verify panel data structure
    expect(panelData.panel_id).toBe('cpu_usage')
    expect(panelData.panel_type).toBe('timeseries')
    expect(panelData.data).toBeDefined()

    // Verify time series data structure (even if mock data)
    expect(panelData.data.series).toBeDefined()
    expect(Array.isArray(panelData.data.series)).toBe(true)

    if (panelData.data.series.length > 0) {
      const firstSeries = panelData.data.series[0]
      expect(firstSeries.timestamps).toBeDefined()
      expect(firstSeries.values).toBeDefined()
      expect(Array.isArray(firstSeries.timestamps)).toBe(true)
      expect(Array.isArray(firstSeries.values)).toBe(true)
      console.log(
        `Panel has ${panelData.data.series.length} series with ${firstSeries.timestamps.length} data points`
      )
    }
  })

  test('panel data includes aggregation info when date range is provided', async ({
    request,
  }) => {
    const dateFrom = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString() // 7 days ago
    const dateTo = new Date().toISOString()

    const response = await request.get(
      `${API_URL}/api/v1/panels/cpu_usage/data?tenant_id=${TEST_TENANT_ID}&date_from=${encodeURIComponent(
        dateFrom
      )}&date_to=${encodeURIComponent(dateTo)}`,
      {
        headers: {
          Authorization: `Bearer ${validUserToken}`,
        },
      }
    )

    expect(response.status()).toBe(200)
    const panelData = await response.json()

    // Verify aggregation info is present
    expect(panelData.aggregation_info).toBeDefined()
    console.log('Aggregation info:', panelData.aggregation_info)

    if (panelData.aggregation_info.applied) {
      expect(panelData.aggregation_info.bucket_interval).toBeDefined()
      console.log(
        `Aggregation applied with bucket interval: ${panelData.aggregation_info.bucket_interval}`
      )
    } else {
      expect(panelData.aggregation_info.reason).toBeDefined()
      console.log(`Aggregation not applied: ${panelData.aggregation_info.reason}`)
    }
  })

  test('panel data respects disable_aggregation flag', async ({ request }) => {
    const dateFrom = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString()
    const dateTo = new Date().toISOString()

    const response = await request.get(
      `${API_URL}/api/v1/panels/cpu_usage/data?tenant_id=${TEST_TENANT_ID}&date_from=${encodeURIComponent(
        dateFrom
      )}&date_to=${encodeURIComponent(dateTo)}&disable_aggregation=true`,
      {
        headers: {
          Authorization: `Bearer ${validUserToken}`,
        },
      }
    )

    expect(response.status()).toBe(200)
    const panelData = await response.json()

    // Verify aggregation is disabled
    expect(panelData.aggregation_info).toBeDefined()
    expect(panelData.aggregation_info.applied).toBe(false)
    expect(panelData.aggregation_info.reason).toContain('disable_aggregation')

    console.log('Aggregation correctly disabled via flag')
  })

  test('user without access to tenant cannot get panel data', async ({ request: req }) => {
    // Create a new user who is not assigned to the tenant
    const unauthorizedUserToken = generateJWTToken({
      sub: 'unauthorized-user-id',
      email: 'unauthorized@example.com',
      name: 'Unauthorized User',
      preferred_username: 'unauthorized',
      realm_access: {
        roles: [],
      },
    })

    // Auto-create the unauthorized user
    await req.get(`${API_URL}/api/v1/auth/me`, {
      headers: { Authorization: `Bearer ${unauthorizedUserToken}` },
    })

    // Try to access panel data
    const response = await req.get(
      `${API_URL}/api/v1/panels/cpu_usage/data?tenant_id=${TEST_TENANT_ID}`,
      {
        headers: {
          Authorization: `Bearer ${unauthorizedUserToken}`,
        },
      }
    )

    // Should be forbidden
    expect(response.status()).toBe(403)
    const error = await response.json()
    expect(error.detail).toContain('does not have access')

    console.log('Unauthorized user correctly denied access to panel data')
  })

  test('non-existent panel returns 404', async ({ request }) => {
    const response = await request.get(
      `${API_URL}/api/v1/panels/non_existent_panel/data?tenant_id=${TEST_TENANT_ID}`,
      {
        headers: {
          Authorization: `Bearer ${validUserToken}`,
        },
      }
    )

    expect(response.status()).toBe(404)
    const error = await response.json()
    expect(error.detail).toContain('not found')

    console.log('Non-existent panel correctly returns 404')
  })

  test('panel data requires authentication', async ({ request }) => {
    const response = await request.get(
      `${API_URL}/api/v1/panels/cpu_usage/data?tenant_id=${TEST_TENANT_ID}`
    )

    // Should be forbidden without auth
    expect(response.status()).toBe(403)

    console.log('Panel data correctly requires authentication')
  })
})
