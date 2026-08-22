import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import func, select, update

from ...audit import record_audit
from ...deps import Admin, Db
from ...models import Role, Session, User
from ...schemas import UserCreate, UserOut, UserUpdate
from ...security import hash_password


router = APIRouter(prefix="/users", tags=["Users and roles"])


@router.get("", response_model=list[UserOut])
async def list_users(_: Admin, db: Db, offset: int = 0, limit: int = 50):
    return (
        await db.execute(select(User).order_by(User.username).offset(max(offset, 0)).limit(min(limit, 100)))
    ).scalars().all()


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate, request: Request, admin: Admin, db: Db):
    if (await db.execute(select(User.id).where(User.username == payload.username))).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Username already exists")
    user = User(username=payload.username, password_hash=hash_password(payload.password.get_secret_value()), role=payload.role)
    db.add(user)
    await record_audit(db, request, "user.create", "success", user=admin, target=payload.username, details={"role": payload.role})
    await db.commit()
    await db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(user_id: uuid.UUID, payload: UserUpdate, request: Request, admin: Admin, db: Db):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id and payload.is_active is False:
        raise HTTPException(status_code=409, detail="You cannot deactivate your current account")
    if user.role == Role.admin and payload.role not in {None, Role.admin}:
        admin_count = (
            await db.execute(select(func.count()).select_from(User).where(User.role == Role.admin, User.is_active.is_(True)))
        ).scalar_one()
        if admin_count <= 1:
            raise HTTPException(status_code=409, detail="At least one active administrator is required")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, key, value)
    if payload.is_active is False:
        await db.execute(update(Session).where(Session.user_id == user.id).values(revoked_at=datetime.now(UTC)))
    await record_audit(db, request, "user.update", "success", user=admin, target=user.username, details=payload.model_dump(exclude_unset=True, mode="json"))
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/roles")
async def roles(_: Admin):
    return [{"name": role.value} for role in Role]
