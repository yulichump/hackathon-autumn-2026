"""Оповещения (Telegram + webhook): напоминания о сроках, события оплаты, команды и кнопки бота."""

import asyncio
import html
import logging
from collections.abc import Iterable
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import httpx
from sqlalchemy import select, update
from sqlalchemy.orm import contains_eager

from .audit import log_action
from .config import local_today, settings, utcnow
from .db import SessionLocal
from .models import PaymentOccurrence, PaymentStatus, RecurringPayment
from .payments import compute_summary, ensure_occurrences
from .telegram import TelegramBot

logger = logging.getLogger("notifications")

bot: TelegramBot | None = None

REMINDER = "reminder"
OVERDUE = "overdue"

EVENT_PAID = "paid"
EVENT_UNPAID = "unpaid"
EVENT_DATE_CHANGED = "date_changed"

NO_BUTTONS = {"inline_keyboard": []}

_run_lock = asyncio.Lock()
_warned_no_channels = False


def fmt_amount(amount) -> str:
    return f"{Decimal(amount):,.2f}".replace(",", " ")


def fmt_date(d: date) -> str:
    return d.strftime("%d.%m.%Y")


def _local_date(moment: datetime) -> date:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(settings.tz).date()


def _days(n: int) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return f"{n} день"
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return f"{n} дня"
    return f"{n} дней"


def _when(days: int) -> str:
    if days == 0:
        return "сегодня"
    if days == 1:
        return "завтра"
    return f"через {_days(days)}"


def _paid_button(occ_id: int) -> dict:
    return {"inline_keyboard": [[{"text": "✅ Оплачено", "callback_data": f"paid:{occ_id}"}]]}


def _head(occ: PaymentOccurrence) -> str:
    return f"<b>{html.escape(occ.recurring_payment.name)}</b>\nСумма: {fmt_amount(occ.amount)} {occ.currency}"


def _render(occ: PaymentOccurrence, kind: str, as_of: date) -> str:
    """Текст напоминания на дату отправки `as_of` — при редактировании сообщения он не «плывёт»."""
    if kind == REMINDER:
        return (
            f"🔔 <b>Напоминание об оплате</b>\n\n{_head(occ)}\n"
            f"Срок оплаты: {fmt_date(occ.due_date)} ({_when((occ.due_date - as_of).days)})"
        )
    return (
        f"⚠️ <b>Платёж просрочен</b>\n\n{_head(occ)}\n"
        f"Срок оплаты был: {fmt_date(occ.due_date)} (просрочка {_days((as_of - occ.due_date).days)})"
    )


def _paid_footer(occ: PaymentOccurrence) -> str:
    late = (occ.actual_payment_date - occ.due_date).days if occ.actual_payment_date else 0
    late_text = f", с опозданием {_days(late)}" if late > 0 else ""
    who = f" · {html.escape(occ.paid_by)}" if occ.paid_by else ""
    return f"\n\n✅ <b>Оплачено {fmt_date(occ.actual_payment_date)}</b>{late_text}{who}"


def _current_message(occ: PaymentOccurrence, kind: str, sent_at: datetime) -> tuple[str, dict]:
    """Актуальный вид ранее отправленного напоминания: с кнопкой, пока не оплачено, и с отметкой после оплаты."""
    text = _render(occ, kind, _local_date(sent_at))
    if occ.status == PaymentStatus.PAID and occ.actual_payment_date:
        return text + _paid_footer(occ), NO_BUTTONS
    return text, _paid_button(occ.id)


def _occurrence_payload(occ: PaymentOccurrence) -> dict:
    return {
        "id": occ.id,
        "recurring_payment_id": occ.recurring_payment_id,
        "name": occ.recurring_payment.name,
        "amount": float(occ.amount),
        "currency": occ.currency,
        "due_date": occ.due_date.isoformat(),
        "status": occ.status,
        "actual_payment_date": occ.actual_payment_date.isoformat() if occ.actual_payment_date else None,
        "paid_by": occ.paid_by,
    }


def _collect_pending() -> list[dict]:
    """Неоплаченные периоды активных платежей, по которым ещё не было оповещения."""
    with SessionLocal() as db:
        ensure_occurrences(db)
        today = local_today()
        horizon = today + timedelta(days=settings.remind_days_before)
        base = (
            select(PaymentOccurrence)
            .join(PaymentOccurrence.recurring_payment)
            .options(contains_eager(PaymentOccurrence.recurring_payment))
            .where(RecurringPayment.is_deleted.is_(False), PaymentOccurrence.status == PaymentStatus.UNPAID)
            .order_by(PaymentOccurrence.due_date)
        )
        reminders = db.scalars(
            base.where(
                PaymentOccurrence.reminder_sent_at.is_(None),
                PaymentOccurrence.due_date >= today,
                PaymentOccurrence.due_date <= horizon,
            )
        ).all()
        overdue = db.scalars(
            base.where(PaymentOccurrence.overdue_notice_sent_at.is_(None), PaymentOccurrence.due_date < today)
        ).all()
        return [
            {
                "id": occ.id,
                "kind": kind,
                "text": _render(occ, kind, today),
                "webhook": {"event": f"payment.{kind}", "occurrence": _occurrence_payload(occ)},
            }
            for kind, items in ((REMINDER, reminders), (OVERDUE, overdue))
            for occ in items
        ]


def _sent_column(kind: str):
    return PaymentOccurrence.reminder_sent_at if kind == REMINDER else PaymentOccurrence.overdue_notice_sent_at


def _message_column(kind: str):
    return PaymentOccurrence.reminder_message_id if kind == REMINDER else PaymentOccurrence.overdue_message_id


def _claim(occ_id: int, kind: str):
    """Атомарно занимает оповещение (UPDATE ... WHERE sent_at IS NULL), чтобы даже несколько
    запущенных экземпляров бекенда не отправили одно и то же дважды. Возвращает метку или None."""
    column = _sent_column(kind)
    stamp = utcnow().replace(tzinfo=None)
    with SessionLocal() as db:
        result = db.execute(
            update(PaymentOccurrence)
            .where(
                PaymentOccurrence.id == occ_id,
                PaymentOccurrence.status == PaymentStatus.UNPAID,
                column.is_(None),
            )
            .values({column: stamp})
            .execution_options(synchronize_session=False)
        )
        db.commit()
        return stamp if result.rowcount == 1 else None


def _release(occ_id: int, kind: str, stamp) -> None:
    """Снимает отметку, если доставка не удалась, — следующая проверка повторит отправку."""
    column = _sent_column(kind)
    with SessionLocal() as db:
        db.execute(
            update(PaymentOccurrence)
            .where(PaymentOccurrence.id == occ_id, column == stamp)
            .values({column: None})
            .execution_options(synchronize_session=False)
        )
        db.commit()


def _store_message_id(occ_id: int, kind: str, message_id: int) -> None:
    with SessionLocal() as db:
        db.execute(
            update(PaymentOccurrence)
            .where(PaymentOccurrence.id == occ_id)
            .values({_message_column(kind): message_id})
            .execution_options(synchronize_session=False)
        )
        db.commit()


async def _send_webhook(payload: dict) -> bool:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(settings.webhook_url, json=payload)
        return resp.is_success
    except httpx.HTTPError as exc:
        logger.warning("Webhook failed: %s", exc)
        return False


def _telegram_ready() -> bool:
    return bot is not None and bot.can_send


async def run_reminders() -> None:
    """Проверка сроков: каждое оповещение сначала атомарно занимается в БД, при неудачной доставке отметка снимается."""
    global _warned_no_channels
    async with _run_lock:
        items = await asyncio.to_thread(_collect_pending)
        if items and not (_telegram_ready() or settings.webhook_url):
            if not _warned_no_channels:
                logger.warning("Есть %d напоминаний, но не настроены TELEGRAM_* / WEBHOOK_URL", len(items))
                _warned_no_channels = True
            return
        for item in items:
            stamp = await asyncio.to_thread(_claim, item["id"], item["kind"])
            if stamp is None:
                continue
            delivered = False
            if _telegram_ready():
                message = await bot.send_message(item["text"], reply_markup=_paid_button(item["id"]))
                if message is not None:
                    delivered = True
                    await asyncio.to_thread(_store_message_id, item["id"], item["kind"], message["message_id"])
            if settings.webhook_url:
                delivered = await _send_webhook(item["webhook"]) or delivered
            if delivered:
                logger.info("Sent %s for occurrence %s", item["kind"], item["id"])
            else:
                await asyncio.to_thread(_release, item["id"], item["kind"], stamp)


async def trigger_reminders() -> None:
    try:
        await run_reminders()
    except Exception:
        logger.exception("Reminder run failed")


async def reminder_loop() -> None:
    while True:
        await trigger_reminders()
        await asyncio.sleep(settings.reminder_check_interval_seconds)


def _event_text(occ: PaymentOccurrence, event: str, actor: str, previous_date: date | None, today: date) -> str:
    who = html.escape(actor)
    due = fmt_date(occ.due_date)
    if event == EVENT_PAID:
        late = (occ.actual_payment_date - occ.due_date).days
        late_text = f" — с опозданием {_days(late)}" if late > 0 else " — вовремя"
        return (
            f"✅ <b>Оплата подтверждена</b>\n\n{_head(occ)}\nСрок: {due}\n"
            f"Оплачено: {fmt_date(occ.actual_payment_date)}{late_text}\nОтметил: {who}"
        )
    if event == EVENT_UNPAID:
        overdue = (today - occ.due_date).days
        overdue_text = f" — просрочен на {_days(overdue)}" if overdue > 0 else ""
        return (
            f"↩️ <b>Оплата отменена</b>\n\n{_head(occ)}\nСрок: {due}{overdue_text}\n"
            f"Статус: не оплачено\nОтменил: {who}"
        )
    was_late = previous_date is not None and previous_date > occ.due_date
    late = (occ.actual_payment_date - occ.due_date).days
    if late > 0:
        verdict = f"\n⚠️ Оплата с опозданием {_days(late)}"
    elif was_late:
        verdict = "\n👌 Просрочка снята"
    else:
        verdict = ""
    previous = fmt_date(previous_date) if previous_date else "—"
    return (
        f"✏️ <b>Исправлена дата оплаты</b>\n\n{_head(occ)}\nСрок: {due}\n"
        f"Дата оплаты: {previous} → {fmt_date(occ.actual_payment_date)}{verdict}\nИсправил: {who}"
    )


def _event_context(occ_id: int, event: str, actor: str, previous_date: date | None) -> dict | None:
    with SessionLocal() as db:
        occ = db.get(PaymentOccurrence, occ_id)
        if occ is None:
            return None
        edits = []
        for kind, message_id, sent_at in (
            (REMINDER, occ.reminder_message_id, occ.reminder_sent_at),
            (OVERDUE, occ.overdue_message_id, occ.overdue_notice_sent_at),
        ):
            if message_id and sent_at:
                text, markup = _current_message(occ, kind, sent_at)
                edits.append({"message_id": message_id, "text": text, "markup": markup})
        return {
            "text": _event_text(occ, event, actor, previous_date, local_today()),
            "reply_to": occ.overdue_message_id or occ.reminder_message_id,
            "edits": edits,
            "webhook": {"event": f"payment.{event}", "actor": actor, "occurrence": _occurrence_payload(occ)},
        }


async def notify_payment_change(
    occ_id: int,
    event: str,
    actor: str,
    previous_date: date | None = None,
    extra_message_ids: Iterable[int] = (),
) -> None:
    """Сообщает в чат об изменении оплаты и обновляет ранее отправленные напоминания по этому периоду."""
    if not (_telegram_ready() or settings.webhook_url):
        return
    try:
        context = await asyncio.to_thread(_event_context, occ_id, event, actor, previous_date)
        if context is None:
            return
        if _telegram_ready():
            known = {edit["message_id"] for edit in context["edits"]}
            for edit in context["edits"]:
                await bot.edit_message(edit["message_id"], edit["text"], edit["markup"])
            for message_id in extra_message_ids:
                if message_id and message_id not in known:
                    await bot.remove_buttons(message_id)
            sent = await bot.send_message(context["text"], reply_to=context["reply_to"])
            logger.info(
                "Event %s for occurrence %s: %s, updated %d reminder(s)",
                event, occ_id, "sent" if sent else "NOT sent", len(context["edits"]),
            )
        if settings.webhook_url:
            await _send_webhook(context["webhook"])
    except Exception:
        logger.exception("Failed to notify about occurrence %s", occ_id)


HELP_TEXT = (
    "Invoice Keeper — напоминания о регулярных платежах.\n\n"
    "/upcoming — к оплате в ближайшие 30 дней\n"
    "/overdue — просроченные\n"
    "/summary — итоги по валютам\n"
    "/chatid — ID этого чата (для TELEGRAM_CHAT_ID)"
)


def _mark_paid_from_telegram(occ_id: int, who: str) -> tuple[bool, str]:
    with SessionLocal() as db:
        occ = db.get(PaymentOccurrence, occ_id)
        if occ is None:
            return False, "Платёж не найден"
        if occ.status == PaymentStatus.PAID:
            return False, "Уже отмечен как оплаченный"
        occ.status = PaymentStatus.PAID
        occ.actual_payment_date = local_today()
        occ.paid_by_id = None
        occ.paid_by = who
        log_action(
            db, None, "occurrence.paid",
            {"occurrence_id": occ.id, "actual_payment_date": occ.actual_payment_date, "via": "telegram"},
            actor=f"telegram:{who}",
        )
        db.commit()
        ensure_occurrences(db, [occ.recurring_payment])
        return True, "✅ Отмечено как оплаченное"


def _list_text(kind: str) -> str:
    with SessionLocal() as db:
        ensure_occurrences(db)
        today = local_today()
        query = (
            select(PaymentOccurrence)
            .join(PaymentOccurrence.recurring_payment)
            .options(contains_eager(PaymentOccurrence.recurring_payment))
            .where(PaymentOccurrence.status == PaymentStatus.UNPAID)
            .order_by(PaymentOccurrence.due_date)
        )
        if kind == "upcoming":
            query = query.where(
                RecurringPayment.is_deleted.is_(False),
                PaymentOccurrence.due_date >= today,
                PaymentOccurrence.due_date <= today + timedelta(days=30),
            )
            title, empty = "📅 <b>К оплате в ближайшие 30 дней</b>", "Ближайших платежей нет 🎉"
        else:
            query = query.where(PaymentOccurrence.due_date < today)
            title, empty = "⚠️ <b>Просроченные платежи</b>", "Просроченных платежей нет 🎉"
        rows = db.scalars(query).all()
        if not rows:
            return empty
        lines = [
            f"• {fmt_date(o.due_date)} — {html.escape(o.recurring_payment.name)} — "
            f"{fmt_amount(o.amount)} {o.currency}"
            for o in rows
        ]
        return title + "\n\n" + "\n".join(lines)


def _summary_text() -> str:
    with SessionLocal() as db:
        ensure_occurrences(db)
        summary = compute_summary(db)
    lines = ["📊 <b>Итоги по валютам</b>"]
    for currency, t in summary.items():
        lines.append(
            f"\n<b>{currency}</b>\nПлан: {fmt_amount(t['total_planned'])}\n"
            f"Оплачено: {fmt_amount(t['total_paid'])}\nПросрочено: {fmt_amount(t['total_overdue'])}"
        )
    return "\n".join(lines)


async def _handle_callback(cq: dict) -> None:
    message = cq.get("message") or {}
    chat_id = (message.get("chat") or {}).get("id")
    data = cq.get("data") or ""
    if not data.startswith("paid:") or not bot.is_target_chat(chat_id):
        await bot.call("answerCallbackQuery", callback_query_id=cq["id"], text="Недоступно")
        return
    sender = cq.get("from") or {}
    who = f"@{sender['username']}" if sender.get("username") else sender.get("first_name", "telegram")
    try:
        occ_id = int(data.split(":", 1)[1])
    except ValueError:
        return
    ok, text = await asyncio.to_thread(_mark_paid_from_telegram, occ_id, who)
    await bot.call("answerCallbackQuery", callback_query_id=cq["id"], text=text)
    if ok:
        await notify_payment_change(occ_id, EVENT_PAID, who, extra_message_ids=[message.get("message_id")])
    else:
        await bot.remove_buttons(message.get("message_id"), chat_id=chat_id)


async def _handle_command(message: dict) -> None:
    chat_id = message["chat"]["id"]
    command = message.get("text", "").split()[0].split("@")[0].lower()
    if command in ("/start", "/help"):
        await bot.send_message(html.escape(HELP_TEXT), chat_id=chat_id)
    elif command == "/chatid":
        await bot.send_message(f"ID этого чата: <code>{chat_id}</code>", chat_id=chat_id)
    elif command in ("/upcoming", "/overdue", "/summary"):
        if not bot.is_target_chat(chat_id):
            await bot.send_message("Этот чат не подключён к Invoice Keeper.", chat_id=chat_id)
            return
        if command == "/summary":
            text = await asyncio.to_thread(_summary_text)
        else:
            text = await asyncio.to_thread(_list_text, command[1:])
        await bot.send_message(text, chat_id=chat_id)


async def polling_loop() -> None:
    offset = None
    while True:
        updates = await bot.get_updates(offset)
        if updates is None:
            await asyncio.sleep(5)
            continue
        for update_item in updates:
            offset = update_item["update_id"] + 1
            try:
                if "callback_query" in update_item:
                    await _handle_callback(update_item["callback_query"])
                elif (update_item.get("message") or {}).get("text", "").startswith("/"):
                    await _handle_command(update_item["message"])
            except Exception:
                logger.exception("Failed to handle update %s", update_item.get("update_id"))
