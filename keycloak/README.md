# pytest-keycloak-fixture

A pytest fixture for running a local Keycloak server for integration testing. No Docker or sudo permissions required - just Java 17+.

## Features

- **Easy Integration**: Simple pytest fixtures for Keycloak testing
- **No Docker Required**: Downloads and runs Keycloak directly using Java
- **Session Scoped**: Start Keycloak once per test session for faster tests
- **Realm Configuration**: Pre-configure realms, users, and clients
- **Admin API Client**: Built-in client for runtime user/realm management
- **Automatic Cleanup**: Manages process lifecycle and cleanup
- **Type Safe**: Full type hints and Pydantic validation

## Requirements

- Python >= 3.9
- Java >= 17 (required to run Keycloak)
- pytest >= 7.0

### Check Java Version

```bash
java -version
```

You should see Java 17 or higher. If not, install from:
- [OpenJDK](https://openjdk.org/)
- [Adoptium](https://adoptium.net/)
- [Oracle JDK](https://www.oracle.com/java/technologies/downloads/)

## Installation

```bash
# wiremock dependency on java
sudo apt update -y && sudo apt install -y default-jdk

# TODO: publish release
pip install pytest-keycloak-fixture
```

For development:

```bash
pip install pytest-keycloak-fixture[dev]
```

## Quick Start

### Basic Usage

```python
# test_auth.py
def test_keycloak_is_running(keycloak):
    """Test that Keycloak is running and accessible."""
    assert keycloak.is_running()
    assert keycloak.get_base_url() == "http://localhost:8080"
```

### Custom Configuration

Create a `conftest.py` in your test directory:

```python
# conftest.py
import pytest
from pytest_keycloak import KeycloakConfig, RealmConfig, UserConfig, ClientConfig


@pytest.fixture(scope="session")
def keycloak_config():
    """Configure Keycloak for your tests."""
    return KeycloakConfig(
        port=8080,
        realm=RealmConfig(
            realm="my-test-realm",
            users=[
                UserConfig(
                    username="alice",
                    password="alice123",
                    email="alice@example.com",
                    realm_roles=["user"]
                ),
                UserConfig(
                    username="bob",
                    password="bob456",
                    email="bob@example.com",
                    realm_roles=["user", "admin"]
                ),
            ],
            clients=[
                ClientConfig(
                    client_id="my-app",
                    redirect_uris=["http://localhost:3000/*"],
                    web_origins=["http://localhost:3000"]
                )
            ],
        ),
    )
```

### Testing Authentication

```python
# test_auth.py
def test_user_can_login(keycloak_client):
    """Test that a pre-configured user can get a token."""
    token_response = keycloak_client.get_user_token(
        username="alice",
        password="alice123",
        client_id="my-app"
    )

    assert "access_token" in token_response
    assert token_response["token_type"] == "Bearer"


def test_create_temporary_user(keycloak_user, keycloak_client):
    """Test creating a temporary user for a single test."""
    # Create a user just for this test
    user_id = keycloak_user(username="temp_user", password="temp_pass")

    # Verify we can get a token
    token_response = keycloak_client.get_user_token(
        username="temp_user",
        password="temp_pass",
        client_id="my-app"
    )

    assert "access_token" in token_response
    # User automatically cleaned up after test
```

## Available Fixtures

### `keycloak_config`

Session-scoped fixture that provides Keycloak configuration. Override this in your `conftest.py` to customize.

**Default Configuration:**
- Version: 26.0.7
- Port: 8080
- Admin user: admin
- Admin password: admin
- Test realm with 2 users and 1 client

### `keycloak`

Session-scoped fixture that provides a running Keycloak instance.

**Returns:** `KeycloakManager`

**Methods:**
- `get_base_url()` - Get Keycloak base URL
- `is_running()` - Check if server is running
- `wait_for_ready(timeout)` - Wait for server to be ready
- `stop()` - Stop the server

**Example:**

```python
def test_with_keycloak(keycloak):
    base_url = keycloak.get_base_url()
    # Configure your app to use base_url
    assert keycloak.is_running()
```

### `keycloak_client`

Session-scoped fixture providing a client for Keycloak Admin REST API.

**Returns:** `KeycloakClient`

**Methods:**
- `create_user(username, password, **kwargs)` - Create a user
- `delete_user(user_id)` - Delete a user
- `get_user_token(username, password, client_id)` - Get user token
- `create_realm(realm_config)` - Create a realm
- `delete_realm(realm)` - Delete a realm

**Example:**

```python
def test_user_management(keycloak_client):
    # Create a user
    user_id = keycloak_client.create_user(
        username="newuser",
        password="newpass",
        email="newuser@example.com"
    )

    # Get token for the user
    token = keycloak_client.get_user_token(
        username="newuser",
        password="newpass",
        client_id="my-app"
    )

    # Clean up
    keycloak_client.delete_user(user_id)
```

### `keycloak_user`

Function-scoped fixture for creating temporary users that are automatically cleaned up.

**Returns:** Callable that creates users

**Example:**

```python
def test_with_temp_user(keycloak_user, keycloak_client):
    # Create user (auto-cleanup after test)
    user_id = keycloak_user(
        username="tempuser",
        password="temppass",
        email="temp@example.com"
    )

    # Use the user in your test
    token = keycloak_client.get_user_token(
        username="tempuser",
        password="temppass",
        client_id="my-app"
    )

    assert token["access_token"]
    # User automatically deleted when test completes
```

## Configuration Reference

### KeycloakConfig

Main configuration class.

```python
KeycloakConfig(
    version="26.0.7",           # Keycloak version to download
    port=8080,                  # HTTP port
    admin_user="admin",         # Admin username
    admin_password="admin",     # Admin password
    install_dir=None,           # Install location (default: ~/.keycloak-test)
    realm=None,                 # Realm configuration
    auto_cleanup=True           # Auto cleanup on exit
)
```

### RealmConfig

Realm configuration.

```python
RealmConfig(
    realm="test-realm",         # Realm name
    enabled=True,               # Realm enabled
    users=[...],                # List of UserConfig
    clients=[...]               # List of ClientConfig
)
```

### UserConfig

User configuration.

```python
UserConfig(
    username="testuser",        # Username (required)
    password="password",        # Password (required)
    email="user@example.com",   # Email address
    first_name="Test",          # First name
    last_name="User",           # Last name
    enabled=True,               # User enabled
    realm_roles=["user"],       # Realm roles
    client_roles={}             # Client roles dict
)
```

### ClientConfig

OIDC client configuration.

```python
ClientConfig(
    client_id="my-app",         # Client ID (required)
    enabled=True,               # Client enabled
    public_client=True,         # Public client (no secret)
    redirect_uris=["http://localhost:*"],
    web_origins=["http://localhost:*"],
    direct_access_grants_enabled=True,  # Password grant
    secret=None                 # Client secret (for confidential clients)
)
```

## Advanced Usage

### Multiple Realms

```python
def test_multiple_realms(keycloak_client):
    # Create additional realm
    realm_config = {
        "realm": "second-realm",
        "enabled": True
    }
    keycloak_client.create_realm(realm_config)

    # Create user in new realm
    user_id = keycloak_client.create_user(
        username="user2",
        password="pass2",
        realm="second-realm"
    )

    # Cleanup
    keycloak_client.delete_user(user_id, realm="second-realm")
    keycloak_client.delete_realm("second-realm")
```

### Custom Port

```python
@pytest.fixture(scope="session")
def keycloak_config():
    return KeycloakConfig(
        port=8081,  # Use different port
        realm=RealmConfig(realm="test-realm")
    )
```

### Skip Auto-Cleanup

```python
@pytest.fixture(scope="session")
def keycloak_config():
    return KeycloakConfig(
        auto_cleanup=False,  # Keep Keycloak running after tests
        realm=RealmConfig(realm="test-realm")
    )
```

### Custom Install Location

```python
from pathlib import Path

@pytest.fixture(scope="session")
def keycloak_config():
    return KeycloakConfig(
        install_dir=Path("/tmp/my-keycloak"),
        realm=RealmConfig(realm="test-realm")
    )
```

## API Reference

### KeycloakManager

Main class for managing Keycloak lifecycle.

#### Methods

**`__init__(version, install_dir, port, admin_user, admin_password)`**
Initialize the manager.

**`download_and_install()`**
Download and install Keycloak if not already present.

**`start(realm_config, wait_for_ready, timeout)`**
Start the Keycloak server.

**`stop(timeout)`**
Stop the Keycloak server gracefully.

**`is_running()`**
Check if Keycloak is running.

**`wait_for_ready(timeout)`**
Wait for Keycloak to be ready.

**`get_base_url()`**
Get the base URL (e.g., http://localhost:8080).

**`cleanup()`**
Clean up resources.

### KeycloakClient

Client for Keycloak Admin REST API.

#### Methods

**`get_admin_token()`**
Get admin access token.

**`create_user(username, password, email, first_name, last_name, enabled, realm)`**
Create a user in the realm.

**`delete_user(user_id, realm)`**
Delete a user.

**`get_user_token(username, password, client_id, realm)`**
Get user access token.

**`create_realm(realm_config)`**
Create a new realm.

**`delete_realm(realm)`**
Delete a realm.

## Troubleshooting

### Java Not Found

**Error:** `JavaNotFoundError: Java not found`

**Solution:** Install Java 17 or higher:
```bash
# Ubuntu/Debian
sudo apt-get install openjdk-17-jdk

# macOS (Homebrew)
brew install openjdk@17

# Windows
# Download from https://adoptium.net/
```

### Port Already in Use

**Error:** `KeycloakStartError: Failed to start`

**Solution:** Change the port in your config:
```python
@pytest.fixture(scope="session")
def keycloak_config():
    return KeycloakConfig(port=8081)  # Use different port
```

### Keycloak Not Ready

**Error:** `KeycloakTimeoutError: Keycloak did not become ready`

**Solution:**
1. Increase timeout:
   ```python
   manager.start(wait_for_ready=True, timeout=120)  # 2 minutes
   ```
2. Check logs at `~/.keycloak-test/logs/keycloak-{port}.log`

### Download Fails

**Error:** `KeycloakDownloadError: Failed to download`

**Solution:**
1. Check internet connection
2. Verify version exists: https://github.com/keycloak/keycloak/releases
3. Try a different version in config:
   ```python
   KeycloakConfig(version="25.0.6")
   ```

### Tests Are Slow

**Issue:** Tests take a long time to start

**Solution:** Keycloak is started once per session. If tests are still slow:
1. Use session-scoped fixtures where possible
2. Reuse `keycloak_client` instead of creating new clients
3. Pre-configure users in `keycloak_config` instead of creating them per test

## Development

### Setup Development Environment

```bash
# Clone repository
git clone https://github.com/yourusername/pytest-keycloak-fixture.git
cd pytest-keycloak-fixture/keycloak

# Install in development mode
pip install -e '.[dev]'

# Run tests
pytest tests/

# Format code
black src/ tests/

# Lint
ruff check src/ tests/

# Type check
mypy src/
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=pytest_keycloak --cov-report=html

# Run specific test file
pytest tests/test_manager.py

# Run with verbose output
pytest -v
```

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Changelog

### 0.1.0 (Initial Release)

- Initial release with core functionality
- KeycloakManager for lifecycle management
- KeycloakClient for Admin API
- Pytest fixtures for easy integration
- Pydantic-based configuration
- Automatic cleanup

## Links

- [Keycloak Documentation](https://www.keycloak.org/documentation)
- [Keycloak Admin REST API](https://www.keycloak.org/docs-api/latest/rest-api/)
- [pytest Documentation](https://docs.pytest.org/)

## Support

For issues and questions:
- GitHub Issues: https://github.com/yourusername/pytest-keycloak-fixture/issues
- Documentation: https://github.com/yourusername/pytest-keycloak-fixture/blob/main/README.md
