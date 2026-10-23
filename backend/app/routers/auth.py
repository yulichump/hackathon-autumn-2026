from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from ..audit import log_action
from ..deps import CurrentUser, DbSession, TokenPayload
from ..models import RevokedToken, User
from ..schemas import LoginRequest, MeResponse, MessageResponse, TokenResponse
from ..security import create_access_token, verify_password

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=TokenResponse, summary="Вход по логину и паролю")
def login(body: LoginRequest, db: DbSession):
    user = db.scalar(select(User).where(User.login == body.login))
    if user is None or not verify_password(body.password, user.password_hash):
        log_action(db, None, "auth.login_failed", {"login": body.login}, actor=body.login)
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Неверный логин или пароль")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Учётная запись отключена")
    log_action(db, user, "auth.login")
    db.commit()
    return TokenResponse(access_token=create_access_token(user), role=user.role)


@router.get("/me", response_model=MeResponse, summary="Текущий пользователь")
def me(user: CurrentUser):
    return user


@router.post("/logout", response_model=MessageResponse, summary="Завершение текущей сессии")
def logout(user: CurrentUser, payload: TokenPayload, db: DbSession):
    expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    db.merge(RevokedToken(jti=payload["jti"], expires_at=expires_at))
    log_action(db, user, "auth.logout")
    db.commit()
    return MessageResponse(message="Successfully logged out")
