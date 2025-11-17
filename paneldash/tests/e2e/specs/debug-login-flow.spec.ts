import { test, expect } from '@playwright/test'

test.setTimeout(120000) // 2 minute timeout

test('debug complete login flow with all logs', async ({ page }) => {
  const consoleMessages: string[] = []
  const networkRequests: Array<{ url: string; method: string; status?: number }> = []
  const networkErrors: string[] = []

  // Capture all console messages
  page.on('console', msg => {
    const text = `[${msg.type().toUpperCase()}] ${msg.text()}`
    consoleMessages.push(text)
    console.log(text)
  })

  // Capture page errors
  page.on('pageerror', error => {
    const text = `[PAGE ERROR] ${error.message}`
    consoleMessages.push(text)
    console.log(text)
  })

  // Capture all network requests
  page.on('request', request => {
    const req = {
      url: request.url(),
      method: request.method()
    }
    networkRequests.push(req)
    console.log(`→ ${req.method} ${req.url}`)
  })

  page.on('response', response => {
    const req = networkRequests.find(r => r.url === response.url() && !r.status)
    if (req) {
      req.status = response.status()
    }
    console.log(`← ${response.status()} ${response.url()}`)
  })

  page.on('requestfailed', request => {
    const text = `[NETWORK ERROR] ${request.url()} - ${request.failure()?.errorText}`
    networkErrors.push(text)
    console.log(text)
  })

  console.log('\n========== STARTING TEST ==========\n')
  console.log('Step 1: Navigate to application')

  // Navigate directly, will clear cooldown inline
  await page.goto('http://localhost:5173/', { waitUntil: 'networkidle', timeout: 60000 })

  // Clear any previous cooldown
  console.log('Step 2: Clearing redirect cooldown')
  try {
    await page.evaluate(() => {
      localStorage.removeItem('keycloak_redirect_timestamp')
    })
  } catch (e) {
    console.log('Could not clear localStorage, continuing anyway')
  }

  // Wait for Keycloak to initialize
  console.log('Step 3: Waiting for Keycloak initialization (15 seconds)...')
  await page.waitForTimeout(15000)

  const currentUrl = page.url()
  console.log(`\nStep 4: Current URL: ${currentUrl}`)

  // Check if we're on Keycloak login page
  if (currentUrl.includes('keycloak')) {
    console.log('Step 5: On Keycloak login page, entering credentials')

    // Wait for login form
    await page.waitForSelector('input[name="username"]', { timeout: 10000 })
    await page.fill('input[name="username"]', 'adminuser')
    await page.fill('input[name="password"]', 'adminpass')

    console.log('Step 6: Submitting login form')
    await page.click('input[type="submit"]')

    console.log('Step 7: Waiting for redirect back to app (20 seconds)...')
    await page.waitForTimeout(20000)

    const finalUrl = page.url()
    console.log(`\nStep 8: Final URL: ${finalUrl}`)

    // Check if we successfully logged in
    const isDashboard = finalUrl.includes('/dashboard') || finalUrl.includes('localhost:5173')
    console.log(`Is on dashboard/app: ${isDashboard}`)

    // Wait a bit more to see if there's a redirect loop
    console.log('\nStep 9: Monitoring for redirect loops (15 seconds)...')
    const urlsBefore = [finalUrl]
    await page.waitForTimeout(5000)
    urlsBefore.push(page.url())
    await page.waitForTimeout(5000)
    urlsBefore.push(page.url())
    await page.waitForTimeout(5000)
    urlsBefore.push(page.url())

    console.log('\nURLs over time:', urlsBefore)

    const uniqueUrls = new Set(urlsBefore)
    if (uniqueUrls.size > 2) {
      console.log('⚠️ WARNING: Possible redirect loop detected!')
    }
  } else {
    console.log('Step 5: Not on Keycloak login page')
    console.log('Current page title:', await page.title())

    // Try to get page content
    try {
      const bodyText = await page.locator('body').textContent()
      console.log('Page content (first 500 chars):', bodyText?.substring(0, 500))
    } catch (e) {
      console.log('Could not get page content:', e)
    }
  }

  console.log('\n========== CONSOLE MESSAGES SUMMARY ==========')
  console.log(`Total console messages: ${consoleMessages.length}`)
  consoleMessages.forEach((msg, i) => {
    console.log(`${i + 1}. ${msg}`)
  })

  console.log('\n========== NETWORK REQUESTS SUMMARY ==========')
  console.log(`Total requests: ${networkRequests.length}`)

  // Group by domain
  const keycloakRequests = networkRequests.filter(r => r.url.includes('keycloak'))
  const frontendRequests = networkRequests.filter(r => r.url.includes('localhost:5173'))
  const backendRequests = networkRequests.filter(r => r.url.includes('localhost:8001'))

  console.log(`\nKeycloak requests: ${keycloakRequests.length}`)
  keycloakRequests.forEach(r => console.log(`  ${r.method} ${r.status || '...'} ${r.url}`))

  console.log(`\nFrontend requests: ${frontendRequests.length}`)
  frontendRequests.slice(0, 10).forEach(r => console.log(`  ${r.method} ${r.status || '...'} ${r.url}`))

  console.log(`\nBackend requests: ${backendRequests.length}`)
  backendRequests.forEach(r => console.log(`  ${r.method} ${r.status || '...'} ${r.url}`))

  console.log('\n========== NETWORK ERRORS ==========')
  console.log(`Total network errors: ${networkErrors.length}`)
  networkErrors.forEach(err => console.log(`  ${err}`))

  console.log('\n========== TEST COMPLETE ==========\n')

  // Don't fail the test, just collect data
  expect(true).toBe(true)
})
