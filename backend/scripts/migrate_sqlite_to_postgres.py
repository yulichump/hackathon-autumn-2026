"""Разовый перенос данных из старой SQLite-базы в PostgreSQL (схема должна быть создана: `alembic upgrade head`).

    python scripts/migrate_sqlite_to_postgres.py --sqlite data/invoice_keeper.db [--target-url postgresql+psycopg://...] [--replace]

Что делает по пути:
- id сохраняются (ссылки не ломаются), после вставки счётчики id выставляются на максимум;
- is_deleted → deleted_at; naive-время старой базы считается UTC → timestamptz;
- reminder_*/overdue_* из payment_occurrences → строки в payment_notifications;
- audit_logs.details (текст) → JSONB (не JSON оборачивается в {"raw": "..."});
- данные, нарушающие новые ограничения, чинятся и попадают в отчёт, а не обрываются молча.
Всё выполняется в одной транзакции: либо перенесено целиком, либо ничего.
"""

import argparse
import json
import sqlite3
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, func, insert, select, text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.models import (  # noqa: E402
    AuditLog, Currency, NotificationKind, PaymentNotification, PaymentOccurrence, PaymentStatus, Period,
    RecurringPayment, RevokedToken, Role, User,
)

TABLES = [User, RevokedToken, RecurringPayment, PaymentOccurrence, PaymentNotification, AuditLog]


def ts(value):
    if not value:
        return None
    moment = datetime.fromisoformat(value)
    return moment.replace(tzinfo=timezone.utc) if moment.tzinfo is None else moment


def d(value):
    return date.fromisoformat(value[:10]) if value else None


def money(value):
    return Decimal(str(value)).quantize(Decimal("0.01"))


def read(conn, table):
    conn.row_factory = sqlite3.Row
    return [dict(r) for r in conn.execute(f"SELECT * FROM {table}")]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sqlite", required=True, help="путь к старому файлу SQLite")
    parser.add_argument("--target-url", default=settings.database_url, help="адрес PostgreSQL (по умолчанию из .env)")
    parser.add_argument("--replace", action="store_true", help="очистить таблицы PostgreSQL перед переносом")
    args = parser.parse_args()

    if not Path(args.sqlite).is_file():
        print(f"Файл не найден: {args.sqlite}")
        return 1
    src = sqlite3.connect(args.sqlite)
    engine = create_engine(args.target_url)
    report: list[str] = []

    users = read(src, "users")
    logins = [u["login"].lower() for u in users]
    if len(set(logins)) != len(logins):
        print("В старой базе есть логины, отличающиеся только регистром, — в PostgreSQL логин уникален без учёта регистра.")
        print("Переименуйте дубликаты и повторите перенос.")
        return 1

    with engine.begin() as pg:
        tables = ", ".join(f'"{t.__tablename__}"' for t in TABLES)
        if args.replace:
            pg.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
        elif pg.scalar(select(func.count()).select_from(User)):
            print("В PostgreSQL уже есть данные. Запустите с --replace, чтобы очистить их перед переносом.")
            return 1

        user_ids = {u["id"] for u in users}
        pg.execute(
            insert(User),
            [
                {
                    "id": u["id"], "login": u["login"], "password_hash": u["password_hash"], "role": Role(u["role"]),
                    "is_active": bool(u["is_active"]), "created_at": ts(u["created_at"]), "updated_at": ts(u["created_at"]),
                }
                for u in users
            ],
        )

        revoked = read(src, "revoked_tokens")
        if revoked:
            pg.execute(insert(RevokedToken), [{"jti": r["jti"], "expires_at": ts(r["expires_at"])} for r in revoked])

        payments = read(src, "recurring_payments")
        if payments:
            pg.execute(
                insert(RecurringPayment),
                [
                    {
                        "id": p["id"], "name": p["name"].strip() or f"Платёж #{p['id']}", "amount": money(p["amount"]),
                        "currency": Currency(p["currency"]), "start_date": d(p["start_date"]), "period": Period(p["period"]),
                        "deleted_at": (ts(p["deleted_at"]) or ts(p["created_at"])) if p["is_deleted"] else None,
                        "created_at": ts(p["created_at"]), "updated_at": ts(p["created_at"]),
                        "created_by_id": p["created_by_id"] if p["created_by_id"] in user_ids else None,
                    }
                    for p in payments
                ],
            )

        occurrences = read(src, "payment_occurrences")
        occ_rows, notif_rows = [], []
        for o in occurrences:
            status = PaymentStatus(o["status"])
            actual = d(o["actual_payment_date"])
            if status == PaymentStatus.PAID and actual is None:
                actual = d(o["due_date"])
                report.append(f"период #{o['id']}: оплачен без даты → фактическая дата = срок ({actual})")
            if status == PaymentStatus.UNPAID and actual is not None:
                actual = None
                report.append(f"период #{o['id']}: не оплачен, но была дата оплаты → дата очищена")
            paid = status == PaymentStatus.PAID
            occ_rows.append(
                {
                    "id": o["id"], "recurring_payment_id": o["recurring_payment_id"], "period_index": o["period_index"],
                    "due_date": d(o["due_date"]), "amount": money(o["amount"]), "currency": Currency(o["currency"]),
                    "status": status, "actual_payment_date": actual, "receipt_url": o["receipt_url"],
                    "paid_by_id": o["paid_by_id"] if paid and o["paid_by_id"] in user_ids else None,
                    "paid_by": o["paid_by"] if paid else None,
                    "created_at": ts(o["updated_at"]), "updated_at": ts(o["updated_at"]),
                }
            )
            for kind, sent, message in (
                (NotificationKind.REMINDER, o["reminder_sent_at"], o["reminder_message_id"]),
                (NotificationKind.OVERDUE, o["overdue_notice_sent_at"], o["overdue_message_id"]),
            ):
                if sent:
                    notif_rows.append(
                        {"occurrence_id": o["id"], "kind": kind, "sent_at": ts(sent), "telegram_message_id": message}
                    )
        if occ_rows:
            pg.execute(insert(PaymentOccurrence), occ_rows)
        if notif_rows:
            pg.execute(insert(PaymentNotification), notif_rows)

        logs = read(src, "audit_logs")
        log_rows = []
        for entry in logs:
            try:
                details = json.loads(entry["details"]) if entry["details"] else None
            except ValueError:
                details = {"raw": entry["details"]}
                report.append(f"audit_logs #{entry['id']}: details не JSON → сохранён как {{'raw': ...}}")
            log_rows.append(
                {
                    "id": entry["id"], "created_at": ts(entry["created_at"]),
                    "user_id": entry["user_id"] if entry["user_id"] in user_ids else None,
                    "actor": entry["actor"], "action": entry["action"], "details": details,
                }
            )
        if log_rows:
            pg.execute(insert(AuditLog), log_rows)

        for model in (User, RecurringPayment, PaymentOccurrence, PaymentNotification, AuditLog):
            table = model.__tablename__
            pg.execute(
                text(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), GREATEST((SELECT COALESCE(MAX(id), 0) FROM {table}), 1), "
                     f"(SELECT COUNT(*) > 0 FROM {table}))")
            )

        counts = {
            "users": (len(users), User), "revoked_tokens": (len(revoked), RevokedToken),
            "recurring_payments": (len(payments), RecurringPayment), "payment_occurrences": (len(occurrences), PaymentOccurrence),
            "payment_notifications": (len(notif_rows), PaymentNotification), "audit_logs": (len(logs), AuditLog),
        }
        print("Перенесено (источник → PostgreSQL):")
        for name, (expected, model) in counts.items():
            actual = pg.scalar(select(func.count()).select_from(model))
            flag = "OK" if actual == expected else "РАСХОЖДЕНИЕ!"
            print(f"  {name:<24}{expected:>6} → {actual:<6}{flag}")
            if actual != expected:
                raise SystemExit("Количество строк не совпало — транзакция отменена.")
    if report:
        print("\nИсправления данных:")
        print("\n".join(f"  - {line}" for line in report))
    print("\nГотово.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
