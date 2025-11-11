# E2E Testing with Screenshots

This directory contains end-to-end tests for the PanelDash application using Playwright.

## Features

- ✅ Full integration testing with real backend and frontend
- 📸 Automatic screenshot capture of all pages and components
- 🎥 Video recording of test execution
- 📊 HTML test reports with visual diff
- 🏗️ GitHub Actions CI integration
- 📦 Screenshot artifacts uploaded to CI

## Running E2E Tests Locally

### Prerequisites

1. Backend server running on `http://localhost:8001`
2. Frontend server running on `http://localhost:5174`

### Quick Start

```bash
# From the project root
./run-e2e-tests.sh
```

This script will:
1. Check if servers are running
2. Run all E2E tests
3. Capture screenshots
4. Create a zip archive of screenshots
5. Generate HTML report

### Manual Execution

```bash
# Install Playwright browsers (first time only)
npx playwright install chromium

# Run tests
npx playwright test

# View HTML report
npx playwright show-report
```

## Test Structure

```
tests/e2e/
├── specs/                          # Test files
│   ├── smoke.spec.ts              # Basic smoke tests
│   ├── dashboard-panels.spec.ts   # Dashboard and panel tests
│   └── ...
├── global-setup.ts                # Setup before all tests
├── global-teardown.ts             # Cleanup after all tests
└── README.md                      # This file
```

## Screenshot Locations

After running tests, screenshots are saved to:
- `test-results/screenshots/` - Individual test screenshots
- `e2e-screenshots/` - Collected screenshots (created by run-e2e-tests.sh)
- `e2e-screenshots.zip` - Archive for easy sharing/CI artifacts

## Test Coverage

Current E2E tests cover:

### ✅ Pages/Components Tested

1. **Health Page**
   - Backend status display
   - Connection status
   - Error handling
   - Responsive design (desktop, tablet, mobile)

2. **API Documentation**
   - Swagger UI accessibility
   - OpenAPI spec validation

3. **Backend Endpoints**
   - Health check
   - API v1 endpoints
   - CORS configuration

### 🔄 Coming Soon

- Dashboard with live panels
- Time series panel data visualization
- KPI panel rendering
- Table panel with sorting/pagination
- Health status panel
- Tenant selection
- User authentication flow
- Admin interface

## Configuration

Configuration is in `playwright.config.ts`:

```typescript
{
  testDir: './tests/e2e/specs',
  screenshot: 'on',        // Always capture screenshots
  video: 'on',            // Always record video
  trace: 'on-first-retry' // Capture trace on retry
}
```

## CI Integration

GitHub Actions workflow (`.github/workflows/ci.yml`) automatically:
1. Runs all E2E tests on every push/PR
2. Captures screenshots
3. Creates screenshot archive
4. Uploads as build artifacts (retained for 30 days)

### Downloading Screenshots from CI

1. Go to Actions tab in GitHub
2. Click on the workflow run
3. Scroll to "Artifacts" section
4. Download `e2e-screenshots` archive

## Writing New Tests

Example test with screenshots:

```typescript
import { test, expect, Page } from '@playwright/test'

test('my feature test', async ({ page }) => {
  // Navigate to page
  await page.goto('/my-page')

  // Verify content
  await expect(page.locator('h1')).toContainText('My Page')

  // Capture screenshot
  await page.screenshot({
    path: 'test-results/screenshots/my-feature.png',
    fullPage: true
  })

  // Interact and verify
  await page.click('button')
  await expect(page.locator('.result')).toBeVisible()

  // Capture result
  await page.screenshot({
    path: 'test-results/screenshots/my-feature-result.png'
  })
})
```

## Debugging

### View test in headed mode
```bash
npx playwright test --headed
```

### Debug specific test
```bash
npx playwright test --debug dashboard-panels.spec.ts
```

### View trace
```bash
npx playwright show-trace test-results/trace.zip
```

## Best Practices

1. **Always wait for content**: Use `waitForSelector` or `waitForLoadState`
2. **Capture screenshots at key points**: After navigation, after actions, on errors
3. **Use data-testid attributes**: Makes selectors more reliable
4. **Test responsive designs**: Test multiple viewport sizes
5. **Handle loading states**: Wait for data to load before assertions
6. **Clean up**: Ensure tests don't leave side effects

## Troubleshooting

### "Target closed" errors
- Servers might have crashed
- Check server logs
- Ensure servers are healthy before running tests

### No screenshots captured
- Check that `test-results/screenshots/` directory exists
- Verify screenshot paths in tests
- Ensure tests are actually running

### Tests timeout
- Increase timeout in playwright.config.ts
- Check network conditions
- Verify servers are responding

## Resources

- [Playwright Documentation](https://playwright.dev)
- [Best Practices](https://playwright.dev/docs/best-practices)
- [GitHub Actions Integration](https://playwright.dev/docs/ci-intro)
