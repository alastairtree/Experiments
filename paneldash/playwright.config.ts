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
  reporter: 'html',

  use: {
    baseURL: `http://${process.env.FRONTEND_HOST}:${process.env.FRONTEND_PORT}`,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  // Global setup to start all servers
  globalSetup: require.resolve('./tests/e2e/global-setup.ts'),
  globalTeardown: require.resolve('./tests/e2e/global-teardown.ts'),
})
