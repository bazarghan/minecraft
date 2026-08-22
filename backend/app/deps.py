from datetime import UTC, datetime
from typing import Annotated

from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .config import get_settings
from .database import get_db
from .models import Role, Session, User
from .security import constant_time_equal_hash, token_hash


Db = Annotated[AsyncSession, Depends(get_db)]


async def current_session(
    request: Request,
    db: Db,
    session_cookie: Annotated[str | None, Cookie(alias=get_settings().cookie_name)] = None,
) -> Session:
    if not session_cookie:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    result = await db.execute(
        select(Session)
        .options(selectinload(Session.user))
        .where(Session.token_hash == token_hash(session_cookie))
    )
    session = result.scalar_one_or_none()
    now = datetime.now(UTC)
    if (
        not session
        or session.revoked_at is not None
        or session.expires_at <= now
        or not session.user.is_active
        or session.created_at < session.user.password_changed_at
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session is invalid")
    request.state.user = session.user
    return session


async def csrf_protected_session(
    session: Annotated[Session, Depends(current_session)],
    csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> Session:
    if not csrf_token or not constant_time_equal_hash(csrf_token, session.csrf_hash):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token")
    return session


async def current_user(session: Annotated[Session, Depends(current_session)]) -> User:
    return session.user


def require_roles(*roles: Role):
    async def dependency(
        session: Annotated[Session, Depends(csrf_protected_session)],
    ) -> User:
        if session.user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return session.user

    return dependency


CurrentUser = Annotated[User, Depends(current_user)]
Admin = Annotated[User, Depends(require_roles(Role.admin))]
Operator = Annotated[User, Depends(require_roles(Role.admin, Role.operator))]
ViewerWrite = Annotated[User, Depends(require_roles(Role.admin, Role.operator, Role.viewer))]
