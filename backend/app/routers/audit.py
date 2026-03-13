"""
Audit Router

API endpoints for viewing audit logs (admin only).
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.utils.dependencies import get_current_admin

router = APIRouter()


@router.get("/logs", status_code=status.HTTP_200_OK)
def get_audit_logs(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of records"),
    action: str | None = Query(None, description="Filter by action type"),
    target_type: str | None = Query(None, description="Filter by target entity type"),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    **Get Audit Logs** (Admin Only)

    Retrieve a paginated list of audit log entries.

    - **skip**: Number of records to skip (pagination)
    - **limit**: Maximum number of records to return
    - **action**: Optional filter by action (e.g., 'create', 'update', 'delete')
    - **target_type**: Optional filter by target type (e.g., 'room', 'user')

    Requires admin authentication.
    """
    query = db.query(AuditLog).order_by(desc(AuditLog.created_at))

    if action:
        query = query.filter(AuditLog.action == action)
    if target_type:
        query = query.filter(AuditLog.target_type == target_type)

    total = query.count()
    logs = query.offset(skip).limit(limit).all()

    return {
        "items": [
            {
                "id": str(log.id),
                "admin_id": str(log.admin_id),
                "action": log.action,
                "target_type": log.target_type,
                "target_id": log.target_id,
                "details": log.details,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ],
        "total": total,
        "skip": skip,
        "limit": limit,
    }
