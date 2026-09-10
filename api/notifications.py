"""
In-app notification center API — read-only view of the notifications table.

Every user can read ONLY their own rows (personal data, keyed by user_id —
no school scoping applies). Read state is the `read_at` timestamp.
"""
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status
from pydantic import BaseModel
from sqlalchemy import select, func, update

from shared.database import get_db
from shared.errors import AuthenticationError
from shared.middleware.tenancy import validate_session
from shared.models import UserRole
from shared.platform_models import Notification
from shared.datetime_utils import utc_now

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["notifications"])


async def _current_user(request: Request, db: AsyncSession):
    user = await validate_session(request, db, touch=False)
    if user is None:
        raise AuthenticationError()
    return user


class NotificationResponse(BaseModel):
    id: UUID
    title: str
    body: str
    category: int
    channel: str
    status: str
    entity_type: Optional[str]
    entity_id: Optional[UUID]
    created_at: object
    read_at: Optional[object]


class NotificationListResponse(BaseModel):
    data: list[NotificationResponse]
    unread_count: int
    pagination: dict


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """My notifications, newest first."""
    user = await _current_user(request, db)

    base = Notification.user_id == user.id
    total = (await db.execute(select(func.count()).select_from(Notification).where(base))).scalar_one()
    unread_count = (
        await db.execute(
            select(func.count()).select_from(Notification).where(base, Notification.read_at.is_(None))
        )
    ).scalar_one()

    rows = (
        await db.execute(
            select(Notification)
            .where(base)
            .order_by(Notification.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()

    return NotificationListResponse(
        data=[
            NotificationResponse(
                id=n.id,
                title=n.title,
                body=n.body,
                category=n.category,
                channel=n.channel.value if hasattr(n.channel, "value") else str(n.channel),
                status=n.status.value if hasattr(n.status, "value") else str(n.status),
                entity_type=n.entity_type,
                entity_id=n.entity_id,
                created_at=n.created_at,
                read_at=n.read_at,
            )
            for n in rows
        ],
        unread_count=unread_count,
        pagination={
            "page": page,
            "page_size": page_size,
            "total_count": total,
            "has_next": page * page_size < total,
        },
    )


@router.get("/unread-count")
async def unread_count(request: Request, db: AsyncSession = Depends(get_db)):
    """Badge count for the bell icon."""
    user = await _current_user(request, db)
    count = (
        await db.execute(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user.id, Notification.read_at.is_(None))
        )
    ).scalar_one()
    return {"unread_count": count}


@router.post("/{notification_id}/read")
async def mark_read(notification_id: UUID, request: Request, db: AsyncSession = Depends(get_db)):
    """Mark one of MY notifications as read."""
    user = await _current_user(request, db)
    result = await db.execute(
        update(Notification)
        .where(Notification.id == notification_id, Notification.user_id == user.id, Notification.read_at.is_(None))
        .values(read_at=utc_now())
    )
    await db.commit()
    if result.rowcount == 0:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Notification not found"}},
        )
    return {"success": True}


@router.post("/read-all")
async def mark_all_read(request: Request, db: AsyncSession = Depends(get_db)):
    """Mark all of my notifications as read."""
    user = await _current_user(request, db)
    await db.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.read_at.is_(None))
        .values(read_at=utc_now())
    )
    await db.commit()
    return {"success": True}
