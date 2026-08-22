import uuid

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from .models import AuditEvent, User


async def record_audit(
    db: AsyncSession,
    request: Request,
    action: str,
    result: str,
    user: User | None = None,
    target: str | None = None,
    details: dict | None = None,
) -> None:
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    ip = forwarded or (request.client.host if request.client else None)
    db.add(
        AuditEvent(
            user_id=user.id if user else None,
            username=user.username if user else None,
            action=action,
            target=target,
            ip_address=ip,
            result=result,
            details=details or {},
            request_id=getattr(request.state, "request_id", str(uuid.uuid4())),
        )
    )
