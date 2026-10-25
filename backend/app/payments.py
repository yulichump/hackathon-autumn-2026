"""Бизнес-логика: расписание периодов, генерация оплат, просрочка, итоги."""

import calendar
from collections.abc import Iterable
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import and_, case, delete, func, or_, select, text, update
from sqlalchemy.orm import Session

from .config import local_today
from .models import Currency, NotificationKind, PaymentOccurrence, PaymentStatus, Period, RecurringPayment

MAX_NEW_OCCURRENCES_PER_RUN = 400
MAX_RESTORE_STEPS = 20_000

# Ключ advisory-блокировки PostgreSQL: генерацию периодов одновременно ведёт только один процесс/поток.
_GENERATION_LOCK_KEY = 7_201_926


def add_months(start: date, months: int) -> date:
    """Сдвиг на N месяцев от исходной даты. Нет такого числа в месяце → последний день месяца."""
    year, month0 = divmod(start.month - 1 + months, 12)
    year += start.year
    last_day = calendar.monthrange(year, month0 + 1)[1]
    return date(year, month0 + 1, min(start.day, last_day))


def due_date_for(start: date, period: str, index: int) -> date:
    """Срок N-го периода считается всегда от start_date, чтобы 31-е не «сползало» к 28-му."""
    match period:
        case Period.DAILY:
            return start + timedelta(days=index)
        case Period.WEEKLY:
            return start + timedelta(weeks=index)
        case Period.MONTHLY:
            return add_months(start, index)
        case Period.QUARTERLY:
            return add_months(start, 3 * index)
        case Period.YEARLY:
            return add_months(start, 12 * index)
    raise ValueError(f"Unknown period: {period}")


def scheduled_due_date(payment: RecurringPayment, index: int) -> date:
    """Срок периода с номером `index` по текущему расписанию.

    После изменения даты или периодичности расписание начинается заново с `start_date`
    у периода номер `schedule_anchor_index`; номера более ранних периодов (история) не меняются.
    """
    return due_date_for(payment.start_date, payment.period, index - payment.schedule_anchor_index)


def is_overdue(occ: PaymentOccurrence, today: date | None = None) -> bool:
    """Просрочка — со следующего дня после срока; оплата в день срока — вовремя."""
    if occ.status == PaymentStatus.PAID:
        return occ.actual_payment_date is not None and occ.actual_payment_date > occ.due_date
    return (today or local_today()) > occ.due_date


def days_overdue(occ: PaymentOccurrence, today: date | None = None) -> int:
    if not is_overdue(occ, today):
        return 0
    end = occ.actual_payment_date if occ.status == PaymentStatus.PAID else (today or local_today())
    return (end - occ.due_date).days


def overdue_clause(today: date):
    return or_(
        and_(PaymentOccurrence.status == PaymentStatus.UNPAID, PaymentOccurrence.due_date < today),
        and_(
            PaymentOccurrence.status == PaymentStatus.PAID,
            PaymentOccurrence.actual_payment_date > PaymentOccurrence.due_date,
        ),
    )


def ensure_occurrences(db: Session, payments: Iterable[RecurringPayment] | None = None) -> int:
    """Создаёт недостающие периоды. Возвращает число созданных.

    Правило: у активного платежа всегда есть «следующий» период — создаём новый, пока
    последний период уже наступил (срок <= сегодня) или уже оплачен. Прошлые периоды
    (оплаченные и просроченные) не трогаем — история сохраняется, просрочка не
    останавливает следующие периоды.
    """
    today = local_today()
    created = 0
    # Транзакционная блокировка снимается на commit; работает и между несколькими экземплярами бэкенда.
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _GENERATION_LOCK_KEY})
    if payments is None:
        payments = db.scalars(select(RecurringPayment).where(RecurringPayment.deleted_at.is_(None))).all()
    for payment in payments:
        if payment.is_deleted:
            continue
        last = db.scalar(
            select(PaymentOccurrence)
            .where(PaymentOccurrence.recurring_payment_id == payment.id)
            .order_by(PaymentOccurrence.period_index.desc())
            .limit(1)
        )
        budget = MAX_NEW_OCCURRENCES_PER_RUN
        while budget and (last is None or last.due_date <= today or last.status == PaymentStatus.PAID):
            index = 0 if last is None else last.period_index + 1
            last = PaymentOccurrence(
                recurring_payment_id=payment.id,
                period_index=index,
                due_date=scheduled_due_date(payment, index),
                amount=payment.amount,
                currency=payment.currency,
                status=PaymentStatus.UNPAID,
            )
            db.add(last)
            db.flush()
            created += 1
            budget -= 1
    db.commit()
    return created


def next_payment_date(db: Session, payment: RecurringPayment) -> date | None:
    """Ближайший неоплаченный период (просроченный тоже считается «к оплате»)."""
    nearest = db.scalar(
        select(PaymentOccurrence.due_date)
        .where(
            PaymentOccurrence.recurring_payment_id == payment.id,
            PaymentOccurrence.status == PaymentStatus.UNPAID,
        )
        .order_by(PaymentOccurrence.due_date)
        .limit(1)
    )
    if nearest is not None or payment.is_deleted:
        return nearest
    last_index = db.scalar(
        select(PaymentOccurrence.period_index)
        .where(PaymentOccurrence.recurring_payment_id == payment.id)
        .order_by(PaymentOccurrence.period_index.desc())
        .limit(1)
    )
    return scheduled_due_date(payment, payment.schedule_anchor_index if last_index is None else last_index + 1)


class ScheduleConflictError(ValueError):
    """Новое расписание пересекается с уже сохранёнными периодами."""

    def __init__(self, last_kept: date):
        super().__init__(last_kept)
        self.last_kept = last_kept


def _last_occurrence(db: Session, payment: RecurringPayment) -> PaymentOccurrence | None:
    return db.scalar(
        select(PaymentOccurrence)
        .where(PaymentOccurrence.recurring_payment_id == payment.id)
        .order_by(PaymentOccurrence.period_index.desc())
        .limit(1)
    )


def _upcoming_unpaid_date(db: Session, payment: RecurringPayment, today: date) -> date | None:
    return db.scalar(
        select(func.min(PaymentOccurrence.due_date)).where(
            PaymentOccurrence.recurring_payment_id == payment.id,
            PaymentOccurrence.status == PaymentStatus.UNPAID,
            PaymentOccurrence.due_date >= today,
        )
    )


def _future_unpaid(payment: RecurringPayment, today: date):
    return and_(
        PaymentOccurrence.recurring_payment_id == payment.id,
        PaymentOccurrence.status == PaymentStatus.UNPAID,
        PaymentOccurrence.due_date >= today,
    )


def update_payment(
    db: Session,
    payment: RecurringPayment,
    *,
    name: str | None = None,
    amount: Decimal | None = None,
    currency: Currency | None = None,
    period: Period | None = None,
    next_payment_date: date | None = None,
) -> dict:
    """Меняет шаблон платежа. Возвращает изменённые поля {поле: [было, стало]}; коммит — за вызывающим.

    Затрагиваются только будущие неоплаченные периоды (срок сегодня и позже): прошлые, просроченные
    и оплаченные остаются как были. Смена даты или периодичности пересоздаёт будущие периоды по
    новому расписанию; дата должна быть позже последнего сохранённого периода.
    """
    today = local_today()
    changes: dict = {}

    if name is not None and name != payment.name:
        changes["name"] = [payment.name, name]
        payment.name = name

    current_next = _upcoming_unpaid_date(db, payment, today) or next_payment_date_for_schedule(db, payment)
    new_period = period if period is not None else payment.period
    new_start = next_payment_date if next_payment_date is not None else current_next
    if new_period != payment.period or new_start != current_next:
        db.execute(delete(PaymentOccurrence).where(_future_unpaid(payment, today)))
        last = _last_occurrence(db, payment)
        if last is not None and new_start <= last.due_date:
            raise ScheduleConflictError(last.due_date)
        if new_period != payment.period:
            changes["period"] = [payment.period, new_period]
        if new_start != current_next:
            changes["next_payment_date"] = [current_next, new_start]
        payment.period = new_period
        payment.start_date = new_start
        payment.schedule_anchor_index = 0 if last is None else last.period_index + 1

    new_amount = amount if amount is not None else payment.amount
    new_currency = currency if currency is not None else payment.currency
    if new_amount != payment.amount or new_currency != payment.currency:
        if new_amount != payment.amount:
            changes["amount"] = [payment.amount, new_amount]
        if new_currency != payment.currency:
            changes["currency"] = [payment.currency, new_currency]
        payment.amount = new_amount
        payment.currency = new_currency
        db.execute(
            update(PaymentOccurrence)
            .where(_future_unpaid(payment, today))
            .values(amount=new_amount, currency=new_currency)
            .execution_options(synchronize_session=False)
        )
    db.flush()
    return changes


def next_payment_date_for_schedule(db: Session, payment: RecurringPayment) -> date:
    """Срок следующего ещё не созданного периода по расписанию."""
    last = _last_occurrence(db, payment)
    return scheduled_due_date(payment, payment.schedule_anchor_index if last is None else last.period_index + 1)


def restore_payment(db: Session, payment: RecurringPayment) -> date | None:
    """Возобновляет прекращённый платёж; коммит — за вызывающим. Возвращает срок первого нового периода.

    Периоды, срок которых прошёл, пока платёж был прекращён, задним числом не создаются:
    расписание продолжается с ближайшего срока, не раньше сегодняшнего дня.
    """
    today = local_today()
    payment.deleted_at = None
    last = _last_occurrence(db, payment)
    index = payment.schedule_anchor_index if last is None else last.period_index + 1
    if last is not None and last.status == PaymentStatus.UNPAID and last.due_date >= today:
        return None
    for _ in range(MAX_RESTORE_STEPS):
        due = scheduled_due_date(payment, index)
        if due >= today:
            break
        index += 1
    else:
        raise ValueError("Не удалось найти следующий срок по расписанию")
    db.add(
        PaymentOccurrence(
            recurring_payment_id=payment.id,
            period_index=index,
            due_date=due,
            amount=payment.amount,
            currency=payment.currency,
            status=PaymentStatus.UNPAID,
        )
    )
    db.flush()
    return due


def occurrence_to_dict(occ: PaymentOccurrence, today: date | None = None) -> dict:
    today = today or local_today()
    rp = occ.recurring_payment
    return {
        "id": occ.id,
        "recurring_payment_id": occ.recurring_payment_id,
        "name": rp.name,
        "amount": occ.amount,
        "currency": occ.currency,
        "due_date": occ.due_date,
        "status": occ.status,
        "actual_payment_date": occ.actual_payment_date,
        "is_overdue": is_overdue(occ, today),
        "days_overdue": days_overdue(occ, today),
        "paid_by": occ.paid_by if occ.status == PaymentStatus.PAID else None,
        "receipt_url": occ.receipt_url,
        "period": rp.period,
        "recurring_payment_is_deleted": rp.is_deleted,
        "reminder_sent": any(n.kind == NotificationKind.REMINDER for n in occ.notifications),
    }


def recurring_to_dict(db: Session, payment: RecurringPayment) -> dict:
    return {
        "id": payment.id,
        "name": payment.name,
        "amount": payment.amount,
        "currency": payment.currency,
        "next_payment_date": next_payment_date(db, payment),
        "period": payment.period,
        "is_deleted": payment.is_deleted,
        "start_date": payment.start_date,
        "created_at": payment.created_at,
    }


def compute_summary(db: Session, date_from: date | None = None, date_to: date | None = None) -> dict[str, dict]:
    """Итоги по каждой валюте отдельно (без конвертации) по срокам периодов в диапазоне. Считает сама БД."""
    today = local_today()
    unpaid = PaymentOccurrence.status == PaymentStatus.UNPAID
    amount = PaymentOccurrence.amount
    query = select(
        PaymentOccurrence.currency,
        func.coalesce(func.sum(amount), 0),
        func.coalesce(func.sum(case((~unpaid, amount), else_=0)), 0),
        func.coalesce(func.sum(case((unpaid, amount), else_=0)), 0),
        func.coalesce(func.sum(case((unpaid & (PaymentOccurrence.due_date < today), amount), else_=0)), 0),
    ).group_by(PaymentOccurrence.currency)
    if date_from:
        query = query.where(PaymentOccurrence.due_date >= date_from)
    if date_to:
        query = query.where(PaymentOccurrence.due_date <= date_to)

    zero = Decimal("0.00")
    result = {
        c.value: {"total_planned": zero, "total_paid": zero, "total_unpaid": zero, "total_overdue": zero} for c in Currency
    }
    for currency, planned, paid, unpaid_sum, overdue in db.execute(query):
        result[Currency(currency).value] = {
            "total_planned": Decimal(planned),
            "total_paid": Decimal(paid),
            "total_unpaid": Decimal(unpaid_sum),
            "total_overdue": Decimal(overdue),
        }
    return result
