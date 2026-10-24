"""Тесты идут на настоящем PostgreSQL (отдельная БД), схема создаётся теми же миграциями Alembic.

Запуск: TEST_DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/invoice_keeper_test pytest
Пустая БД должна существовать; её содержимое тесты стирают.
"""

import os

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL", "postgresql+psycopg://invoice:invoice@localhost:5432/invoice_keeper_test"
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.update(
    ADMIN_LOGIN="admin", ADMIN_PASSWORD="admin-pass", SECRET_KEY="test-secret", TELEGRAM_BOT_TOKEN="", WEBHOOK_URL=""
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.bootstrap import sync_admin  # noqa: E402
from app.db import Base, SessionLocal, engine, upgrade_head  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _schema():
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    upgrade_head()
    yield


@pytest.fixture(autouse=True)
def _clean_tables(_schema):
    tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    sync_admin()


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client():
    return TestClient(app)  # без lifespan: фоновые задачи и Telegram не нужны


def _login(client, login, password):
    r = client.post("/api/v1/auth/login", json={"login": login, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def admin_headers(client):
    return _login(client, "admin", "admin-pass")


@pytest.fixture
def user_headers(client, admin_headers):
    r = client.post("/api/v1/users", json={"login": "worker", "password": "worker-pass"}, headers=admin_headers)
    assert r.status_code == 201, r.text
    return _login(client, "worker", "worker-pass")
