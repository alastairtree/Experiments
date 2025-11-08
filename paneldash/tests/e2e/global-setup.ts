import { spawn, ChildProcess } from 'child_process'
import { writeFileSync, existsSync, mkdirSync } from 'fs'
import { join } from 'path'
import * as dotenv from 'dotenv'
import { createWriteStream } from 'fs'
import { pipeline } from 'stream/promises'

// Load E2E environment
dotenv.config({ path: join(__dirname, '../../e2e.env') })

const processes: { name: string; pid: number }[] = []
const ROOT_DIR = join(__dirname, '../..')

// Database connection details (will be set by pgserver)
let dbConnectionDetails: { host: string; port: number } = { host: 'localhost', port: 5433 }

// WireMock configuration
const WIREMOCK_VERSION = '3.3.1'
const WIREMOCK_JAR_URL = `https://repo1.maven.org/maven2/org/wiremock/wiremock-standalone/${WIREMOCK_VERSION}/wiremock-standalone-${WIREMOCK_VERSION}.jar`

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

async function downloadWireMockJar(jarPath: string): Promise<void> {
  if (existsSync(jarPath)) {
    console.log('✓ WireMock jar already exists')
    return
  }

  console.log(`Downloading WireMock ${WIREMOCK_VERSION}...`)
  const response = await fetch(WIREMOCK_JAR_URL)

  if (!response.ok) {
    throw new Error(`Failed to download WireMock: ${response.statusText}`)
  }

  // Ensure directory exists
  const dir = join(jarPath, '..')
  if (!existsSync(dir)) {
    mkdirSync(dir, { recursive: true })
  }

  // Download the jar
  const fileStream = createWriteStream(jarPath)
  await pipeline(response.body as any, fileStream)
  console.log('✓ WireMock jar downloaded successfully')
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
    // 1. Start PostgreSQL Database using pgserver
    console.log('1. Starting PostgreSQL Database (pgserver)...')

    const dbReady = await new Promise<boolean>((resolve, reject) => {
      const dbProc = spawn(
        'uv',
        ['run', 'python', join(ROOT_DIR, 'tests/e2e/start-test-db.py')],
        {
          cwd: join(ROOT_DIR, 'backend'),
          stdio: 'pipe',
          detached: false,
        }
      )

      let connectionInfo: Record<string, string> = {}

      dbProc.stdout?.on('data', (data) => {
        const output = data.toString().trim()
        const lines = output.split('\n')

        for (const line of lines) {
          if (line.includes('=')) {
            const [key, value] = line.split('=')
            connectionInfo[key] = value
            console.log(`[postgres] ${line}`)

            if (key === 'READY' && value === 'true') {
              // Extract connection details
              dbConnectionDetails.host = connectionInfo.PGHOST || 'localhost'
              dbConnectionDetails.port = parseInt(connectionInfo.PGPORT || '5432')
              resolve(true)
            }
          }
        }
      })

      dbProc.stderr?.on('data', (data) => {
        const output = data.toString().trim()
        if (output) console.error(`[postgres] ${output}`)
      })

      dbProc.on('error', (error) => {
        reject(error)
      })

      if (dbProc.pid) {
        processes.push({ name: 'postgres', pid: dbProc.pid })
      }

      // Timeout after 30 seconds
      setTimeout(() => reject(new Error('Timeout waiting for database')), 30000)
    })

    console.log(`✓ PostgreSQL ready on ${dbConnectionDetails.host}:${dbConnectionDetails.port}\n`)

    // 2. Run Database Migrations
    console.log('2. Running Database Migrations...')
    const migrateResult = await new Promise<number>((resolve) => {
      const migrateProc = spawn('uv', ['run', 'alembic', 'upgrade', 'head'], {
        cwd: join(ROOT_DIR, 'backend'),
        env: {
          ...process.env,
          CENTRAL_DB_HOST: dbConnectionDetails.host,
          CENTRAL_DB_PORT: dbConnectionDetails.port.toString(),
          CENTRAL_DB_NAME: 'postgres',
          CENTRAL_DB_USER: 'postgres',
          CENTRAL_DB_PASSWORD: '',
        },
        stdio: 'pipe',
      })

      migrateProc.stdout?.on('data', (data) => {
        console.log(`[migrate] ${data.toString().trim()}`)
      })

      migrateProc.stderr?.on('data', (data) => {
        const output = data.toString().trim()
        if (output) console.error(`[migrate] ${output}`)
      })

      migrateProc.on('close', (code) => {
        resolve(code || 0)
      })
    })

    if (migrateResult !== 0) {
      throw new Error('Database migration failed')
    }
    console.log('✓ Migrations complete\n')

    // 3. Start WireMock (Keycloak Mock)
    console.log('3. Starting WireMock (Keycloak Mock)...')
    const wiremockJarPath = join(ROOT_DIR, 'tests/e2e/wiremock/wiremock-standalone.jar')
    await downloadWireMockJar(wiremockJarPath)

    const wiremockProc = startProcess(
      'wiremock',
      'java',
      [
        '-jar',
        wiremockJarPath,
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

    // 4. Start Backend API
    console.log('4. Starting Backend API...')
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
        CENTRAL_DB_HOST: dbConnectionDetails.host,
        CENTRAL_DB_PORT: dbConnectionDetails.port.toString(),
        CENTRAL_DB_NAME: 'postgres',
        CENTRAL_DB_USER: 'postgres',
        CENTRAL_DB_PASSWORD: '',
        KEYCLOAK_SERVER_URL: process.env.KEYCLOAK_SERVER_URL || 'http://localhost:8081',
        KEYCLOAK_REALM: process.env.KEYCLOAK_REALM || 'paneldash',
        KEYCLOAK_CLIENT_ID: process.env.KEYCLOAK_CLIENT_ID || 'paneldash-api',
      }
    )

    // Wait for backend to be ready
    await waitForUrl(`http://localhost:${process.env.BACKEND_PORT || 8001}/health`)
    console.log('✓ Backend API ready\n')

    // 5. Start Frontend
    console.log('5. Starting Frontend...')
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
    writeFileSync(pidsFile, JSON.stringify({ processes }, null, 2))

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
