import logging

from sqlalchemy import delete, select

from .config import settings, utcnow
from .db import SessionLocal
from .models import RevokedToken, Role, User
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


def prepare_data() -> None:
    sync_admin()
    with SessionLocal() as db:
        db.execute(delete(RevokedToken).where(RevokedToken.expires_at < utcnow().replace(tzinfo=None)))
        db.commit()
        ensure_occurrences(db)
