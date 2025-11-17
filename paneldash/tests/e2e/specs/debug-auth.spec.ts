import { test, expect, chromium } from '@playwright/test'

test('debug authentication flow manual', async () => {
  // Launch browser manually to control it better
  const browser = await chromium.launch({ headless: true })
  const context = await browser.newContext()
  const page = await context.newPage()

  let consoleMessages: string[] = []
  let pageErrors: string[] = []
  // Capture all console messages including errors
  page.on('console', msg => {
    const type = msg.type()
    const text = msg.text()
    console.log(`[${type.toUpperCase()}] ${text}`)
  })

  // Capture page errors
  page.on('pageerror', error => {
    console.log(`[PAGE ERROR] ${error.message}`)
    console.log(error.stack)
  })

  // Navigate to the app
  console.log('Navigating to app...')
  await page.goto('/', { waitUntil: 'networkidle', timeout: 30000 })

  console.log('Current URL:', page.url())

  // Wait for React to mount by checking for the loading spinner
  console.log('Waiting for React to render...')
  try {
    await page.waitForSelector('text=Loading...', { timeout: 10000 })
    console.log('✅ Found "Loading..." text - React has rendered!')
  } catch (e) {
    console.log('❌ Could not find "Loading..." text')
  }

  // Wait to see what happens - increase wait time
  console.log('Waiting 10 seconds to see if useEffect runs...')
  await page.waitForTimeout(10000)

  console.log('Final URL:', page.url())

  // Check page content
  const bodyText = await page.textContent('body')
  console.log('Page body contains:', bodyText?.substring(0, 200))

  // Don't take screenshot - that's what causes crash
  // await page.screenshot({ path: 'test-results/debug-auth.png', fullPage: true })

  console.log('Test complete!')
})
