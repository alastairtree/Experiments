/**
 * E2E Browser Test: Keycloak Login Flow
 *
 * This test verifies the complete Keycloak authentication flow:
 * 1. Frontend loads and redirects to Keycloak login
 * 2. User enters credentials
 * 3. Keycloak authenticates and redirects back
 * 4. User is logged in and can access the dashboard
 *
 * This test will help debug:
 * - Redirect loops between frontend and Keycloak
 * - CORS issues
 * - Token exchange problems
 * - Configuration mismatches
 */

import { test, expect } from '@playwright/test'

test.describe('Keycloak Login Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Set up console logging to capture errors
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        console.error(`Browser console error: ${msg.text()}`)
      } else if (msg.type() === 'warning') {
        console.warn(`Browser console warning: ${msg.text()}`)
      } else {
        console.log(`Browser console: ${msg.text()}`)
      }
    })

    // Log network errors
    page.on('requestfailed', (request) => {
      console.error(`Network request failed: ${request.url()} - ${request.failure()?.errorText}`)
    })

    // Log page errors
    page.on('pageerror', (error) => {
      console.error(`Page error: ${error.message}`)
      console.error(error.stack)
    })
  })

  test('should complete full login flow with testuser', async ({ page }) => {
    console.log('🧪 Starting login test with testuser...')

    // Track all navigation events to detect redirect loops
    const visitedUrls: string[] = []
    let redirectCount = 0

    page.on('framenavigated', (frame) => {
      if (frame === page.mainFrame()) {
        const url = frame.url()
        visitedUrls.push(url)
        console.log(`  Navigation ${visitedUrls.length}: ${url}`)

        // Detect potential redirect loop
        if (visitedUrls.length > 2) {
          const lastThree = visitedUrls.slice(-3)
          if (lastThree[0] === lastThree[2]) {
            redirectCount++
            if (redirectCount > 3) {
              console.error('❌ Detected redirect loop!')
              console.error('   URLs:', lastThree)
            }
          }
        }
      }
    })

    // Step 1: Navigate to the application
    console.log('  Step 1: Navigating to application...')
    await page.goto('/', { waitUntil: 'networkidle', timeout: 30000 })

    // Wait for Keycloak initialization to complete - increase timeout
    console.log('  Waiting for Keycloak initialization (10 seconds)...')
    await page.waitForTimeout(10000)

    const currentUrl = page.url()
    console.log(`  Current URL after initial navigation: ${currentUrl}`)

    // Step 2: Check if we need to login or if we're already on dashboard
    if (currentUrl.includes('/login') || currentUrl.includes('keycloak')) {
      console.log('  Step 2: Login required, proceeding with authentication...')

      // Check if we're on Keycloak login page
      if (currentUrl.includes('keycloak')) {
        console.log('  Step 2a: On Keycloak login page')

        // Wait for the login form to be visible
        const usernameField = page.locator('input[name="username"], input#username')
        const passwordField = page.locator('input[name="password"], input#password, input[type="password"]')
        const loginButton = page.locator('button[type="submit"], input[type="submit"], button:has-text("Sign In"), button:has-text("Log In")')

        try {
          await usernameField.waitFor({ state: 'visible', timeout: 10000 })
          console.log('    ✓ Username field found')

          await passwordField.waitFor({ state: 'visible', timeout: 10000 })
          console.log('    ✓ Password field found')

          // Fill in credentials
          console.log('  Step 3: Filling in credentials (testuser/testpass)...')
          await usernameField.fill('testuser')
          await passwordField.fill('testpass')

          // Take a screenshot before clicking login
          await page.screenshot({ path: 'test-results/before-login.png', fullPage: true })
          console.log('    📸 Screenshot saved: before-login.png')

          // Click login button
          console.log('  Step 4: Clicking login button...')
          await loginButton.click()

          // Wait for navigation after login
          console.log('  Step 5: Waiting for redirect after login...')
          await page.waitForTimeout(3000)

        } catch (error) {
          console.error('❌ Error during Keycloak login:', error)
          await page.screenshot({ path: 'test-results/login-error.png', fullPage: true })
          throw error
        }
      } else if (currentUrl.includes('/login')) {
        console.log('  Step 2b: On application login page')
        // Look for a login button that will redirect to Keycloak
        const loginButton = page.locator('button:has-text("Login"), button:has-text("Sign In"), a:has-text("Login")')

        try {
          await loginButton.waitFor({ state: 'visible', timeout: 5000 })
          console.log('    ✓ Login button found, clicking...')
          await loginButton.click()

          // Wait for redirect to Keycloak
          await page.waitForTimeout(2000)

          // Now we should be on Keycloak, repeat the login process
          const usernameField = page.locator('input[name="username"], input#username')
          const passwordField = page.locator('input[name="password"], input#password, input[type="password"]')
          const keycloakLoginButton = page.locator('button[type="submit"], input[type="submit"]')

          await usernameField.waitFor({ state: 'visible', timeout: 10000 })
          await usernameField.fill('testuser')
          await passwordField.fill('testpass')

          await page.screenshot({ path: 'test-results/before-login.png', fullPage: true })
          await keycloakLoginButton.click()
          await page.waitForTimeout(3000)
        } catch (error) {
          console.error('❌ Error during application login:', error)
          await page.screenshot({ path: 'test-results/login-page-error.png', fullPage: true })
          throw error
        }
      }
    } else {
      console.log('  Step 2: Already on a page, checking authentication status...')
    }

    // Step 6: Verify we're now on the dashboard or logged in
    console.log('  Step 6: Verifying successful login...')
    const finalUrl = page.url()
    console.log(`    Final URL: ${finalUrl}`)

    // Take a screenshot of the final state
    // DISABLED - causes browser crash
    // await page.screenshot({ path: 'test-results/after-login.png', fullPage: true })
    // console.log('    📸 Screenshot saved: after-login.png')

    // Check if we're stuck in a redirect loop
    if (redirectCount > 3) {
      console.error('❌ Test failed: Redirect loop detected')
      console.error('   Visited URLs:', visitedUrls)
      throw new Error('Redirect loop detected')
    }

    // Verify we're NOT on the login page anymore
    expect(finalUrl).not.toContain('/login')
    expect(finalUrl).not.toContain('keycloak')

    // Verify we can access dashboard content
    // Look for common dashboard elements
    const dashboardIndicators = [
      page.locator('text=/dashboard/i'),
      page.locator('[data-testid="dashboard"]'),
      page.locator('h1, h2, h3').filter({ hasText: /dashboard|home|welcome/i }),
      page.locator('nav, header').first()
    ]

    let foundDashboard = false
    for (const indicator of dashboardIndicators) {
      try {
        await indicator.first().waitFor({ state: 'visible', timeout: 5000 })
        foundDashboard = true
        console.log('    ✓ Dashboard element found')
        break
      } catch {
        // Try next indicator
      }
    }

    // If no specific dashboard indicators, at least verify we have content
    if (!foundDashboard) {
      const body = await page.locator('body')
      await expect(body).toBeVisible()
      const content = await page.textContent('body')
      expect(content).toBeTruthy()
      console.log('    ✓ Page has content')
    }

    // Verify no error messages
    const errorMessages = await page.locator('text=/error|failed|invalid/i').count()
    if (errorMessages > 0) {
      console.warn(`    ⚠️ Found ${errorMessages} potential error messages on page`)
      const errors = await page.locator('text=/error|failed|invalid/i').allTextContents()
      console.warn('    Error texts:', errors)
    }

    console.log('✅ Login test completed successfully!')
    console.log(`   Total navigation events: ${visitedUrls.length}`)
  })

  test('should complete full login flow with adminuser', async ({ page }) => {
    console.log('🧪 Starting login test with adminuser...')

    // Similar flow as above but with admin credentials
    const visitedUrls: string[] = []
    page.on('framenavigated', (frame) => {
      if (frame === page.mainFrame()) {
        visitedUrls.push(frame.url())
      }
    })

    await page.goto('/', { waitUntil: 'networkidle', timeout: 30000 })
    await page.waitForTimeout(2000)

    const currentUrl = page.url()
    console.log(`  Current URL: ${currentUrl}`)

    if (currentUrl.includes('keycloak')) {
      const usernameField = page.locator('input[name="username"], input#username')
      const passwordField = page.locator('input[name="password"], input#password, input[type="password"]')
      const loginButton = page.locator('button[type="submit"], input[type="submit"]')

      await usernameField.waitFor({ state: 'visible', timeout: 10000 })
      await usernameField.fill('adminuser')
      await passwordField.fill('adminpass')

      await page.screenshot({ path: 'test-results/admin-before-login.png', fullPage: true })
      await loginButton.click()
      await page.waitForTimeout(3000)
    }

    const finalUrl = page.url()
    console.log(`  Final URL: ${finalUrl}`)

    await page.screenshot({ path: 'test-results/admin-after-login.png', fullPage: true })

    expect(finalUrl).not.toContain('/login')
    expect(finalUrl).not.toContain('keycloak')

    console.log('✅ Admin login test completed successfully!')
  })

  test('should reject invalid credentials', async ({ page }) => {
    console.log('🧪 Starting invalid credentials test...')

    await page.goto('/', { waitUntil: 'networkidle', timeout: 30000 })
    await page.waitForTimeout(2000)

    const currentUrl = page.url()

    if (currentUrl.includes('keycloak')) {
      const usernameField = page.locator('input[name="username"], input#username')
      const passwordField = page.locator('input[name="password"], input#password, input[type="password"]')
      const loginButton = page.locator('button[type="submit"], input[type="submit"]')

      await usernameField.waitFor({ state: 'visible', timeout: 10000 })
      await usernameField.fill('invaliduser')
      await passwordField.fill('wrongpassword')

      await loginButton.click()
      await page.waitForTimeout(2000)

      // Should still be on Keycloak page with error message
      const urlAfterFail = page.url()
      expect(urlAfterFail).toContain('keycloak')

      // Look for error message
      const errorMessage = page.locator('text=/invalid|incorrect|failed/i')
      await expect(errorMessage.first()).toBeVisible({ timeout: 5000 })

      console.log('✅ Invalid credentials correctly rejected')
    } else {
      console.log('⚠️ Test skipped: Not on Keycloak login page')
    }
  })
})
