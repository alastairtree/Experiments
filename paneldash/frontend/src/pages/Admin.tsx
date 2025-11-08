import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient, User, Tenant } from '../api/client'
import Header from '../components/Header'

export default function Admin() {
  const queryClient = useQueryClient()
  const [selectedUser, setSelectedUser] = useState<User | null>(null)
  const [isAssigning, setIsAssigning] = useState(false)

  // Fetch all users
  const { data: users = [], isLoading: isLoadingUsers } = useQuery({
    queryKey: ['admin', 'users'],
    queryFn: () => apiClient.getUsers(),
  })

  // Fetch all tenants
  const { data: tenants = [], isLoading: isLoadingTenants } = useQuery({
    queryKey: ['admin', 'tenants'],
    queryFn: () => apiClient.getTenants(),
  })

  // Delete user mutation
  const deleteUserMutation = useMutation({
    mutationFn: (userId: string) => apiClient.deleteUser(userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] })
      setSelectedUser(null)
    },
  })

  // Update user mutation
  const updateUserMutation = useMutation({
    mutationFn: ({ userId, data }: { userId: string; data: Partial<User> }) =>
      apiClient.updateUser(userId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] })
    },
  })

  // Assign user to tenant mutation
  const assignUserMutation = useMutation({
    mutationFn: ({ tenantId, userId }: { tenantId: string; userId: string }) =>
      apiClient.assignUserToTenant(tenantId, userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] })
      setIsAssigning(false)
    },
  })

  // Remove user from tenant mutation
  const removeUserMutation = useMutation({
    mutationFn: ({ tenantId, userId }: { tenantId: string; userId: string }) =>
      apiClient.removeUserFromTenant(tenantId, userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] })
    },
  })

  const handleToggleAdmin = (user: User) => {
    updateUserMutation.mutate({
      userId: user.id,
      data: { is_admin: !user.is_admin },
    })
  }

  const handleDeleteUser = (userId: string) => {
    if (confirm('Are you sure you want to delete this user?')) {
      deleteUserMutation.mutate(userId)
    }
  }

  const handleAssignToTenant = (tenantId: string) => {
    if (selectedUser) {
      assignUserMutation.mutate({ tenantId, userId: selectedUser.id })
    }
  }

  const handleRemoveFromTenant = (tenantId: string) => {
    if (selectedUser) {
      removeUserMutation.mutate({ tenantId, userId: selectedUser.id })
    }
  }

  if (isLoadingUsers || isLoadingTenants) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Header />
        <div className="flex items-center justify-center py-12">
          <div className="text-center">
            <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-blue-600 border-r-transparent"></div>
            <p className="mt-4 text-gray-600">Loading...</p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          <h1 className="text-3xl font-bold text-gray-900 mb-6">
            User Management
          </h1>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Users List */}
            <div className="bg-white shadow rounded-lg overflow-hidden">
              <div className="px-4 py-5 sm:px-6 bg-gray-50 border-b border-gray-200">
                <h2 className="text-lg font-medium text-gray-900">
                  All Users ({users.length})
                </h2>
              </div>
              <ul className="divide-y divide-gray-200 max-h-96 overflow-y-auto">
                {users.map((user) => (
                  <li
                    key={user.id}
                    className={`px-4 py-4 hover:bg-gray-50 cursor-pointer ${
                      selectedUser?.id === user.id ? 'bg-blue-50' : ''
                    }`}
                    onClick={() => setSelectedUser(user)}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900 truncate">
                          {user.full_name}
                        </p>
                        <p className="text-sm text-gray-500 truncate">
                          {user.email}
                        </p>
                        <div className="mt-1 flex items-center space-x-2">
                          {user.is_admin && (
                            <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-800">
                              Admin
                            </span>
                          )}
                          <span className="text-xs text-gray-500">
                            {user.accessible_tenant_ids.length} tenant(s)
                          </span>
                        </div>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            </div>

            {/* User Details & Actions */}
            <div className="bg-white shadow rounded-lg overflow-hidden">
              <div className="px-4 py-5 sm:px-6 bg-gray-50 border-b border-gray-200">
                <h2 className="text-lg font-medium text-gray-900">
                  {selectedUser ? 'User Details' : 'Select a User'}
                </h2>
              </div>
              {selectedUser ? (
                <div className="px-4 py-5 sm:p-6">
                  <dl className="grid grid-cols-1 gap-4 mb-6">
                    <div>
                      <dt className="text-sm font-medium text-gray-500">
                        Full Name
                      </dt>
                      <dd className="mt-1 text-sm text-gray-900">
                        {selectedUser.full_name}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-sm font-medium text-gray-500">Email</dt>
                      <dd className="mt-1 text-sm text-gray-900">
                        {selectedUser.email}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-sm font-medium text-gray-500">
                        Keycloak ID
                      </dt>
                      <dd className="mt-1 text-sm text-gray-900 font-mono text-xs">
                        {selectedUser.keycloak_id}
                      </dd>
                    </div>
                  </dl>

                  <div className="space-y-4 border-t border-gray-200 pt-4">
                    <button
                      onClick={() => handleToggleAdmin(selectedUser)}
                      disabled={updateUserMutation.isPending}
                      className="w-full inline-flex justify-center items-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
                    >
                      {selectedUser.is_admin
                        ? 'Remove Admin Rights'
                        : 'Grant Admin Rights'}
                    </button>

                    <button
                      onClick={() => setIsAssigning(!isAssigning)}
                      className="w-full inline-flex justify-center items-center px-4 py-2 border border-blue-300 shadow-sm text-sm font-medium rounded-md text-blue-700 bg-blue-50 hover:bg-blue-100 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                    >
                      {isAssigning ? 'Cancel' : 'Manage Tenant Access'}
                    </button>

                    {isAssigning && (
                      <div className="border border-gray-200 rounded-md p-4 space-y-2">
                        <h3 className="text-sm font-medium text-gray-900 mb-2">
                          Available Tenants
                        </h3>
                        {tenants.map((tenant) => {
                          const hasAccess =
                            selectedUser.accessible_tenant_ids.includes(
                              tenant.id
                            )
                          return (
                            <div
                              key={tenant.id}
                              className="flex items-center justify-between py-2"
                            >
                              <div>
                                <p className="text-sm font-medium text-gray-900">
                                  {tenant.name}
                                </p>
                                <p className="text-xs text-gray-500">
                                  {tenant.tenant_id}
                                </p>
                              </div>
                              <button
                                onClick={() =>
                                  hasAccess
                                    ? handleRemoveFromTenant(tenant.id)
                                    : handleAssignToTenant(tenant.id)
                                }
                                disabled={
                                  assignUserMutation.isPending ||
                                  removeUserMutation.isPending
                                }
                                className={`px-3 py-1 text-xs font-medium rounded ${
                                  hasAccess
                                    ? 'bg-red-100 text-red-700 hover:bg-red-200'
                                    : 'bg-green-100 text-green-700 hover:bg-green-200'
                                } disabled:opacity-50`}
                              >
                                {hasAccess ? 'Remove' : 'Add'}
                              </button>
                            </div>
                          )
                        })}
                      </div>
                    )}

                    <button
                      onClick={() => handleDeleteUser(selectedUser.id)}
                      disabled={deleteUserMutation.isPending}
                      className="w-full inline-flex justify-center items-center px-4 py-2 border border-red-300 shadow-sm text-sm font-medium rounded-md text-red-700 bg-red-50 hover:bg-red-100 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-50"
                    >
                      Delete User
                    </button>
                  </div>
                </div>
              ) : (
                <div className="px-4 py-12 text-center text-gray-500">
                  Select a user from the list to view details and manage access
                </div>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
