"""Keycloak integration for JWT token validation."""

import httpx
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError

from app.config import settings


class KeycloakAuth:
    """Keycloak authentication handler."""

    def __init__(self) -> None:
        """Initialize Keycloak authentication."""
        self.server_url = settings.keycloak_server_url
        self.realm = settings.keycloak_realm
        self.client_id = settings.keycloak_client_id
        self._public_key: str | None = None

    async def get_public_key(self) -> str:
        """Fetch the public key from Keycloak for JWT validation."""
        if self._public_key:
            return self._public_key

        certs_url = (
            f"{self.server_url}/realms/{self.realm}/protocol/openid-connect/certs"
        )

        async with httpx.AsyncClient() as client:
            response = await client.get(certs_url)
            response.raise_for_status()
            keys = response.json()

            # Get the first key (Keycloak typically uses RS256)
            if keys.get("keys"):
                # Convert JWK to PEM format
                from jose.backends import RSAKey

                jwk = keys["keys"][0]
                key = RSAKey(jwk, algorithm="RS256")  # type: ignore[misc]
                self._public_key = key.to_pem().decode("utf-8")
                return self._public_key

        raise ValueError("No public key found in Keycloak")

    async def verify_token(self, token: str) -> dict[str, object]:
        """
        Verify and decode a JWT token from Keycloak.

        Args:
            token: JWT token string

        Returns:
            Decoded token payload

        Raises:
            JWTError: If token is invalid or expired
        """
        try:
            public_key = await self.get_public_key()

            # Decode and verify the token
            payload: dict[str, object] = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                audience=self.client_id,
                options={"verify_aud": True, "verify_exp": True},
            )

            return payload

        except ExpiredSignatureError as exc:
            raise JWTError("Token has expired") from exc
        except JWTError as exc:
            raise JWTError(f"Invalid token: {exc}") from exc

    def extract_user_info(self, token_payload: dict[str, object]) -> dict[str, object]:
        """
        Extract user information from decoded token.

        Args:
            token_payload: Decoded JWT payload

        Returns:
            Dictionary with user information
        """
        # JWT payload access requires dynamic dict operations
        realm_access = token_payload.get("realm_access", {})
        roles = realm_access.get("roles", []) if isinstance(realm_access, dict) else []

        return {
            "keycloak_id": token_payload.get("sub"),
            "email": token_payload.get("email"),
            "full_name": token_payload.get("name"),
            "preferred_username": token_payload.get("preferred_username"),
            "email_verified": token_payload.get("email_verified", False),
            "realm_roles": roles,
        }


# Global instance
keycloak_auth = KeycloakAuth()
