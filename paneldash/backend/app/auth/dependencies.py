"""FastAPI dependencies for authentication and authorization."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.keycloak import keycloak_auth
from app.database import get_central_db
from app.models.central import User

# Security scheme for bearer token
security = HTTPBearer()


async def get_current_user_from_token(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_central_db)],
) -> User:
    """
    Get the current user from the JWT token.

    Args:
        credentials: HTTP bearer token credentials
        db: Database session

    Returns:
        User object

    Raises:
        HTTPException: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Verify token with Keycloak
        token_payload = await keycloak_auth.verify_token(credentials.credentials)
        user_info = keycloak_auth.extract_user_info(token_payload)

        keycloak_id = user_info.get("keycloak_id")
        if not keycloak_id:
            raise credentials_exception

        # Find or create user in our database
        result = await db.execute(
            select(User).where(User.keycloak_id == keycloak_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            # Auto-create user on first login
            email = str(user_info.get("email", ""))
            full_name_obj = user_info.get("full_name")
            full_name = str(full_name_obj) if full_name_obj else None
            realm_roles = user_info.get("realm_roles", [])
            is_admin = "admin" in realm_roles if isinstance(realm_roles, list) else False

            user = User(
                keycloak_id=keycloak_id,
                email=email,
                full_name=full_name,
                is_admin=is_admin,
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)

        return user

    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication credentials: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user_from_token)],
) -> User:
    """
    Get the current active user.

    Args:
        current_user: Current user from token

    Returns:
        User object

    Raises:
        HTTPException: If user is inactive
    """
    # For now, all users are considered active
    # You can add an is_active field later if needed
    return current_user


async def get_current_admin_user(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    """
    Get the current user and verify they are an admin.

    Args:
        current_user: Current active user

    Returns:
        User object if they are an admin

    Raises:
        HTTPException: If user is not an admin
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions. Admin access required.",
        )
    return current_user


# Type aliases for cleaner endpoint signatures
CurrentUser = Annotated[User, Depends(get_current_active_user)]
AdminUser = Annotated[User, Depends(get_current_admin_user)]
