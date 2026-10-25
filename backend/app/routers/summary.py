from datetime import date, timedelta

from fastapi import APIRouter, Query
from sqlalchemy import select

from ..config import local_today
from ..deps import AdminUser, CurrentUser, DbSession
from ..models import AuditLog, Currency, PaymentOccurrence, PaymentStatus, RecurringPayment
from ..payments import add_months, compute_summary, ensure_occurrences, scheduled_due_date
from ..schemas import AuditLogOut, BudgetCurrency, BudgetResponse, CurrencySummary

router = APIRouter(tags=["Summary"])


@router.get(
    "/payments/summary",
    response_model=dict[Currency, CurrencySummary],
    summary="Итоговые суммы по валютам",
    description=(
        "Считается отдельно по RUB/USD/EUR, без конвертации. "
        "`total_overdue` — неоплаченные периоды с прошедшим сроком. "
        "Фильтр по сроку оплаты: date_from / date_to (например, «итоги на дату»: date_to=YYYY-MM-DD)."
    ),
)
def payments_summary(_: CurrentUser, db: DbSession, date_from: date | None = None, date_to: date | None = None):
    ensure_occurrences(db)
    return compute_summary(db, date_from, date_to)


@router.get(
    "/payments/budget",
    response_model=BudgetResponse,
    summary="Бюджет на месяц или год по валютам",
    description="Плановые расходы по расписанию активных платежей + уже оплаченное за период. Без month — весь год.",
)
def payments_budget(
    _: CurrentUser,
    db: DbSession,
    year: int = Query(default_factory=lambda: local_today().year, ge=2000, le=2100),
    month: int | None = Query(None, ge=1, le=12),
):
    start = date(year, month or 1, 1)
    end = add_months(start, 1 if month else 12)
    budget = {c: BudgetCurrency() for c in Currency}

    occurrences = db.scalars(
        select(PaymentOccurrence).where(PaymentOccurrence.due_date >= start, PaymentOccurrence.due_date < end)
    ).all()
    known = {(o.recurring_payment_id, o.due_date) for o in occurrences}
    for occ in occurrences:
        budget[Currency(occ.currency)].planned += occ.amount
        if occ.status == PaymentStatus.PAID:
            budget[Currency(occ.currency)].paid += occ.amount

    today = local_today()
    for payment in db.scalars(select(RecurringPayment).where(RecurringPayment.deleted_at.is_(None))):
        index = payment.schedule_anchor_index
        while (due := scheduled_due_date(payment, index)) < end:
            if due >= start and due >= today and (payment.id, due) not in known:
                budget[Currency(payment.currency)].planned += payment.amount
            index += 1
            if index - payment.schedule_anchor_index > 5000:
                break
    return BudgetResponse(date_from=start, date_to=end - timedelta(days=1), currencies=budget)


@router.get("/audit-logs", response_model=list[AuditLogOut], tags=["Audit"], summary="Журнал действий (админ)")
def audit_logs(_: AdminUser, db: DbSession, limit: int = Query(100, ge=1, le=1000)):
    return db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)).all()
