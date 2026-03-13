"""
Notifications Router

API endpoints for user notifications.
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.repositories.notification_repository import NotificationRepository
from app.schemas.notification import NotificationResponse
from app.utils.dependencies import get_current_user

router = APIRouter()


@router.get("/", response_model=list[NotificationResponse], status_code=status.HTTP_200_OK)
def get_notifications(
    unread_only: bool = Query(False, description="Only return unread notifications"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of records"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    **Get User Notifications**

    Get notifications for the current authenticated user.

    - **unread_only**: If true, only return unread notifications
    - **skip**: Number of records to skip (pagination)
    - **limit**: Maximum number of records to return

    Returns list of notifications sorted by most recent first.

    Requires authentication.
    """
    notification_repo = NotificationRepository(db)

    notifications = notification_repo.get_by_user(str(current_user.id), unread_only=unread_only, skip=skip, limit=limit)

    return [NotificationResponse.model_validate(n) for n in notifications]


@router.patch("/{notification_id}/read", response_model=NotificationResponse, status_code=status.HTTP_200_OK)
def mark_notification_read(
    notification_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    **Mark Notification as Read**

    Mark a specific notification as read.

    - **notification_id**: Notification UUID

    Only the notification owner can mark it as read.

    Requires authentication.
    """
    from fastapi import HTTPException

    notification_repo = NotificationRepository(db)

    # Get notification and verify ownership
    notification = notification_repo.get_by_id(notification_id)
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

    if str(notification.user_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    notification = notification_repo.mark_as_read(notification_id)

    return NotificationResponse.model_validate(notification)


@router.post("/read-all", status_code=status.HTTP_200_OK)
def mark_all_notifications_read(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    **Mark All Notifications as Read**

    Mark all unread notifications as read for the current user.

    Requires authentication.
    """
    notification_repo = NotificationRepository(db)

    count = notification_repo.mark_all_as_read(str(current_user.id))

    return {"success": True, "message": f"{count} notification(s) marked as read"}


@router.get("/unread-count", status_code=status.HTTP_200_OK)
def get_unread_count(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    **Get Unread Notification Count**

    Get the count of unread notifications for the current user.

    Requires authentication.
    """
    notification_repo = NotificationRepository(db)

    count = notification_repo.get_unread_count(str(current_user.id))

    return {"unread_count": count}
