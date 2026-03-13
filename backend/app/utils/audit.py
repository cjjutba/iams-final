"""
Audit Logging Utility

Helper function to record admin actions in the audit log.
"""

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def log_audit(
    db: Session,
    admin_id,
    action: str,
    target_type: str,
    target_id: str | None = None,
    details: str | None = None,
):
    """
    Record an admin action in the audit log.

    Args:
        db: Database session
        admin_id: UUID of the admin performing the action
        action: Action performed (e.g., 'create', 'update', 'delete')
        target_type: Type of entity acted upon (e.g., 'room', 'user')
        target_id: ID of the target entity (optional)
        details: Additional details about the action (optional)
    """
    log = AuditLog(
        admin_id=admin_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details,
    )
    db.add(log)
    db.commit()
