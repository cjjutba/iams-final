"""
Audit Logs Router

Admin-only endpoint for viewing audit trail of administrative actions.
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.utils.dependencies import get_current_admin

router = APIRouter()


@router.get("/logs", status_code=status.HTTP_200_OK)
def get_audit_logs(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    action: str | None = Query(default=None),
    target_type: str | None = Query(default=None),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Get paginated audit logs, optionally filtered by action and/or target_type.
    """
    query = db.query(AuditLog)

    if action:
        query = query.filter(AuditLog.action == action)
    if target_type:
        query = query.filter(AuditLog.target_type == target_type)

    total = query.count()
    logs = query.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit).all()

    return {
        "success": True,
        "data": [
            {
                "id": str(log.id),
                "admin_id": str(log.admin_id),
                "action": log.action,
                "target_type": log.target_type,
                "target_id": log.target_id,
                "details": log.details,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ],
        "total": total,
        "skip": skip,
        "limit": limit,
    }
