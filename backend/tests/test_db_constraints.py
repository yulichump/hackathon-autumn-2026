"""Инварианты защищены самой БД, а не только кодом приложения."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import (
    Currency, NotificationKind, PaymentNotification, PaymentOccurrence, PaymentStatus, Period, RecurringPayment, Role, User,
)


def _payment(db, **kw):
    p = RecurringPayment(
        name=kw.get("name", "Аренда"), amount=kw.get("amount", Decimal("10.00")), currency=Currency.RUB,
        start_date=date(2026, 1, 1), period=Period.MONTHLY,
    )
    db.add(p)
    db.flush()
    return p


def _occ(payment, index=0, **kw):
    return PaymentOccurrence(
        recurring_payment_id=payment.id, period_index=index, due_date=kw.pop("due_date", date(2026, 1, 1 + index)),
        amount=Decimal("10.00"), currency=Currency.RUB, **kw,
    )


def test_amount_must_be_positive(db):
    with pytest.raises(IntegrityError):
        _payment(db, amount=Decimal("0"))


def test_blank_name_rejected(db):
    with pytest.raises(IntegrityError):
        _payment(db, name="   ")


def test_paid_requires_actual_date(db):
    p = _payment(db)
    db.add(_occ(p, status=PaymentStatus.PAID))
    with pytest.raises(IntegrityError):
        db.flush()


def test_unpaid_cannot_have_actual_date(db):
    p = _payment(db)
    db.add(_occ(p, status=PaymentStatus.UNPAID, actual_payment_date=date(2026, 1, 1)))
    with pytest.raises(IntegrityError):
        db.flush()


def test_paid_by_only_for_paid(db):
    p = _payment(db)
    db.add(_occ(p, status=PaymentStatus.UNPAID, paid_by="someone"))
    with pytest.raises(IntegrityError):
        db.flush()


def test_period_index_and_due_date_unique_per_payment(db):
    p = _payment(db)
    db.add(_occ(p, 0))
    db.flush()
    db.add(_occ(p, 0, due_date=date(2026, 5, 5)))
    with pytest.raises(IntegrityError):
        db.flush()


def test_cannot_hard_delete_payment_with_history(db):
    p = _payment(db)
    db.add(_occ(p, 0))
    db.commit()
    db.delete(p)
    with pytest.raises(IntegrityError):  # ON DELETE RESTRICT: история не теряется
        db.flush()


def test_notification_unique_per_occurrence_and_kind(db):
    p = _payment(db)
    o = _occ(p, 0)
    db.add(o)
    db.flush()
    db.add(PaymentNotification(occurrence_id=o.id, kind=NotificationKind.REMINDER))
    db.flush()
    db.add(PaymentNotification(occurrence_id=o.id, kind=NotificationKind.REMINDER))
    with pytest.raises(IntegrityError):
        db.flush()


def test_login_unique_case_insensitive(db):
    db.add(User(login="Bob", password_hash="x", role=Role.USER))
    db.flush()
    db.add(User(login="bob", password_hash="x", role=Role.USER))
    with pytest.raises(IntegrityError):
        db.flush()


def test_only_one_active_admin(db):
    db.add(User(login="second-admin", password_hash="x", role=Role.ADMIN))  # первый админ создан фикстурой
    with pytest.raises(IntegrityError):
        db.flush()


def test_deleting_user_keeps_payment_history(db):
    user = User(login="temp", password_hash="x", role=Role.USER)
    db.add(user)
    db.flush()
    p = _payment(db)
    o = _occ(p, 0, status=PaymentStatus.PAID, actual_payment_date=date(2026, 1, 1), paid_by="temp", paid_by_id=user.id)
    db.add(o)
    db.commit()
    db.delete(user)
    db.commit()
    db.refresh(o)
    assert o.paid_by_id is None and o.paid_by == "temp"  # ссылка обнулилась, имя-снимок осталось
