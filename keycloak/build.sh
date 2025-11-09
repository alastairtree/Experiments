#!/bin/bash

# Exit on error, undefined variables, and pipe failures
set -euo pipefail

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored messages
print_step() {
    echo -e "${GREEN}==>${NC} $1"
}

print_error() {
    echo -e "${RED}ERROR:${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}WARNING:${NC} $1"
}

# Track overall success
BUILD_SUCCESS=true

# Parse command line arguments
CLEAN_BUILD=false
SKIP_TESTS=false
for arg in "$@"; do
    case "$arg" in
        --clean)
            CLEAN_BUILD=true
            print_warning "Clean build requested - will recreate virtual environment"
            ;;
        --skip-tests)
            SKIP_TESTS=true
            print_warning "Skipping tests"
            ;;
        *)
            print_error "Unknown option: $arg"
            echo "Usage: $0 [--clean] [--skip-tests]"
            exit 1
            ;;
    esac
done

# Cleanup function
cleanup_on_error() {
    if [ "$BUILD_SUCCESS" = false ]; then
        print_error "Build failed. See errors above."
        exit 1
    fi
}

trap cleanup_on_error EXIT

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

print_step "Starting build process..."

# Step 1: Check and install Java 17+ if needed
print_step "Checking for Java 17+..."
if ! java -version 2>&1 | grep -qE "(openjdk|java) version \"(1[7-9]|[2-9][0-9])"; then
    print_warning "Java 17+ not found. Installing OpenJDK 17..."

    # Check if running with sudo privileges
    if ! sudo -n true 2>/dev/null; then
        print_error "Java 17+ is required but not installed. Please run one of the following:"
        echo "  1. Install Java manually: sudo apt-get update && sudo apt-get install -y openjdk-17-jdk"
        echo "  2. Run this script with sudo access"
        BUILD_SUCCESS=false
        exit 1
    fi

    # Install Java
    sudo apt-get update -qq || {
        print_error "Failed to update package list"
        BUILD_SUCCESS=false
        exit 1
    }

    sudo apt-get install -y openjdk-17-jdk || {
        print_error "Failed to install Java 17"
        BUILD_SUCCESS=false
        exit 1
    }

    print_step "Java 17 installed successfully"
else
    JAVA_VERSION=$(java -version 2>&1 | head -n 1)
    print_step "Java already installed: $JAVA_VERSION"
fi

# Step 2: Create or use existing virtual environment
if [ "$CLEAN_BUILD" = true ]; then
    if [ -d ".venv" ]; then
        print_step "Removing existing virtual environment..."
        rm -rf .venv
    fi
    print_step "Creating fresh virtual environment..."
    python3 -m venv .venv || {
        print_error "Failed to create virtual environment"
        BUILD_SUCCESS=false
        exit 1
    }
elif [ -d ".venv" ]; then
    print_step "Using existing virtual environment..."
else
    print_step "Creating virtual environment..."
    python3 -m venv .venv || {
        print_error "Failed to create virtual environment"
        BUILD_SUCCESS=false
        exit 1
    }
fi

print_step "Activating virtual environment..."
source .venv/bin/activate || {
    print_error "Failed to activate virtual environment"
    BUILD_SUCCESS=false
    exit 1
}

# Verify we're in the venv
if [ -z "${VIRTUAL_ENV:-}" ]; then
    print_error "Virtual environment activation failed"
    BUILD_SUCCESS=false
    exit 1
fi

print_step "Virtual environment activated at: $VIRTUAL_ENV"

# Step 3: Upgrade pip and install build tools
print_step "Upgrading pip and installing build tools..."
pip install --upgrade pip setuptools wheel build || {
    print_error "Failed to upgrade pip and install build tools"
    BUILD_SUCCESS=false
    exit 1
}

# Step 4: Install project dependencies (including dev dependencies)
print_step "Installing project dependencies..."
pip install -e ".[dev]" || {
    print_error "Failed to install project dependencies"
    BUILD_SUCCESS=false
    exit 1
}

# Step 5: Run ruff linting and auto-fix issues
print_step "Running ruff linting and fixing issues..."
if ! ruff check --fix src/ tests/; then
    print_warning "Ruff found issues that couldn't be auto-fixed"
    print_step "Attempting to continue after manual fixes..."

    # Try again without --fix to see if issues remain
    if ! ruff check src/ tests/; then
        print_error "Ruff linting failed with unfixable issues"
        BUILD_SUCCESS=false
        exit 1
    fi
fi

print_step "Running ruff formatting..."
ruff format src/ tests/ || {
    print_error "Ruff formatting failed"
    BUILD_SUCCESS=false
    exit 1
}

# Step 6: Run tests
if [ "$SKIP_TESTS" = false ]; then
    print_step "Running tests..."
    if ! pytest tests/ -v; then
        print_error "Tests failed"
        BUILD_SUCCESS=false
        exit 1
    fi
else
    print_step "Skipping tests (--skip-tests flag provided)"
fi

# Step 7: Build wheel package
print_step "Building wheel package..."
if [ -d "dist" ]; then
    print_warning "Cleaning old dist directory..."
    rm -rf dist
fi

python -m build --wheel || {
    print_error "Failed to build wheel package"
    BUILD_SUCCESS=false
    exit 1
}

# Verify wheel was created
if [ ! -d "dist" ] || [ -z "$(ls -A dist/*.whl 2>/dev/null)" ]; then
    print_error "Wheel file was not created"
    BUILD_SUCCESS=false
    exit 1
fi

# Step 8: Final success message
echo ""
echo "========================================"
echo -e "${GREEN}BUILD SUCCESS${NC}"
echo "========================================"
echo ""
echo "Virtual environment: $VIRTUAL_ENV"
echo "Wheel package(s) created:"
ls -lh dist/*.whl
echo ""
echo "To install the package:"
echo "  pip install dist/$(ls dist/*.whl | head -n1 | xargs basename)"
echo ""
