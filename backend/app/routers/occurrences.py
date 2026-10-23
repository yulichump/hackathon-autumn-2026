from datetime import date

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from sqlalchemy import not_, select
from sqlalchemy.orm import contains_eager

from ..audit import log_action
from ..config import local_today
from ..deps import CurrentUser, DbSession
from ..models import Currency, PaymentOccurrence, PaymentStatus, RecurringPayment
from ..notifications import EVENT_DATE_CHANGED, EVENT_PAID, EVENT_UNPAID, notify_payment_change
from ..payments import ensure_occurrences, occurrence_to_dict, overdue_clause
from ..schemas import PaymentOccurrenceOut, PaymentOccurrenceUpdate

router = APIRouter(prefix="/payment-occurrences", tags=["Payment occurrences"])


def _get_occurrence(db: DbSession, occurrence_id: int) -> PaymentOccurrence:
    occ = db.get(PaymentOccurrence, occurrence_id)
    if occ is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Платёж не найден")
    return occ


@router.get("", response_model=list[PaymentOccurrenceOut], summary="Список периодов оплаты (с фильтрами)")
def list_occurrences(
    _: CurrentUser,
    db: DbSession,
    status_: PaymentStatus | None = Query(None, alias="status"),
    currency: Currency | None = None,
    is_overdue: bool | None = None,
    recurring_payment_id: int | None = None,
    date_from: date | None = Query(None, description="Срок оплаты с (включительно)"),
    date_to: date | None = Query(None, description="Срок оплаты по (включительно)"),
    include_deleted: bool = Query(True, description="Показывать историю удалённых регулярных платежей"),
):
    ensure_occurrences(db)
    today = local_today()
    query = (
        select(PaymentOccurrence)
        .join(PaymentOccurrence.recurring_payment)
        .options(contains_eager(PaymentOccurrence.recurring_payment))
        .order_by(PaymentOccurrence.due_date, PaymentOccurrence.id)
    )
    if status_ is not None:
        query = query.where(PaymentOccurrence.status == status_)
    if currency is not None:
        query = query.where(PaymentOccurrence.currency == currency)
    if is_overdue is not None:
        query = query.where(overdue_clause(today) if is_overdue else not_(overdue_clause(today)))
    if recurring_payment_id is not None:
        query = query.where(PaymentOccurrence.recurring_payment_id == recurring_payment_id)
    if date_from is not None:
        query = query.where(PaymentOccurrence.due_date >= date_from)
    if date_to is not None:
        query = query.where(PaymentOccurrence.due_date <= date_to)
    if not include_deleted:
        query = query.where(RecurringPayment.is_deleted.is_(False))
    return [occurrence_to_dict(o, today) for o in db.scalars(query)]


@router.get("/{occurrence_id}", response_model=PaymentOccurrenceOut, summary="Конкретный период оплаты")
def get_occurrence(occurrence_id: int, _: CurrentUser, db: DbSession):
    return occurrence_to_dict(_get_occurrence(db, occurrence_id))


@router.patch(
    "/{occurrence_id}",
    response_model=PaymentOccurrenceOut,
    summary="Подтверждение/отмена оплаты, исправление фактической даты",
    description=(
        "Срок оплаты (due_date) не меняется. `paid` без даты → фактическая дата = сегодня. "
        "`unpaid` → фактическая дата очищается. Просрочка пересчитывается по фактической дате."
    ),
)
def update_occurrence(
    occurrence_id: int, body: PaymentOccurrenceUpdate, user: CurrentUser, db: DbSession, background: BackgroundTasks
):
    occ = _get_occurrence(db, occurrence_id)
    fields = body.model_fields_set
    today = local_today()
    before = {"status": occ.status, "actual_payment_date": occ.actual_payment_date}

    new_status = body.status if "status" in fields and body.status is not None else occ.status

    if new_status == PaymentStatus.UNPAID:
        if "actual_payment_date" in fields and body.actual_payment_date is not None and "status" not in fields:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Нельзя указать дату оплаты у неоплаченного периода"
            )
        occ.status = PaymentStatus.UNPAID
        occ.actual_payment_date = None
        occ.paid_by_id = None
        occ.paid_by = None
    else:
        actual = body.actual_payment_date if "actual_payment_date" in fields else occ.actual_payment_date
        actual = actual or today
        if actual > today:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Фактическая дата оплаты не может быть в будущем"
            )
        if occ.status != PaymentStatus.PAID:
            occ.paid_by_id = user.id
            occ.paid_by = user.login
        occ.status = PaymentStatus.PAID
        occ.actual_payment_date = actual

    if "receipt_url" in fields:
        occ.receipt_url = body.receipt_url or None

    log_action(
        db, user, "occurrence.update",
        {"occurrence_id": occ.id, "before": before,
         "after": {"status": occ.status, "actual_payment_date": occ.actual_payment_date}},
    )
    db.commit()
    ensure_occurrences(db, [occ.recurring_payment])

    event = _payment_event(before, occ)
    if event is not None:
        background.add_task(notify_payment_change, occ.id, event, user.login, before["actual_payment_date"])
    return occurrence_to_dict(occ, today)


def _payment_event(before: dict, occ) -> str | None:
    was_paid = before["status"] == PaymentStatus.PAID
    is_paid = occ.status == PaymentStatus.PAID
    if not was_paid and is_paid:
        return EVENT_PAID
    if was_paid and not is_paid:
        return EVENT_UNPAID
    if is_paid and before["actual_payment_date"] != occ.actual_payment_date:
        return EVENT_DATE_CHANGED
    return None
