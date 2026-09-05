from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.rate_limit import rate_limit
from app.core.security import create_access_token, verify_password
from app.database.session import get_db
from app.models.case import AuditLog
from app.models.user import User
from app.schemas.auth import CurrentUserResponse, LoginRequest, LogoutResponse, TokenResponse
from app.schemas.user import UserRead

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authority Officer Authentication",
    description="Authenticate an authority officer using government email and password, returning a secure JWT token.",
    dependencies=[Depends(rate_limit(max_requests=30, window_seconds=60))],
)
async def login(
    login_data: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    # Lookup user by email
    stmt = select(User).where(User.email == login_data.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    # Generic invalid credential check to avoid user enumeration
    if not user or not user.hashed_password or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid government email or security password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authority account is inactive or revoked. Contact system administrator.",
        )

    # Generate JWT Token
    token_claims = {
        "email": user.email,
        "role": user.role,
        "badge_id": user.badge_id,
        "state": user.jurisdiction_state,
        "district": user.jurisdiction_district,
    }
    access_token = create_access_token(subject=user.id, claims=token_claims)

    # Audit log login action
    client_ip = request.client.host if request.client else None
    audit_entry = AuditLog(
        user_id=user.id,
        action="USER_LOGIN",
        entity_type="User",
        entity_id=str(user.id),
        details_json={
            "email": user.email,
            "badge_id": user.badge_id,
            "role": user.role,
            "login_timestamp": datetime.now(timezone.utc).isoformat(),
        },
        ip_address=client_ip,
    )
    db.add(audit_entry)
    await db.commit()
    await db.refresh(user)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserRead.model_validate(user),
    )


@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="Authority Officer Logout",
    description="Terminates active session and records regulatory audit log entry.",
)
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Audit log logout action
    client_ip = request.client.host if request.client else None
    audit_entry = AuditLog(
        user_id=current_user.id,
        action="USER_LOGOUT",
        entity_type="User",
        entity_id=str(current_user.id),
        details_json={
            "email": current_user.email,
            "badge_id": current_user.badge_id,
            "logout_timestamp": datetime.now(timezone.utc).isoformat(),
        },
        ip_address=client_ip,
    )
    db.add(audit_entry)
    await db.commit()

    return LogoutResponse(
        status="success",
        message=f"Officer {current_user.full_name} ({current_user.badge_id}) logged out successfully",
    )


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    summary="Current Officer Profile",
    description="Retrieve verified credentials and jurisdiction for the currently authenticated officer.",
)
async def get_me(current_user: User = Depends(get_current_user)):
    return CurrentUserResponse(user=UserRead.model_validate(current_user))
