import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from redis.asyncio import Redis
from sqlalchemy import select, update

from ...audit import record_audit
from ...config import get_settings
from ...deps import CurrentUser, Db, csrf_protected_session, current_session
from ...models import Session, User
from ...schemas import LoginRequest, LoginResponse, PasswordChange, SessionOut, UserOut
from ...security import hash_password, random_token, token_hash, verify_password


router = APIRouter(prefix="/auth", tags=["Authentication"])
DUMMY_PASSWORD_HASH = hash_password(random_token())


def _client_ip(request: Request) -> str:
    return request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (
        request.client.host if request.client else "unknown"
    )


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, request: Request, response: Response, db: Db):
    settings = get_settings()
    ip = _client_ip(request)
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    rate_key = f"login:{ip}"
    try:
        attempts = await redis.incr(rate_key)
        if attempts == 1:
            await redis.expire(rate_key, 60)
        if attempts > settings.login_max_attempts:
            raise HTTPException(status_code=429, detail="Too many login attempts; try again later")
    finally:
        await redis.aclose()

    user = (
        await db.execute(select(User).where(User.username == payload.username))
    ).scalar_one_or_none()
    now = datetime.now(UTC)
    if user and user.locked_until and user.locked_until > now:
        await record_audit(db, request, "auth.login", "locked", user=user)
        await db.commit()
        raise HTTPException(status_code=423, detail="Account is temporarily locked")
    password_valid = verify_password(
        user.password_hash if user else DUMMY_PASSWORD_HASH,
        payload.password.get_secret_value(),
    )
    if not user or not user.is_active or not password_valid:
        if user:
            user.failed_login_count += 1
            if user.failed_login_count >= settings.login_max_attempts:
                user.locked_until = now + timedelta(minutes=settings.lockout_minutes)
                user.failed_login_count = 0
        await record_audit(db, request, "auth.login", "denied", user=user, details={"username": payload.username})
        await db.commit()
        raise HTTPException(status_code=401, detail="Invalid username or password")

    user.failed_login_count = 0
    user.locked_until = None
    session_token = random_token()
    csrf_token = random_token()
    session = Session(
        user_id=user.id,
        token_hash=token_hash(session_token),
        csrf_hash=token_hash(csrf_token),
        expires_at=now + timedelta(minutes=settings.session_ttl_minutes),
        ip_address=ip,
        user_agent=request.headers.get("user-agent", "")[:512],
    )
    db.add(session)
    await record_audit(db, request, "auth.login", "success", user=user)
    await db.commit()
    response.set_cookie(
        settings.cookie_name,
        session_token,
        max_age=settings.session_ttl_minutes * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/",
    )
    return LoginResponse(user=UserOut.model_validate(user), csrf_token=csrf_token)


@router.post("/csrf")
async def rotate_csrf(
    session: Annotated[Session, Depends(current_session)], db: Db
):
    csrf_token = random_token()
    session.csrf_hash = token_hash(csrf_token)
    await db.commit()
    return {"csrf_token": csrf_token}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    db: Db,
    session: Annotated[Session, Depends(csrf_protected_session)],
):
    session.revoked_at = datetime.now(UTC)
    await record_audit(db, request, "auth.logout", "success", user=session.user)
    await db.commit()
    response.delete_cookie(get_settings().cookie_name, path="/")


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser):
    return user


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: PasswordChange,
    request: Request,
    db: Db,
    session: Annotated[Session, Depends(csrf_protected_session)],
):
    user = session.user
    if not verify_password(user.password_hash, payload.current_password.get_secret_value()):
        await record_audit(db, request, "auth.password_change", "denied", user=user)
        await db.commit()
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    changed_at = datetime.now(UTC)
    user.password_hash = hash_password(payload.new_password.get_secret_value())
    user.password_changed_at = changed_at
    session.created_at = changed_at
    await db.execute(
        update(Session)
        .where(Session.user_id == user.id, Session.id != session.id)
        .values(revoked_at=datetime.now(UTC))
    )
    await record_audit(db, request, "auth.password_change", "success", user=user)
    await db.commit()


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(user: CurrentUser, db: Db):
    return (
        await db.execute(select(Session).where(Session.user_id == user.id).order_by(Session.created_at.desc()))
    ).scalars().all()


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_session(
    session_id: uuid.UUID,
    request: Request,
    db: Db,
    current: Annotated[Session, Depends(csrf_protected_session)],
):
    target = (
        await db.execute(select(Session).where(Session.id == session_id, Session.user_id == current.user_id))
    ).scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Session not found")
    target.revoked_at = datetime.now(UTC)
    await record_audit(db, request, "auth.session_revoke", "success", user=current.user, target=str(session_id))
    await db.commit()
