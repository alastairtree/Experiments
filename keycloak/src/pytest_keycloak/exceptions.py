"""Custom exceptions for pytest-keycloak-fixture."""

from typing import Optional


class KeycloakError(Exception):
    """Base exception for all Keycloak-related errors."""

    pass


class KeycloakDownloadError(KeycloakError):
    """Failed to download Keycloak."""

    pass


class JavaNotFoundError(KeycloakError):
    """Java not found or wrong version."""

    pass


class KeycloakStartError(KeycloakError):
    """Failed to start Keycloak server."""

    pass


class KeycloakTimeoutError(KeycloakError):
    """Keycloak did not become ready in time."""

    pass


class KeycloakAPIError(KeycloakError):
    """Error calling Keycloak API."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        """
        Initialize KeycloakAPIError.

        Args:
            message: Error message
            status_code: HTTP status code if applicable
        """
        super().__init__(message)
        self.status_code = status_code
