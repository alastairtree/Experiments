"""Configuration models for pytest-keycloak-fixture."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class UserConfig(BaseModel):
    """Configuration for a test user."""

    username: str
    password: str
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    enabled: bool = True
    realm_roles: List[str] = Field(default_factory=list)
    client_roles: Dict[str, List[str]] = Field(default_factory=dict)


class ClientConfig(BaseModel):
    """Configuration for an OIDC client."""

    client_id: str
    enabled: bool = True
    public_client: bool = True
    redirect_uris: List[str] = Field(default_factory=lambda: ["http://localhost:*"])
    web_origins: List[str] = Field(default_factory=lambda: ["http://localhost:*"])
    direct_access_grants_enabled: bool = True
    secret: Optional[str] = None


class RealmConfig(BaseModel):
    """Configuration for a Keycloak realm."""

    realm: str
    enabled: bool = True
    users: List[UserConfig] = Field(default_factory=list)
    clients: List[ClientConfig] = Field(default_factory=list)

    def to_keycloak_json(self) -> Dict[str, Any]:
        """
        Convert to Keycloak realm import JSON format.

        Should produce the JSON structure that Keycloak expects
        for realm import (--import-realm flag).

        Returns:
            Dictionary in Keycloak realm import format
        """
        realm_data: Dict[str, Any] = {
            "realm": self.realm,
            "enabled": self.enabled,
            "verifyEmail": False,  # Disable email verification requirement
            "registrationEmailAsUsername": False,
            "users": [],
            "clients": [],
            "roles": {
                "realm": [
                    {"name": "user", "description": "User role"},
                    {"name": "admin", "description": "Admin role"},
                ]
            },
        }

        # Convert users
        for user in self.users:
            user_data: Dict[str, Any] = {
                "username": user.username,
                "enabled": user.enabled,
                "credentials": [
                    {
                        "type": "password",
                        "value": user.password,
                        "temporary": False,
                    }
                ],
            }

            if user.email:
                user_data["email"] = user.email
                user_data["emailVerified"] = True

            if user.first_name:
                user_data["firstName"] = user.first_name

            if user.last_name:
                user_data["lastName"] = user.last_name

            if user.realm_roles:
                user_data["realmRoles"] = user.realm_roles

            if user.client_roles:
                user_data["clientRoles"] = user.client_roles

            realm_data["users"].append(user_data)

        # Convert clients
        for client in self.clients:
            client_data: Dict[str, Any] = {
                "clientId": client.client_id,
                "enabled": client.enabled,
                "publicClient": client.public_client,
                "redirectUris": client.redirect_uris,
                "webOrigins": client.web_origins,
                "directAccessGrantsEnabled": client.direct_access_grants_enabled,
                "standardFlowEnabled": True,
                "implicitFlowEnabled": False,
                "serviceAccountsEnabled": not client.public_client,
            }

            if client.secret and not client.public_client:
                client_data["secret"] = client.secret

            realm_data["clients"].append(client_data)

        return realm_data


class KeycloakConfig(BaseModel):
    """Overall configuration for Keycloak test instance."""

    version: str = "26.0.7"
    port: int = 8080
    admin_user: str = "admin"
    admin_password: str = "admin"
    install_dir: Optional[Path] = None
    realm: Optional[RealmConfig] = None
    auto_cleanup: bool = True
