import json
import logging

from sqlalchemy import delete, select

from .config import settings, utcnow
from .db import SessionLocal
from .models import AuditLog, PaymentOccurrence, PaymentStatus, RevokedToken, Role, User
from .payments import ensure_occurrences
from .security import hash_password, verify_password

logger = logging.getLogger("bootstrap")


def sync_admin() -> None:
    with SessionLocal() as db:
        admin = db.scalar(select(User).where(User.login == settings.admin_login))
        if admin is None:
            admin = User(login=settings.admin_login, password_hash=hash_password(settings.admin_password))
            db.add(admin)
            logger.info("Создан администратор %s из .env", settings.admin_login)
        elif not verify_password(settings.admin_password, admin.password_hash):
            admin.password_hash = hash_password(settings.admin_password)
        admin.role = Role.ADMIN
        admin.is_active = True
        for other in db.scalars(select(User).where(User.role == Role.ADMIN, User.login != settings.admin_login)):
            other.is_active = False
        db.commit()


def backfill_paid_by(db) -> None:
    """Заполняет «кто отметил оплату» у оплат, сделанных до появления этого поля: по пользователю или журналу."""
    rows = db.scalars(
        select(PaymentOccurrence).where(PaymentOccurrence.status == PaymentStatus.PAID, PaymentOccurrence.paid_by.is_(None))
    ).all()
    if not rows:
        return
    logins = dict(db.execute(select(User.id, User.login)).all())
    telegram_actors = {}
    for entry in db.scalars(
        select(AuditLog).where(AuditLog.action == "occurrence.paid", AuditLog.actor.like("telegram:%")).order_by(AuditLog.id)
    ):
        try:
            telegram_actors[json.loads(entry.details)["occurrence_id"]] = entry.actor.removeprefix("telegram:")
        except (TypeError, ValueError, KeyError):
            continue
    for occ in rows:
        occ.paid_by = logins.get(occ.paid_by_id) or telegram_actors.get(occ.id)
    db.commit()


def prepare_data() -> None:
    sync_admin()
    with SessionLocal() as db:
        db.execute(delete(RevokedToken).where(RevokedToken.expires_at < utcnow().replace(tzinfo=None)))
        db.commit()
        backfill_paid_by(db)
        ensure_occurrences(db)
