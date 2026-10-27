from flask import request
from flask_login import current_user

from ..extensions import db
from ..models import AuditLog


def record(action: str, entity, details=None) -> None:
    db.session.add(
        AuditLog(
            actor_id=current_user.id if current_user.is_authenticated else None,
            action=action,
            entity_type=entity.__class__.__name__,
            entity_id=str(getattr(entity, "id", "")) or None,
            details=details or {},
            ip_address=request.remote_addr,
        )
    )

