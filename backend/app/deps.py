from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .db import get_db
from .models import RevokedToken, Role, User
from .security import decode_token

bearer_scheme = HTTPBearer(auto_error=False, description="JWT из POST /api/v1/auth/login")

DbSession = Annotated[Session, Depends(get_db)]


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail=detail, headers={"WWW-Authenticate": "Bearer"})


def get_token_payload(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> dict:
    if credentials is None:
        raise _unauthorized("Требуется авторизация")
    try:
        return decode_token(credentials.credentials)
    except jwt.PyJWTError:
        raise _unauthorized("Недействительный или просроченный токен")


TokenPayload = Annotated[dict, Depends(get_token_payload)]


def get_current_user(db: DbSession, payload: TokenPayload) -> User:
    if db.get(RevokedToken, payload["jti"]):
        raise _unauthorized("Сессия завершена, войдите заново")
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise _unauthorized("Пользователь не найден или отключён")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_admin(user: CurrentUser) -> User:
    if user.role != Role.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Действие доступно только администратору")
    return user


AdminUser = Annotated[User, Depends(require_admin)]
