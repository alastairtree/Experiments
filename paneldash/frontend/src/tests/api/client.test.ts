import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { ApiClient } from '../../api/client'

describe('ApiClient', () => {
  let client: ApiClient
  let fetchSpy: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    client = new ApiClient('http://test-api')
    fetchSpy = vi.spyOn(global, 'fetch')
    // Clear localStorage
    localStorage.clear()
  })

  afterEach(() => {
    fetchSpy.mockRestore()
  })

  describe('Token Management', () => {
    it('should initialize with null token', () => {
      expect(client.getToken()).toBeNull()
    })

    it('should store token in localStorage when set', () => {
      client.setToken('test-token')
      expect(localStorage.getItem('auth_token')).toBe('test-token')
      expect(client.getToken()).toBe('test-token')
    })

    it('should load token from localStorage on initialization', () => {
      localStorage.setItem('auth_token', 'existing-token')
      const newClient = new ApiClient('http://test-api')
      expect(newClient.getToken()).toBe('existing-token')
    })

    it('should remove token from localStorage when set to null', () => {
      client.setToken('test-token')
      client.setToken(null)
      expect(localStorage.getItem('auth_token')).toBeNull()
      expect(client.getToken()).toBeNull()
    })
  })

  describe('HTTP Headers', () => {
    it('should include Authorization header when token is set', async () => {
      client.setToken('test-token')
      fetchSpy.mockResolvedValueOnce(
        new Response(JSON.stringify({ status: 'healthy' }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      )

      await client.getHealth()

      expect(fetchSpy).toHaveBeenCalledWith(
        'http://test-api/health',
        expect.objectContaining({
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
          }),
        })
      )
    })
  })

  describe('getHealth', () => {
    it('should fetch health status', async () => {
      fetchSpy.mockResolvedValueOnce(
        new Response(JSON.stringify({ status: 'healthy' }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      )

      const result = await client.getHealth()

      expect(result).toEqual({ status: 'healthy' })
      expect(fetchSpy).toHaveBeenCalledWith(
        'http://test-api/health',
        expect.any(Object)
      )
    })

    it('should throw error on failed health check', async () => {
      fetchSpy.mockResolvedValueOnce(
        new Response('', {
          status: 500,
          statusText: 'Internal Server Error',
        })
      )

      await expect(client.getHealth()).rejects.toThrow('Health check failed')
    })
  })

  describe('getMe', () => {
    it('should fetch current user', async () => {
      const mockUser = {
        id: '1',
        email: 'test@example.com',
        full_name: 'Test User',
        keycloak_id: 'kc-123',
        is_admin: false,
        accessible_tenant_ids: [],
      }

      client.setToken('test-token')
      fetchSpy.mockResolvedValueOnce(
        new Response(JSON.stringify(mockUser), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      )

      const result = await client.getMe()

      expect(result).toEqual(mockUser)
      expect(fetchSpy).toHaveBeenCalledWith(
        'http://test-api/api/v1/auth/me',
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: 'Bearer test-token',
          }),
        })
      )
    })

    it('should throw Unauthorized error on 401', async () => {
      client.setToken('invalid-token')
      fetchSpy.mockResolvedValueOnce(
        new Response('', {
          status: 401,
          statusText: 'Unauthorized',
        })
      )

      await expect(client.getMe()).rejects.toThrow('Unauthorized')
    })
  })

  describe('getTenants', () => {
    it('should fetch list of tenants', async () => {
      const mockTenants = [
        { id: '1', tenant_id: 't1', name: 'Tenant 1', is_active: true },
        { id: '2', tenant_id: 't2', name: 'Tenant 2', is_active: true },
      ]

      client.setToken('test-token')
      fetchSpy.mockResolvedValueOnce(
        new Response(JSON.stringify(mockTenants), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      )

      const result = await client.getTenants()

      expect(result).toEqual(mockTenants)
    })
  })

  describe('getUsers', () => {
    it('should fetch list of users', async () => {
      const mockUsers = [
        {
          id: '1',
          email: 'user1@example.com',
          full_name: 'User 1',
          keycloak_id: 'kc-1',
          is_admin: false,
          accessible_tenant_ids: [],
        },
      ]

      client.setToken('test-token')
      fetchSpy.mockResolvedValueOnce(
        new Response(JSON.stringify(mockUsers), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      )

      const result = await client.getUsers()

      expect(result).toEqual(mockUsers)
    })
  })

  describe('updateUser', () => {
    it('should update user with PATCH request', async () => {
      const mockUser = {
        id: '1',
        email: 'user@example.com',
        full_name: 'Updated Name',
        keycloak_id: 'kc-1',
        is_admin: true,
        accessible_tenant_ids: [],
      }

      client.setToken('test-token')
      fetchSpy.mockResolvedValueOnce(
        new Response(JSON.stringify(mockUser), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      )

      const result = await client.updateUser('1', {
        full_name: 'Updated Name',
        is_admin: true,
      })

      expect(result).toEqual(mockUser)
      expect(fetchSpy).toHaveBeenCalledWith(
        'http://test-api/api/v1/users/1',
        expect.objectContaining({
          method: 'PATCH',
          body: JSON.stringify({
            full_name: 'Updated Name',
            is_admin: true,
          }),
        })
      )
    })
  })

  describe('deleteUser', () => {
    it('should delete user with DELETE request', async () => {
      client.setToken('test-token')
      fetchSpy.mockResolvedValueOnce(
        new Response('', {
          status: 204,
        })
      )

      await client.deleteUser('1')

      expect(fetchSpy).toHaveBeenCalledWith(
        'http://test-api/api/v1/users/1',
        expect.objectContaining({
          method: 'DELETE',
        })
      )
    })
  })
})
