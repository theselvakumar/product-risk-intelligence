import uuid
from typing import AsyncGenerator, Callable, List, Optional
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.roles import UserRole, ROLE_HIERARCHY
from app.core.security import decode_access_token
from app.database.session import get_db
from app.models.user import User

security_scheme = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Validate bearer JWT token and resolve active authority user from database."""
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate authority credentials or token has expired",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(token)
        user_id_str: Optional[str] = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
        user_id = uuid.UUID(user_id_str)
    except (jwt.PyJWTError, ValueError):
        raise credentials_exception

    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authority officer record not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authority officer account is deactivated",
        )

    return user


def require_role(*allowed_roles: str) -> Callable[[User], User]:
    """Dependency factory enforcing Role-Based Access Control (RBAC)."""
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        user_role = current_user.role
        # Check direct role match or hierarchical inheritance
        has_access = False
        for allowed in allowed_roles:
            if user_role == allowed:
                has_access = True
                break
            # Check hierarchy if defined
            try:
                role_enum = UserRole(user_role)
                if UserRole(allowed) in ROLE_HIERARCHY.get(role_enum, []):
                    has_access = True
                    break
            except ValueError:
                pass

        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: requires one of roles {[str(r) for r in allowed_roles]}",
            )
        return current_user

    return role_checker


# Convenient role-specific dependencies
require_authority_officer = require_role(UserRole.AUTHORITY_OFFICER, UserRole.SUPERVISOR, UserRole.ADMIN)
require_admin = require_role(UserRole.ADMIN)
