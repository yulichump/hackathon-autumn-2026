from fastapi import APIRouter, BackgroundTasks, HTTPException, Response, status
from sqlalchemy import delete, select

from ..audit import log_action
from ..config import local_today, utcnow
from ..deps import AdminUser, CurrentUser, DbSession
from ..models import PaymentOccurrence, PaymentStatus, RecurringPayment
from ..notifications import trigger_reminders
from ..payments import ScheduleConflictError, ensure_occurrences, recurring_to_dict, restore_payment, update_payment
from ..schemas import RecurringPaymentCreate, RecurringPaymentOut, RecurringPaymentUpdate

router = APIRouter(prefix="/recurring-payments", tags=["Recurring payments"])


def _get_payment(db: DbSession, payment_id: int) -> RecurringPayment:
    payment = db.get(RecurringPayment, payment_id)
    if payment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Регулярный платёж не найден")
    return payment


@router.get("", response_model=list[RecurringPaymentOut], summary="Список регулярных платежей")
def list_recurring(_: CurrentUser, db: DbSession, include_deleted: bool = False):
    ensure_occurrences(db)
    query = select(RecurringPayment).order_by(RecurringPayment.id)
    if not include_deleted:
        query = query.where(RecurringPayment.deleted_at.is_(None))
    return [recurring_to_dict(db, p) for p in db.scalars(query)]


@router.get("/{payment_id}", response_model=RecurringPaymentOut, summary="Регулярный платёж по id")
def get_recurring(payment_id: int, _: CurrentUser, db: DbSession):
    return recurring_to_dict(db, _get_payment(db, payment_id))


@router.post(
    "", response_model=RecurringPaymentOut, status_code=status.HTTP_201_CREATED, summary="Создание регулярного платежа"
)
def create_recurring(body: RecurringPaymentCreate, admin: AdminUser, db: DbSession, background: BackgroundTasks):
    payment = RecurringPayment(
        name=body.name,
        amount=body.amount,
        currency=body.currency,
        start_date=body.next_payment_date,
        period=body.period,
        created_by_id=admin.id,
    )
    db.add(payment)
    db.flush()
    log_action(db, admin, "recurring.create", body.model_dump() | {"id": payment.id})
    db.commit()
    ensure_occurrences(db, [payment])
    background.add_task(trigger_reminders)
    return recurring_to_dict(db, payment)


@router.patch(
    "/{payment_id}",
    response_model=RecurringPaymentOut,
    summary="Изменение регулярного платежа",
    description=(
        "Можно менять название, сумму, валюту, периодичность и дату ближайшей оплаты. Изменения касаются только "
        "будущих неоплаченных периодов (срок сегодня и позже); прошлые, просроченные и оплаченные периоды не меняются. "
        "Новая дата ближайшей оплаты должна быть позже последнего сохранённого периода, иначе `409`. "
        "Прекращённый платёж сначала нужно восстановить (`409`)."
    ),
)
def update_recurring(
    payment_id: int, body: RecurringPaymentUpdate, admin: AdminUser, db: DbSession, background: BackgroundTasks
):
    payment = _get_payment(db, payment_id)
    if payment.is_deleted:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Платёж прекращён — сначала восстановите его")
    fields = body.model_dump(exclude_unset=True, exclude_none=True)
    try:
        changes = update_payment(db, payment, **fields)
    except ScheduleConflictError as exc:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"Дата ближайшей оплаты должна быть позже последнего сохранённого периода "
            f"({exc.last_kept.strftime('%d.%m.%Y')})",
        )
    if changes:
        log_action(db, admin, "recurring.update", {"id": payment.id, "changes": changes})
    db.commit()
    ensure_occurrences(db, [payment])
    if changes:
        background.add_task(trigger_reminders)
    return recurring_to_dict(db, payment)


@router.post(
    "/{payment_id}/restore",
    response_model=RecurringPaymentOut,
    summary="Восстановление прекращённого платежа",
    description=(
        "Платёж снова создаёт периоды и напоминания. Периоды, срок которых прошёл, пока платёж был прекращён, "
        "не создаются: расписание продолжается с ближайшего срока не раньше сегодняшнего дня. "
        "Для активного платежа ничего не меняет."
    ),
)
def restore_recurring(payment_id: int, admin: AdminUser, db: DbSession, background: BackgroundTasks):
    payment = _get_payment(db, payment_id)
    if payment.is_deleted:
        first_due = restore_payment(db, payment)
        log_action(db, admin, "recurring.restore", {"id": payment.id, "name": payment.name, "first_due": first_due})
        db.commit()
        ensure_occurrences(db, [payment])
        background.add_task(trigger_reminders)
    return recurring_to_dict(db, payment)


@router.delete(
    "/{payment_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Прекращение платежа с сохранением истории"
)
def delete_recurring(payment_id: int, admin: AdminUser, db: DbSession):
    payment = _get_payment(db, payment_id)
    if not payment.is_deleted:
        payment.deleted_at = utcnow()
        db.execute(
            delete(PaymentOccurrence).where(
                PaymentOccurrence.recurring_payment_id == payment.id,
                PaymentOccurrence.status == PaymentStatus.UNPAID,
                PaymentOccurrence.due_date > local_today(),
            )
        )
        log_action(db, admin, "recurring.delete", {"id": payment.id, "name": payment.name})
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
