import { readFileSync, unlinkSync } from 'fs'
import { join } from 'path'
import { spawn } from 'child_process'

export default async function globalTeardown() {
  console.log('\n=== Stopping E2E Test Infrastructure ===\n')

  const ROOT_DIR = join(__dirname, '../..')
  const pidsFile = join(ROOT_DIR, 'tests/e2e/.pids.json')

  try {
    const pidsData = readFileSync(pidsFile, 'utf-8')
    const data = JSON.parse(pidsData)
    const processes: { name: string; pid: number }[] = data.processes || data

    // Kill processes in reverse order
    for (const { name, pid } of processes.reverse()) {
      console.log(`Stopping ${name} (PID: ${pid})...`)
      try {
        process.kill(pid, 'SIGTERM')
        // Give it a moment to terminate gracefully
        await new Promise((resolve) => setTimeout(resolve, 1000))

        // Check if still running and force kill if needed
        try {
          process.kill(pid, 0) // Check if process exists
          console.log(`Force killing ${name}...`)
          process.kill(pid, 'SIGKILL')
        } catch {
          // Process is already dead
        }
        console.log(`✓ ${name} stopped`)
      } catch (error: any) {
        if (error.code === 'ESRCH') {
          console.log(`✓ ${name} already stopped`)
        } else {
          console.error(`Failed to stop ${name}:`, error.message)
        }
      }
    }

    // Clean up PID file
    unlinkSync(pidsFile)
    console.log('\n=== E2E Infrastructure stopped ===\n')
  } catch (error) {
    console.error('Error during teardown:', error)
  }
}
