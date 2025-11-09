"""Keycloak Admin REST API client."""

import logging
from typing import Any, Dict, Optional

import requests

from .exceptions import KeycloakAPIError

logger = logging.getLogger(__name__)


class KeycloakClient:
    """
    Client for interacting with Keycloak Admin REST API.

    Used for runtime user/realm management during tests.
    """

    def __init__(
        self,
        base_url: str,
        admin_user: str,
        admin_password: str,
        realm: str = "master",
    ):
        """
        Initialize KeycloakClient.

        Args:
            base_url: Keycloak base URL (e.g., http://localhost:8080)
            admin_user: Admin username
            admin_password: Admin password
            realm: Realm to operate in
        """
        self.base_url = base_url.rstrip("/")
        self.admin_user = admin_user
        self.admin_password = admin_password
        self.realm = realm
        self._token: Optional[str] = None

    def get_admin_token(self) -> str:
        """
        Get admin access token.

        POST {base_url}/realms/master/protocol/openid-connect/token
        with grant_type=password, client_id=admin-cli

        Returns:
            Access token string

        Raises:
            KeycloakAPIError: If token request fails
        """
        url = f"{self.base_url}/realms/master/protocol/openid-connect/token"

        data = {
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": self.admin_user,
            "password": self.admin_password,
        }

        try:
            response = requests.post(url, data=data, timeout=30)
            response.raise_for_status()

            token_data = response.json()
            self._token = token_data["access_token"]
            return self._token

        except requests.RequestException as e:
            raise KeycloakAPIError(
                f"Failed to get admin token: {e}",
                status_code=getattr(e.response, "status_code", None)
                if hasattr(e, "response")
                else None,
            )

    def _get_headers(self) -> Dict[str, str]:
        """
        Get headers with authorization token.

        Returns:
            Headers dictionary with Authorization
        """
        if not self._token:
            self.get_admin_token()

        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    def create_user(
        self,
        username: str,
        password: str,
        email: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        enabled: bool = True,
        realm: Optional[str] = None,
    ) -> str:
        """
        Create a user in the specified realm.

        POST {base_url}/admin/realms/{realm}/users

        Args:
            username: Username
            password: Password
            email: Email address
            first_name: First name
            last_name: Last name
            enabled: Whether user is enabled
            realm: Realm name (defaults to self.realm)

        Returns:
            User ID

        Raises:
            KeycloakAPIError: If creation fails
        """
        target_realm = realm or self.realm
        url = f"{self.base_url}/admin/realms/{target_realm}/users"

        # Note: Keycloak requires email, firstName, and lastName to be set for accounts
        # created via API to avoid "Account is not fully set up" errors during password grant.
        # Provide defaults if not specified.
        user_data: Dict[str, Any] = {
            "username": username,
            "enabled": enabled,
            "email": email or f"{username}@example.com",
            "emailVerified": True,
            "firstName": first_name or "Test",
            "lastName": last_name or "User",
            "requiredActions": [],
        }

        try:
            response = requests.post(
                url,
                json=user_data,
                headers=self._get_headers(),
                timeout=30,
            )

            # Handle 409 Conflict (user already exists)
            if response.status_code == 409:
                raise KeycloakAPIError(
                    f"User '{username}' already exists",
                    status_code=409,
                )

            response.raise_for_status()

            # Extract user ID from Location header
            location = response.headers.get("Location", "")
            user_id = location.split("/")[-1] if location else ""

            if not user_id:
                # Fallback: query to get user ID
                user_id = self._get_user_id_by_username(username, target_realm)

            # Set password via dedicated reset-password endpoint
            # This is more reliable than setting credentials during user creation
            password_url = f"{self.base_url}/admin/realms/{target_realm}/users/{user_id}/reset-password"
            password_data = {
                "type": "password",
                "value": password,
                "temporary": False,
            }
            try:
                pwd_resp = requests.put(
                    password_url,
                    json=password_data,
                    headers=self._get_headers(),
                    timeout=30
                )
                pwd_resp.raise_for_status()
                logger.info(f"Set password for user {user_id}")
            except requests.RequestException as e:
                # If password setting fails, delete the user and raise error
                try:
                    self.delete_user(user_id, target_realm)
                except Exception:
                    pass
                raise KeycloakAPIError(
                    f"Failed to set password for user '{username}': {e}",
                    status_code=getattr(e.response, "status_code", None)
                    if hasattr(e, "response")
                    else None,
                )

            # Assign default realm role to ensure user is fully set up
            # This prevents "Account is not fully set up" error during password grant
            self._assign_default_realm_roles(user_id, target_realm)

            logger.info(f"Created user '{username}' with ID: {user_id}")
            return user_id

        except KeycloakAPIError:
            raise
        except requests.RequestException as e:
            raise KeycloakAPIError(
                f"Failed to create user '{username}': {e}",
                status_code=getattr(e.response, "status_code", None)
                if hasattr(e, "response")
                else None,
            )

    def _assign_default_realm_roles(self, user_id: str, realm: str) -> None:
        """
        Assign default realm roles to a user.

        This ensures users have at least the default-roles assigned,
        which prevents "Account is not fully set up" errors.

        Args:
            user_id: User ID
            realm: Realm name
        """
        # Get the roles for the realm
        url = f"{self.base_url}/admin/realms/{realm}/roles"

        try:
            # Get all roles
            response = requests.get(
                url,
                headers=self._get_headers(),
                timeout=30,
            )
            response.raise_for_status()
            roles = response.json()

            # First try to assign the "user" role (commonly used basic role)
            user_role = next((r for r in roles if r["name"] == "user"), None)

            # If "user" role exists, assign it
            if user_role:
                assign_url = f"{self.base_url}/admin/realms/{realm}/users/{user_id}/role-mappings/realm"
                response = requests.post(
                    assign_url,
                    json=[user_role],
                    headers=self._get_headers(),
                    timeout=30,
                )
                response.raise_for_status()
                logger.info(f"Assigned 'user' realm role to user {user_id}")
            else:
                # Fallback: assign default-roles composite role
                default_role_name = f"default-roles-{realm}"
                default_role = next((r for r in roles if r["name"] == default_role_name), None)

                if default_role:
                    assign_url = f"{self.base_url}/admin/realms/{realm}/users/{user_id}/role-mappings/realm"
                    response = requests.post(
                        assign_url,
                        json=[default_role],
                        headers=self._get_headers(),
                        timeout=30,
                    )
                    response.raise_for_status()
                    logger.info(f"Assigned default-roles-{realm} to user {user_id}")
                else:
                    logger.warning(f"No 'user' or default realm roles found in realm {realm}")

        except requests.RequestException as e:
            # Don't fail user creation if role assignment fails
            logger.error(f"Failed to assign default roles to user {user_id}: {e}")

    def _get_user_id_by_username(self, username: str, realm: str) -> str:
        """
        Get user ID by username.

        Args:
            username: Username to search for
            realm: Realm name

        Returns:
            User ID

        Raises:
            KeycloakAPIError: If user not found
        """
        url = f"{self.base_url}/admin/realms/{realm}/users"
        params = {"username": username, "exact": "true"}

        try:
            response = requests.get(
                url,
                params=params,
                headers=self._get_headers(),
                timeout=30,
            )
            response.raise_for_status()

            users = response.json()
            if not users:
                raise KeycloakAPIError(f"User '{username}' not found")

            return users[0]["id"]

        except KeycloakAPIError:
            raise
        except requests.RequestException as e:
            raise KeycloakAPIError(
                f"Failed to get user ID for '{username}': {e}",
                status_code=getattr(e.response, "status_code", None)
                if hasattr(e, "response")
                else None,
            )

    def delete_user(self, user_id: str, realm: Optional[str] = None) -> None:
        """
        Delete a user.

        DELETE {base_url}/admin/realms/{realm}/users/{user_id}

        Args:
            user_id: User ID to delete
            realm: Realm name (defaults to self.realm)

        Raises:
            KeycloakAPIError: If deletion fails
        """
        target_realm = realm or self.realm
        url = f"{self.base_url}/admin/realms/{target_realm}/users/{user_id}"

        try:
            response = requests.delete(
                url,
                headers=self._get_headers(),
                timeout=30,
            )
            response.raise_for_status()

            logger.info(f"Deleted user with ID: {user_id}")

        except requests.RequestException as e:
            raise KeycloakAPIError(
                f"Failed to delete user '{user_id}': {e}",
                status_code=getattr(e.response, "status_code", None)
                if hasattr(e, "response")
                else None,
            )

    def get_user_token(
        self,
        username: str,
        password: str,
        client_id: str,
        realm: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get user access token using password grant.

        POST {base_url}/realms/{realm}/protocol/openid-connect/token

        Args:
            username: Username
            password: Password
            client_id: Client ID
            realm: Realm name (defaults to self.realm)

        Returns:
            Token response dict with access_token, refresh_token, etc.

        Raises:
            KeycloakAPIError: If token request fails
        """
        target_realm = realm or self.realm
        url = f"{self.base_url}/realms/{target_realm}/protocol/openid-connect/token"

        data = {
            "grant_type": "password",
            "client_id": client_id,
            "username": username,
            "password": password,
        }

        try:
            response = requests.post(url, data=data, timeout=30)
            response.raise_for_status()

            return response.json()

        except requests.RequestException as e:
            # Log the error response body for debugging
            error_detail = ""
            if hasattr(e, "response") and e.response is not None:
                try:
                    error_detail = f" - {e.response.text}"
                except Exception:
                    pass

            raise KeycloakAPIError(
                f"Failed to get user token for '{username}': {e}{error_detail}",
                status_code=getattr(e.response, "status_code", None)
                if hasattr(e, "response")
                else None,
            )

    def create_realm(self, realm_config: Dict[str, Any]) -> None:
        """
        Create a new realm.

        POST {base_url}/admin/realms

        Args:
            realm_config: Realm configuration dictionary

        Raises:
            KeycloakAPIError: If creation fails
        """
        url = f"{self.base_url}/admin/realms"

        try:
            response = requests.post(
                url,
                json=realm_config,
                headers=self._get_headers(),
                timeout=30,
            )

            # Handle 409 Conflict (realm already exists)
            if response.status_code == 409:
                raise KeycloakAPIError(
                    f"Realm '{realm_config.get('realm')}' already exists",
                    status_code=409,
                )

            response.raise_for_status()

            logger.info(f"Created realm: {realm_config.get('realm')}")

        except KeycloakAPIError:
            raise
        except requests.RequestException as e:
            raise KeycloakAPIError(
                f"Failed to create realm: {e}",
                status_code=getattr(e.response, "status_code", None)
                if hasattr(e, "response")
                else None,
            )

    def delete_realm(self, realm: str) -> None:
        """
        Delete a realm.

        DELETE {base_url}/admin/realms/{realm}

        Args:
            realm: Realm name to delete

        Raises:
            KeycloakAPIError: If deletion fails
        """
        url = f"{self.base_url}/admin/realms/{realm}"

        try:
            response = requests.delete(
                url,
                headers=self._get_headers(),
                timeout=30,
            )
            response.raise_for_status()

            logger.info(f"Deleted realm: {realm}")

        except requests.RequestException as e:
            raise KeycloakAPIError(
                f"Failed to delete realm '{realm}': {e}",
                status_code=getattr(e.response, "status_code", None)
                if hasattr(e, "response")
                else None,
            )
