import { useQuery } from '@tanstack/react-query'
import { apiClient } from '../api/client'

function Health() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['health'],
    queryFn: () => apiClient.getHealth(),
  })

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-50">
      <div className="max-w-md w-full bg-white shadow-lg rounded-lg p-8">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">System Health Check</h1>

        {isLoading && (
          <div className="flex items-center justify-center py-8">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
          </div>
        )}

        {error && (
          <div
            className="bg-red-50 border border-red-200 rounded-lg p-4"
            data-testid="health-error"
          >
            <div className="flex items-center">
              <svg className="h-5 w-5 text-red-400 mr-2" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
              <span className="text-red-800 font-medium">Backend Unreachable</span>
            </div>
            <p className="text-red-700 text-sm mt-2">
              {error instanceof Error ? error.message : 'Unknown error'}
            </p>
          </div>
        )}

        {data && (
          <div
            className="bg-green-50 border border-green-200 rounded-lg p-4"
            data-testid="health-success"
          >
            <div className="flex items-center">
              <svg className="h-5 w-5 text-green-400 mr-2" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
              <span className="text-green-800 font-medium">Backend Status: {data.status}</span>
            </div>
            <div className="mt-3 text-sm text-green-700">
              <p>✅ API is responding</p>
              <p>✅ Connection successful</p>
            </div>
          </div>
        )}

        <div className="mt-6 pt-6 border-t border-gray-200">
          <dl className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <dt className="font-medium text-gray-500">Endpoint</dt>
              <dd className="mt-1 text-gray-900">/health</dd>
            </div>
            <div>
              <dt className="font-medium text-gray-500">Status</dt>
              <dd className="mt-1">
                {isLoading && <span className="text-yellow-600">Checking...</span>}
                {error && <span className="text-red-600">Error</span>}
                {data && <span className="text-green-600 font-medium">Healthy</span>}
              </dd>
            </div>
          </dl>
        </div>
      </div>
    </div>
  )
}

export default Health
