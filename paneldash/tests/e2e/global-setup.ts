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
    console.log(`[${name}] ${data.toString().trim()}`)
  })

  proc.stderr?.on('data', (data) => {
    console.error(`[${name}] ${data.toString().trim()}`)
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
    // 1. Start pgserver (test database)
    console.log('1. Starting pgserver...')
    const dbProc = startProcess(
      'pgserver',
      'python',
      ['-m', 'pgserver', '--port', process.env.CENTRAL_DB_PORT!],
      join(ROOT_DIR, 'backend'),
      {}
    )

    // Give database time to initialize
    await new Promise((resolve) => setTimeout(resolve, 5000))
    console.log('✓ Database ready\n')

    // 2. Download and start WireMock
    console.log('2. Starting WireMock...')
    // Check if wiremock jar exists, if not download it
    const wiremockJar = join(ROOT_DIR, 'tests/e2e/wiremock/wiremock-standalone.jar')
    try {
      require('fs').statSync(wiremockJar)
    } catch {
      console.log('Downloading WireMock...')
      const { execSync } = require('child_process')
      execSync(
        `curl -L https://repo1.maven.org/maven2/org/wiremock/wiremock-standalone/3.3.1/wiremock-standalone-3.3.1.jar -o ${wiremockJar}`,
        { stdio: 'inherit' }
      )
    }

    const wiremockProc = startProcess(
      'wiremock',
      'java',
      [
        '-jar',
        wiremockJar,
        '--port',
        process.env.WIREMOCK_PORT!,
        '--root-dir',
        join(ROOT_DIR, 'tests/e2e/wiremock'),
      ],
      ROOT_DIR,
      {}
    )

    // Wait for WireMock to be ready
    await waitForUrl(`http://localhost:${process.env.WIREMOCK_PORT}/__admin/`)
    console.log('✓ WireMock ready\n')

    // 3. Start Backend API
    console.log('3. Starting Backend API...')
    const backendProc = startProcess(
      'backend',
      'uv',
      [
        'run',
        'uvicorn',
        'app.main:app',
        '--host',
        process.env.BACKEND_HOST!,
        '--port',
        process.env.BACKEND_PORT!,
      ],
      join(ROOT_DIR, 'backend'),
      {
        CENTRAL_DB_HOST: process.env.CENTRAL_DB_HOST!,
        CENTRAL_DB_PORT: process.env.CENTRAL_DB_PORT!,
        CENTRAL_DB_NAME: process.env.CENTRAL_DB_NAME!,
        CENTRAL_DB_USER: process.env.CENTRAL_DB_USER!,
        CENTRAL_DB_PASSWORD: process.env.CENTRAL_DB_PASSWORD!,
        KEYCLOAK_SERVER_URL: process.env.KEYCLOAK_SERVER_URL!,
        KEYCLOAK_REALM: process.env.KEYCLOAK_REALM!,
        KEYCLOAK_CLIENT_ID: process.env.KEYCLOAK_CLIENT_ID!,
      }
    )

    // Wait for backend to be ready
    await waitForUrl(`http://localhost:${process.env.BACKEND_PORT}/health`)
    console.log('✓ Backend API ready\n')

    // 4. Start Frontend
    console.log('4. Starting Frontend...')
    const frontendProc = startProcess(
      'frontend',
      'npm',
      ['run', 'dev', '--', '--host', process.env.FRONTEND_HOST!, '--port', process.env.FRONTEND_PORT!],
      join(ROOT_DIR, 'frontend'),
      {
        VITE_API_URL: process.env.VITE_API_URL!,
        VITE_KEYCLOAK_URL: process.env.VITE_KEYCLOAK_URL!,
        VITE_KEYCLOAK_REALM: process.env.VITE_KEYCLOAK_REALM!,
        VITE_KEYCLOAK_CLIENT_ID: process.env.VITE_KEYCLOAK_CLIENT_ID!,
      }
    )

    // Wait for frontend to be ready
    await waitForUrl(`http://localhost:${process.env.FRONTEND_PORT}`)
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
