import { spawn, ChildProcess } from 'child_process'
import { writeFileSync } from 'fs'
import { join } from 'path'
import * as dotenv from 'dotenv'

// Load E2E environment
dotenv.config({ path: join(__dirname, '../../e2e.env') })

const processes: { name: string; pid: number }[] = []
const ROOT_DIR = join(__dirname, '../..')

async function waitForUrl(url: string, timeout = 60000): Promise<void> {
  const start = Date.now()
  while (Date.now() - start < timeout) {
    try {
      const response = await fetch(url)
      if (response.ok) {
        console.log(`✓ ${url} is ready`)
        return
      }
    } catch (error) {
      // Service not ready yet
    }
    await new Promise((resolve) => setTimeout(resolve, 1000))
  }
  throw new Error(`Timeout waiting for ${url}`)
}

function startProcess(
  name: string,
  command: string,
  args: string[],
  cwd: string,
  env: Record<string, string> = {}
): ChildProcess {
  console.log(`Starting ${name}...`)
  const proc = spawn(command, args, {
    cwd,
    env: { ...process.env, ...env },
    stdio: 'pipe',
    detached: false,
  })

  proc.stdout?.on('data', (data) => {
    const output = data.toString().trim()
    if (output) console.log(`[${name}] ${output}`)
  })

  proc.stderr?.on('data', (data) => {
    const output = data.toString().trim()
    if (output && !output.includes('Warning:')) {
      console.error(`[${name}] ${output}`)
    }
  })

  proc.on('error', (error) => {
    console.error(`[${name}] Error:`, error)
  })

  if (proc.pid) {
    processes.push({ name, pid: proc.pid })
    console.log(`✓ ${name} started (PID: ${proc.pid})`)
  }

  return proc
}

export default async function globalSetup() {
  console.log('\n=== Starting E2E Test Infrastructure ===\n')

  try {
    // 1. Start WireMock (Keycloak Mock)
    console.log('1. Starting WireMock (Keycloak Mock)...')
    const wiremockProc = startProcess(
      'wiremock',
      'java',
      [
        '-jar',
        join(ROOT_DIR, 'tests/e2e/wiremock/wiremock-standalone.jar'),
        '--port',
        process.env.WIREMOCK_PORT || '8081',
        '--root-dir',
        join(ROOT_DIR, 'tests/e2e/wiremock'),
        '--global-response-templating',
      ],
      ROOT_DIR,
      {}
    )

    // Wait for WireMock to be ready
    await waitForUrl(`http://localhost:${process.env.WIREMOCK_PORT || 8081}/__admin/`)
    console.log('✓ WireMock ready\n')

    // 2. Start Backend API
    console.log('2. Starting Backend API...')
    const backendProc = startProcess(
      'backend',
      'uv',
      [
        'run',
        'uvicorn',
        'app.main:app',
        '--host',
        process.env.BACKEND_HOST || 'localhost',
        '--port',
        process.env.BACKEND_PORT || '8001',
      ],
      join(ROOT_DIR, 'backend'),
      {
        // Backend will use environment variables or defaults
        ...(process.env.CENTRAL_DB_HOST && { CENTRAL_DB_HOST: process.env.CENTRAL_DB_HOST }),
        ...(process.env.CENTRAL_DB_PORT && { CENTRAL_DB_PORT: process.env.CENTRAL_DB_PORT }),
        KEYCLOAK_SERVER_URL: process.env.KEYCLOAK_SERVER_URL || 'http://localhost:8081',
        KEYCLOAK_REALM: process.env.KEYCLOAK_REALM || 'paneldash',
        KEYCLOAK_CLIENT_ID: process.env.KEYCLOAK_CLIENT_ID || 'paneldash-api',
      }
    )

    // Wait for backend to be ready
    await waitForUrl(`http://localhost:${process.env.BACKEND_PORT || 8001}/health`)
    console.log('✓ Backend API ready\n')

    // 3. Start Frontend
    console.log('3. Starting Frontend...')
    const frontendProc = startProcess(
      'frontend',
      'npm',
      [
        'run',
        'dev',
        '--',
        '--host',
        process.env.FRONTEND_HOST || 'localhost',
        '--port',
        process.env.FRONTEND_PORT || '5174',
      ],
      join(ROOT_DIR, 'frontend'),
      {
        VITE_API_URL: process.env.VITE_API_URL || 'http://localhost:8001',
        VITE_KEYCLOAK_URL: process.env.VITE_KEYCLOAK_URL || 'http://localhost:8081',
        VITE_KEYCLOAK_REALM: process.env.VITE_KEYCLOAK_REALM || 'paneldash',
        VITE_KEYCLOAK_CLIENT_ID: process.env.VITE_KEYCLOAK_CLIENT_ID || 'paneldash-frontend',
      }
    )

    // Wait for frontend to be ready
    await waitForUrl(`http://localhost:${process.env.FRONTEND_PORT || 5174}`)
    console.log('✓ Frontend ready\n')

    // Save process IDs for teardown
    const pidsFile = join(ROOT_DIR, 'tests/e2e/.pids.json')
    writeFileSync(pidsFile, JSON.stringify(processes, null, 2))

    console.log('=== All E2E services ready! ===\n')
  } catch (error) {
    console.error('Failed to start E2E infrastructure:', error)
    // Kill any started processes
    processes.forEach(({ name, pid }) => {
      console.log(`Killing ${name} (${pid})...`)
      try {
        process.kill(pid, 'SIGTERM')
      } catch (e) {
        // Process may already be dead
      }
    })
    throw error
  }
}
