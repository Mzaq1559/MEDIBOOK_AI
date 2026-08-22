import uuid
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog


def log_audit_event(
    db: Session,
    action: str,
    table_name: str,
    record_id: uuid.UUID,
    user_id: Optional[uuid.UUID] = None,
    old_values: Optional[Dict[str, Any]] = None,
    new_values: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    commit: bool = False
) -> AuditLog:
    """Create an audit log record, filtering out sensitive fields."""
    sensitive_keys = {"password", "password_hash", "token", "access_token", "refresh_token", "secret"}

    def clean_dict(d: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not d:
            return None
        return {k: ("***" if k.lower() in sensitive_keys else v) for k, v in d.items()}

    log_entry = AuditLog(
        id=uuid.uuid4(),
        user_id=user_id,
        action=action,
        table_name=table_name,
        record_id=record_id,
        old_values=clean_dict(old_values),
        new_values=clean_dict(new_values),
        ip_address=ip_address,
        user_agent=user_agent
    )
    db.add(log_entry)
    if commit:
        db.commit()
    return log_entry
