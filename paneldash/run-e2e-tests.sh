#!/bin/bash

# Script to run E2E tests with screenshot capture
# This script starts the backend and frontend servers, runs the E2E tests, and collects screenshots

set -e

echo "🚀 Starting E2E Test Suite with Screenshot Capture"
echo "=================================================="

# Create screenshots directory
mkdir -p test-results/screenshots
mkdir -p e2e-screenshots

echo "📸 Screenshots will be saved to: e2e-screenshots/"

# Check if servers are already running
BACKEND_RUNNING=$(curl -s http://localhost:8001/health 2>/dev/null && echo "yes" || echo "no")
FRONTEND_RUNNING=$(curl -s http://localhost:5174 2>/dev/null && echo "yes" || echo "no")

if [ "$BACKEND_RUNNING" = "no" ]; then
  echo "⚠️  Backend server not running on port 8001"
  echo "   Please start it with: cd backend && uv run uvicorn app.main:app --port 8001"
  echo "   Or run: ./scripts/start-dev.sh"
fi

if [ "$FRONTEND_RUNNING" = "no" ]; then
  echo "⚠️  Frontend server not running on port 5174"
  echo "   Please start it with: cd frontend && npm run dev -- --port 5174"
fi

if [ "$BACKEND_RUNNING" = "no" ] || [ "$FRONTEND_RUNNING" = "no" ]; then
  echo ""
  echo "❌ Servers must be running to execute E2E tests"
  exit 1
fi

echo "✅ Backend is running on http://localhost:8001"
echo "✅ Frontend is running on http://localhost:5174"
echo ""

# Run E2E tests
echo "🧪 Running E2E tests..."
npx playwright test --reporter=html,list

# Collect screenshots
echo ""
echo "📸 Collecting screenshots..."

# Find and copy all screenshots from test results
find tests/e2e/test-results -name "*.png" -exec cp {} e2e-screenshots/ \; 2>/dev/null || true
find tests/e2e/playwright-report -name "*.png" -exec cp {} e2e-screenshots/ \; 2>/dev/null || true
find test-results -name "*.png" -exec cp {} e2e-screenshots/ \; 2>/dev/null || true
find playwright-report -name "*.png" -exec cp {} e2e-screenshots/ \; 2>/dev/null || true

# Count screenshots
SCREENSHOT_COUNT=$(ls -1 e2e-screenshots/*.png 2>/dev/null | wc -l)

echo "📊 Collected $SCREENSHOT_COUNT screenshots"

if [ "$SCREENSHOT_COUNT" -gt 0 ]; then
  echo ""
  echo "Screenshots saved:"
  ls -lh e2e-screenshots/*.png

  echo ""
  echo "Creating screenshot archive..."
  zip -r e2e-screenshots.zip e2e-screenshots/
  echo "✅ Archive created: e2e-screenshots.zip"

  echo ""
  echo "✅ E2E tests complete!"
  echo "📖 View the HTML report: npx playwright show-report"
else
  echo ""
  echo "❌ FAILURE: No screenshots were captured during E2E tests"
  echo "   Screenshots are required to verify browser-based testing"
  echo "   Check playwright.config.ts screenshot configuration"
  echo ""
  exit 1
fi
