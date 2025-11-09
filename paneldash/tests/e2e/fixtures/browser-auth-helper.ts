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
 * @param page - Playwright page instance
 * @param userInfo - User information to generate JWT token
 */
export async function authenticatePageWithToken(
  page: Page,
  userInfo: UserInfo
): Promise<string> {
  const token = generateJWTToken(userInfo)

  // Inject token into localStorage before navigation
  await page.addInitScript((authToken) => {
    localStorage.setItem('auth_token', authToken)
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
