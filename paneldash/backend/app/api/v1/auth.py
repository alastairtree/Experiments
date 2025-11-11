"""Authentication endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, get_current_active_user
from app.database import get_central_db
from app.models.central import UserTenant
from app.schemas.user import UserMeResponse

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.get("/me", response_model=UserMeResponse)
async def get_current_user_info(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_central_db)],
) -> UserMeResponse:
    """
    Get current user information including accessible tenants.

    Returns:
        User information with list of accessible tenant IDs
    """
    # Get user's accessible tenants
    result = await db.execute(
        select(UserTenant.tenant_id).where(UserTenant.user_id == current_user.id)
    )
    tenant_ids = [row[0] for row in result.all()]

    return UserMeResponse(
        id=current_user.id,
        keycloak_id=current_user.keycloak_id,
        email=current_user.email,
        full_name=current_user.full_name,
        is_admin=current_user.is_admin,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
        accessible_tenant_ids=tenant_ids,
    )


@router.post("/logout")
async def logout(current_user: Annotated[CurrentUser, Depends(get_current_active_user)]) -> dict[str, str]:  # noqa: ARG001
    """
    Logout endpoint (client-side token removal).

    Note: This is primarily for client-side state management.
    The actual JWT token invalidation should be handled by Keycloak.

    Returns:
        Success message
    """
    return {"message": "Successfully logged out"}
