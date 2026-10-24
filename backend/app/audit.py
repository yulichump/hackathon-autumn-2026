import json
import logging

from sqlalchemy.orm import Session

from .models import AuditLog, User

logger = logging.getLogger("audit")


def log_action(db: Session, user: User | None, action: str, details: dict | None = None, actor: str | None = None) -> None:
    """Добавляет запись в журнал; коммит делает вызывающий код."""
    actor = actor or (user.login if user else "anonymous")
    # Прогоняем через json, чтобы даты/Decimal/enum стали обычными JSON-значениями для JSONB
    payload = json.loads(json.dumps(details, ensure_ascii=False, default=str)) if details else None
    db.add(AuditLog(user_id=user.id if user else None, actor=actor, action=action, details=payload))
    logger.info("%s %s %s", actor, action, json.dumps(payload, ensure_ascii=False) if payload else "")
