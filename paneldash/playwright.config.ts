import { defineConfig, devices } from '@playwright/test'
import * as dotenv from 'dotenv'

// Load E2E environment variables
dotenv.config({ path: './e2e.env' })

export default defineConfig({
  testDir: './tests/e2e/specs',
  fullyParallel: false, // Run serially to avoid conflicts
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1, // Single worker to avoid port conflicts

  // Output directories for artifacts
  outputDir: './tests/e2e/test-results',

  reporter: [
    ['html', { outputFolder: './tests/e2e/playwright-report' }],
    ['list'],
    ['junit', { outputFile: './tests/e2e/junit-results.xml' }],
  ],

  use: {
    baseURL: `http://${process.env.FRONTEND_HOST}:${process.env.FRONTEND_PORT}`,

    // Trace: capture detailed debugging info on failure
    trace: process.env.CI ? 'retain-on-failure' : 'on-first-retry',

    // Screenshots: always capture all screenshots for validation
    screenshot: 'on',

    // Video: only retain on failure to save space
    video: process.env.CI ? 'retain-on-failure' : 'on-first-retry',
  },

  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        // Browser launch options for better stability in CI
        launchOptions: {
          args: [
            '--disable-dev-shm-usage',
            '--disable-gpu',
            '--no-sandbox',
            '--disable-setuid-sandbox',
          ],
        },
      },
    },
  ],

  // Global setup to start all servers
  globalSetup: require.resolve('./tests/e2e/global-setup.ts'),
  globalTeardown: require.resolve('./tests/e2e/global-teardown.ts'),
})
