# Hello World CLI

A Python CLI web server that displays a Hello World page, lets users enter their name, and prints a personalised greeting. Includes a full [Playwright](https://playwright.dev/python/) test suite with screenshots.

## Requirements

- [uv](https://docs.astral.sh/uv/) – Python package manager
- [ty](https://github.com/astral-sh/ty) – type checker (installed as a dev dependency)

## Project structure

```
playwrite/
├── src/hello_world/
│   └── server.py        # Flask web server + Click CLI
├── tests/
│   ├── conftest.py      # Fixtures: live server, browser config
│   └── test_hello_world.py
├── screenshots/         # Auto-generated test screenshots
├── config.toml          # Browser settings (headless / desktop)
├── pyproject.toml       # Project metadata and dependencies
└── README.md
```

## Running the CLI server

```bash
# Install dependencies
uv sync

# Start the server (default: http://127.0.0.1:5000)
uv run hello-world

# Custom host / port
uv run hello-world --host 0.0.0.0 --port 8080

# Enable Flask debug mode
uv run hello-world --debug
```

Open the printed URL in your browser to see the Hello World page. Enter a name and click **Submit** to receive a personalised greeting.

## Running the Playwright tests

```bash
# Install dependencies (first time)
uv sync
uv run playwright install chromium

# Run all tests (headless, default)
uv run pytest -v

# Run a specific test class
uv run pytest -v tests/test_hello_world.py::TestNameSubmission

# Run a single test
uv run pytest -v -k test_greet_page_shows_name
```

Screenshots are saved to `screenshots/` automatically after each test.

## Browser configuration

Edit `config.toml` to control browser behaviour:

```toml
[browser]
headless = true          # false = open a visible browser window (desktop mode)
browser_type = "chromium"  # chromium | firefox | webkit
```

| Setting | Value | Effect |
|---------|-------|--------|
| `headless` | `true` *(default)* | Run in headless mode (no visible window) |
| `headless` | `false` | Open a real browser window (desktop mode) |
| `browser_type` | `"chromium"` | Use Chromium (default) |
| `browser_type` | `"firefox"` | Use Firefox |
| `browser_type` | `"webkit"` | Use WebKit/Safari |

## Type checking with ty

```bash
uv run ty check src/
```

## CI / GitHub Actions

The workflow at `.github/workflows/playwright-tests.yml` automatically:

1. Installs Python 3.11 and `uv`
2. Installs project dependencies
3. Installs the Chromium browser
4. Runs the full Playwright test suite
5. Uploads screenshots as build artifacts (retained 30 days)
6. Writes a test summary to the GitHub Actions job summary page

The workflow triggers on any push or pull request that touches the `playwrite/` folder.
