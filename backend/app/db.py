from importlib import import_module
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

_url = make_url(settings.database_url)
_connect_args = {}
if _url.get_backend_name() == "sqlite":
    _connect_args["check_same_thread"] = False
    if _url.database and _url.database != ":memory:":
        Path(_url.database).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(settings.database_url, connect_args=_connect_args)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    with SessionLocal() as db:
        yield db


def init_db() -> None:
    """Создаёт таблицы всех моделей (модуль models импортируется, чтобы зарегистрировать их в Base)."""
    import_module(".models", __package__)
    Base.metadata.create_all(engine)
