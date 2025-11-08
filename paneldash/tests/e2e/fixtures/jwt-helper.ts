/**
 * JWT Token Generation Helper for E2E Tests
 *
 * This module generates valid JWT tokens that can be verified by the backend
 * using the WireMock public key setup.
 */

import jwt from 'jsonwebtoken'
import { TEST_PRIVATE_KEY } from './test-keys'

interface UserInfo {
  sub: string // Keycloak user ID
  email: string
  name?: string
  preferred_username?: string
  email_verified?: boolean
  realm_access?: {
    roles: string[]
  }
}

/**
 * Generate a valid JWT token for testing
 */
export function generateJWTToken(userInfo: UserInfo): string {
  const now = Math.floor(Date.now() / 1000)

  const payload = {
    ...userInfo,
    iat: now,
    exp: now + 3600, // Valid for 1 hour
    iss: 'http://localhost:8081/realms/paneldash',
    aud: 'paneldash-api',
  }

  return jwt.sign(payload, TEST_PRIVATE_KEY, {
    algorithm: 'RS256',
    keyid: 'test-key-id',
  })
}

// Predefined test users
export const TEST_USERS = {
  validUser: {
    sub: 'e2e-valid-user-kc-id',
    email: 'validuser@example.com',
    name: 'Valid Test User',
    preferred_username: 'validuser',
    email_verified: true,
    realm_access: {
      roles: ['user']
    }
  },
  invalidUser: {
    sub: 'e2e-invalid-user-kc-id',
    email: 'invaliduser@example.com',
    name: 'Invalid Test User',
    preferred_username: 'invaliduser',
    email_verified: true,
    realm_access: {
      roles: ['user']
    }
  },
  adminUser: {
    sub: 'e2e-admin-user-kc-id',
    email: 'adminuser@example.com',
    name: 'Admin Test User',
    preferred_username: 'adminuser',
    email_verified: true,
    realm_access: {
      roles: ['admin']
    }
  }
}
