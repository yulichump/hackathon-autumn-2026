import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func, select

from app import notifications
from app.config import local_today
from app.db import SessionLocal
from app.models import (
    Currency, NotificationKind, PaymentNotification, PaymentOccurrence, PaymentStatus, Period, RecurringPayment,
)
from app.payments import ensure_occurrences


def _make(db, days_from_today, name="P"):
    p = RecurringPayment(
        name=name, amount=Decimal("5.00"), currency=Currency.EUR,
        start_date=local_today() + timedelta(days=days_from_today), period=Period.YEARLY,
    )
    db.add(p)
    db.commit()
    ensure_occurrences(db, [p])
    return db.scalar(select(PaymentOccurrence).where(PaymentOccurrence.recurring_payment_id == p.id))


def test_claim_is_exclusive_and_releasable(db):
    occ = _make(db, 2)
    first = notifications._claim(occ.id, NotificationKind.REMINDER)
    assert first is not None
    assert notifications._claim(occ.id, NotificationKind.REMINDER) is None  # второй раз — нельзя
    assert notifications._claim(occ.id, NotificationKind.OVERDUE) is not None  # другой вид — можно
    notifications._release(first)
    assert notifications._claim(occ.id, NotificationKind.REMINDER) is not None  # после сбоя доставки — повтор


def test_claim_races_have_exactly_one_winner(db):
    occ = _make(db, 2)
    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(lambda _: notifications._claim(occ.id, NotificationKind.REMINDER), range(24)))
    assert sum(r is not None for r in results) == 1
    count = db.scalar(select(func.count()).select_from(PaymentNotification).where(PaymentNotification.occurrence_id == occ.id))
    assert count == 1


def test_paid_occurrence_cannot_be_claimed(db):
    occ = _make(db, 2)
    occ.status, occ.actual_payment_date = PaymentStatus.PAID, local_today()
    db.commit()
    assert notifications._claim(occ.id, NotificationKind.REMINDER) is None


def test_collect_pending_reminder_and_overdue_once(db):
    soon = _make(db, 2, "soon")
    late = _make(db, -3, "late")
    far = _make(db, 30, "far")
    kinds = {(i["id"], i["kind"]) for i in notifications._collect_pending()}
    assert (soon.id, NotificationKind.REMINDER) in kinds and (late.id, NotificationKind.OVERDUE) in kinds
    assert not any(i == far.id for i, _ in kinds)
    notifications._claim(soon.id, NotificationKind.REMINDER)
    assert (soon.id, NotificationKind.REMINDER) not in {(i["id"], i["kind"]) for i in notifications._collect_pending()}


def test_run_reminders_delivers_once_and_retries_after_failure(db, monkeypatch):
    occ = _make(db, 1)
    sent = []

    class FakeBot:
        can_send = True
        fail = True

        async def send_message(self, text, **kw):
            if self.fail:
                return None
            sent.append(text)
            return {"message_id": 4242}

    bot = FakeBot()
    monkeypatch.setattr(notifications, "bot", bot)

    asyncio.run(notifications.run_reminders())  # доставка не удалась → запись снята
    assert not sent and db.scalar(select(func.count()).select_from(PaymentNotification)) == 0

    bot.fail = False
    asyncio.run(notifications.run_reminders())
    asyncio.run(notifications.run_reminders())  # повторный запуск не дублирует
    assert len(sent) == 1
    n = db.scalar(select(PaymentNotification).where(PaymentNotification.occurrence_id == occ.id))
    assert n.telegram_message_id == 4242 and n.kind == NotificationKind.REMINDER
