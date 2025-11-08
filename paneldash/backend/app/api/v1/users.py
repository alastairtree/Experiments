"""User management endpoints (admin only)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import AdminUser
from app.database import get_central_db
from app.models.central import User
from app.schemas.user import UserResponse, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=list[UserResponse])
async def list_users(
    admin_user: AdminUser,  # noqa: ARG001
    db: Annotated[AsyncSession, Depends(get_central_db)],
) -> list[UserResponse]:
    """
    List all users (admin only).

    Returns:
        List of all users
    """
    result = await db.execute(select(User))
    users = result.scalars().all()

    return [
        UserResponse(
            id=user.id,
            keycloak_id=user.keycloak_id,
            email=user.email,
            full_name=user.full_name,
            is_admin=user.is_admin,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
        for user in users
    ]


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    admin_user: AdminUser,  # noqa: ARG001
    db: Annotated[AsyncSession, Depends(get_central_db)],
) -> UserResponse:
    """
    Get user by ID (admin only).

    Args:
        user_id: User UUID

    Returns:
        User information

    Raises:
        HTTPException: If user not found
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    return UserResponse(
        id=user.id,
        keycloak_id=user.keycloak_id,
        email=user.email,
        full_name=user.full_name,
        is_admin=user.is_admin,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    user_data: UserUpdate,
    admin_user: AdminUser,  # noqa: ARG001
    db: Annotated[AsyncSession, Depends(get_central_db)],
) -> UserResponse:
    """
    Update user information (admin only).

    Args:
        user_id: User UUID
        user_data: User update data

    Returns:
        Updated user

    Raises:
        HTTPException: If user not found
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Update fields if provided
    if user_data.email is not None:
        user.email = user_data.email
    if user_data.full_name is not None:
        user.full_name = user_data.full_name
    if user_data.is_admin is not None:
        user.is_admin = user_data.is_admin

    await db.commit()
    await db.refresh(user)

    return UserResponse(
        id=user.id,
        keycloak_id=user.keycloak_id,
        email=user.email,
        full_name=user.full_name,
        is_admin=user.is_admin,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    admin_user: AdminUser,  # noqa: ARG001
    db: Annotated[AsyncSession, Depends(get_central_db)],
) -> None:
    """
    Delete a user (admin only).

    Args:
        user_id: User UUID

    Raises:
        HTTPException: If user not found
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    await db.delete(user)
    await db.commit()
