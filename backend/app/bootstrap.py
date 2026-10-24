import logging

from sqlalchemy import delete, func, select, update

from .config import settings, utcnow
from .db import SessionLocal
from .models import RevokedToken, Role, User
from .payments import ensure_occurrences
from .security import hash_password, verify_password

logger = logging.getLogger("bootstrap")


def sync_admin() -> None:
    """Администратор задаётся .env: создаётся/обновляется при старте, остальные админы отключаются."""
    with SessionLocal() as db:
        # Сначала отключаем прежних админов: частичный уникальный индекс допускает только одного активного.
        db.execute(
            update(User)
            .where(User.role == Role.ADMIN, func.lower(User.login) != settings.admin_login.lower())
            .values(is_active=False)
        )
        admin = db.scalar(select(User).where(func.lower(User.login) == settings.admin_login.lower()))
        if admin is None:
            admin = User(login=settings.admin_login, password_hash=hash_password(settings.admin_password))
            db.add(admin)
            logger.info("Создан администратор %s из .env", settings.admin_login)
        elif not verify_password(settings.admin_password, admin.password_hash):
            admin.password_hash = hash_password(settings.admin_password)
        admin.role = Role.ADMIN
        admin.is_active = True
        db.commit()


def prepare_data() -> None:
    sync_admin()
    with SessionLocal() as db:
        db.execute(delete(RevokedToken).where(RevokedToken.expires_at < utcnow()))
        db.commit()
        ensure_occurrences(db)
