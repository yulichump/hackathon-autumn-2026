from importlib import import_module
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
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


def _add_missing_columns() -> None:
    """Добавляет в существующие таблицы новые nullable-колонки моделей, чтобы старая база не требовала пересоздания."""
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue
            existing = {column["name"] for column in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name not in existing:
                    column_type = column.type.compile(engine.dialect)
                    conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {column_type}'))


def init_db() -> None:
    """Создаёт таблицы всех моделей (модуль models импортируется, чтобы зарегистрировать их в Base)."""
    import_module(".models", __package__)
    Base.metadata.create_all(engine)
    _add_missing_columns()
