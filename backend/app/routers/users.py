from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import func, select

from ..audit import log_action
from ..deps import AdminUser, DbSession
from ..models import Role, User
from ..schemas import UserCreate, UserOut, UserUpdate
from ..security import hash_password

router = APIRouter(prefix="/users", tags=["Users (admin)"])


def _get_regular_user(db: DbSession, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")
    if user.role == Role.ADMIN:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail="Учётная запись администратора задаётся через .env и не изменяется через API"
        )
    return user


def _ensure_login_free(db: DbSession, login: str) -> None:
    if db.scalar(select(User.id).where(func.lower(User.login) == login.lower())):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Пользователь с таким логином уже существует")


@router.get("", response_model=list[UserOut], summary="Список обычных пользователей")
def list_users(_: AdminUser, db: DbSession):
    return db.scalars(select(User).where(User.role == Role.USER).order_by(User.id)).all()


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED, summary="Создание обычного пользователя")
def create_user(body: UserCreate, admin: AdminUser, db: DbSession):
    _ensure_login_free(db, body.login)
    user = User(login=body.login, password_hash=hash_password(body.password), role=Role.USER, is_active=True)
    db.add(user)
    db.flush()
    log_action(db, admin, "user.create", {"user_id": user.id, "login": user.login})
    db.commit()
    return user


@router.patch("/{user_id}", response_model=UserOut, summary="Изменение пользователя")
def update_user(user_id: int, body: UserUpdate, admin: AdminUser, db: DbSession):
    user = _get_regular_user(db, user_id)
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    if "login" in changes and changes["login"].lower() != user.login.lower():
        _ensure_login_free(db, changes["login"])
        user.login = changes["login"]
    if "password" in changes:
        user.password_hash = hash_password(changes["password"])
    if "is_active" in changes:
        user.is_active = changes["is_active"]
    log_action(db, admin, "user.update", {"user_id": user.id, "fields": sorted(changes)})
    db.commit()
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удаление пользователя")
def delete_user(user_id: int, admin: AdminUser, db: DbSession):
    user = _get_regular_user(db, user_id)
    # Ссылки на пользователя (paid_by_id, created_by_id, audit_logs.user_id) обнуляет сама БД: ON DELETE SET NULL
    log_action(db, admin, "user.delete", {"user_id": user.id, "login": user.login})
    db.delete(user)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
