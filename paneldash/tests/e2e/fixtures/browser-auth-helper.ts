/**
 * Browser Authentication Helper for E2E Tests
 *
 * This module provides utilities to inject JWT tokens into the browser context
 * for testing authenticated pages without going through the full Keycloak flow.
 */

import { Page } from '@playwright/test'
import { generateJWTToken } from './jwt-helper'

interface UserInfo {
  sub: string
  email: string
  name?: string
  preferred_username?: string
  email_verified?: boolean
  realm_access?: {
    roles: string[]
  }
}

/**
 * Authenticate a page by injecting a JWT token into localStorage
 *
 * This allows tests to bypass the Keycloak login flow and directly
 * navigate to protected pages.
 *
 * IMPORTANT: Call this BEFORE navigating to any page
 *
 * @param page - Playwright page instance
 * @param userInfo - User information to generate JWT token
 */
export async function authenticatePageWithToken(
  page: Page,
  userInfo: UserInfo
): Promise<string> {
  const token = generateJWTToken(userInfo)

  // Inject token and E2E flag into localStorage before page loads
  await page.addInitScript((authToken) => {
    localStorage.setItem('auth_token', authToken)
    localStorage.setItem('e2e_testing', 'true')
  }, token)

  return token
}

/**
 * Check if the page is currently authenticated by verifying localStorage token
 */
export async function isPageAuthenticated(page: Page): Promise<boolean> {
  const token = await page.evaluate(() => localStorage.getItem('auth_token'))
  return !!token
}

/**
 * Clear authentication from the page by removing the token from localStorage
 */
export async function clearPageAuthentication(page: Page): Promise<void> {
  await page.evaluate(() => {
    localStorage.removeItem('auth_token')
  })
}

/**
 * Get the current authentication token from the page
 */
export async function getPageAuthToken(page: Page): Promise<string | null> {
  return await page.evaluate(() => localStorage.getItem('auth_token'))
}

/**
 * Wait for authentication to complete after page load
 *
 * This checks if the app has finished loading and authentication is complete
 * by waiting for the loading spinner to disappear
 *
 * @param page - Playwright page instance
 * @param timeout - Maximum time to wait in milliseconds (default: 10000)
 */
export async function waitForAuthComplete(page: Page, timeout: number = 10000): Promise<void> {
  try {
    // Wait for either successful auth or redirect to login
    await Promise.race([
      // Wait for loading to finish (loading indicator should disappear)
      page.waitForSelector('text=/Loading/i', { state: 'hidden', timeout }),
      // Or wait for login page (means auth failed)
      page.waitForURL('**/login', { timeout }),
      // Or wait for successful page load
      page.waitForLoadState('networkidle', { timeout: Math.min(timeout, 5000) })
    ])
  } catch (error) {
    console.warn('Auth wait timed out or failed:', error)
    // Don't throw - let the test continue and fail on its own assertions
  }
}
