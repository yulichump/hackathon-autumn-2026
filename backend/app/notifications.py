"""Напоминания (Telegram + webhook) и обработка команд/кнопок бота."""

import asyncio
import html
import logging
from datetime import date, timedelta
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

_run_lock = asyncio.Lock()
_warned_no_channels = False


def fmt_amount(amount) -> str:
    return f"{Decimal(amount):,.2f}".replace(",", " ")


def fmt_date(d: date) -> str:
    return d.strftime("%d.%m.%Y")


def _when(days: int) -> str:
    if days == 0:
        return "сегодня"
    if days == 1:
        return "завтра"
    return f"через {days} дн."


def _paid_button(occ_id: int) -> dict:
    return {"inline_keyboard": [[{"text": "✅ Оплачено", "callback_data": f"paid:{occ_id}"}]]}


def _render(occ: PaymentOccurrence, kind: str, today: date) -> str:
    name = html.escape(occ.recurring_payment.name)
    amount = f"{fmt_amount(occ.amount)} {occ.currency}"
    if kind == REMINDER:
        return (
            "🔔 <b>Напоминание об оплате</b>\n\n"
            f"<b>{name}</b>\n"
            f"Сумма: {amount}\n"
            f"Срок оплаты: {fmt_date(occ.due_date)} ({_when((occ.due_date - today).days)})"
        )
    return (
        "⚠️ <b>Платёж просрочен</b>\n\n"
        f"<b>{name}</b>\n"
        f"Сумма: {amount}\n"
        f"Срок оплаты был: {fmt_date(occ.due_date)} (просрочка {(today - occ.due_date).days} дн.)"
    )


def _webhook_payload(occ: PaymentOccurrence, kind: str) -> dict:
    return {
        "event": f"payment.{kind}",
        "occurrence": {
            "id": occ.id,
            "recurring_payment_id": occ.recurring_payment_id,
            "name": occ.recurring_payment.name,
            "amount": float(occ.amount),
            "currency": occ.currency,
            "due_date": occ.due_date.isoformat(),
        },
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
            {"id": occ.id, "kind": kind, "text": _render(occ, kind, today), "webhook": _webhook_payload(occ, kind)}
            for kind, items in ((REMINDER, reminders), (OVERDUE, overdue))
            for occ in items
        ]


def _sent_column(kind: str):
    return PaymentOccurrence.reminder_sent_at if kind == REMINDER else PaymentOccurrence.overdue_notice_sent_at


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


async def _send_webhook(payload: dict) -> bool:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(settings.webhook_url, json=payload)
        return resp.is_success
    except httpx.HTTPError as exc:
        logger.warning("Webhook failed: %s", exc)
        return False


async def run_reminders() -> None:
    """Проверка сроков: каждое оповещение сначала атомарно занимается в БД, при неудачной доставке отметка снимается."""
    global _warned_no_channels
    async with _run_lock:
        items = await asyncio.to_thread(_collect_pending)
        has_telegram = bot is not None and bot.can_send
        if items and not (has_telegram or settings.webhook_url):
            if not _warned_no_channels:
                logger.warning("Есть %d напоминаний, но не настроены TELEGRAM_* / WEBHOOK_URL", len(items))
                _warned_no_channels = True
            return
        for item in items:
            stamp = await asyncio.to_thread(_claim, item["id"], item["kind"])
            if stamp is None:
                continue
            delivered = False
            if has_telegram:
                markup = _paid_button(item["id"])
                delivered = await bot.send_message(item["text"], reply_markup=markup)
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
        log_action(
            db, None, "occurrence.paid",
            {"occurrence_id": occ.id, "actual_payment_date": occ.actual_payment_date, "via": "telegram"},
            actor=f"telegram:{who}",
        )
        db.commit()
        ensure_occurrences(db, [occ.recurring_payment])
        return True, (
            f"✅ «{occ.recurring_payment.name}» за {fmt_date(occ.due_date)} отмечен оплаченным "
            f"({fmt_date(occ.actual_payment_date)}, {who})"
        )


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
    await bot.call("answerCallbackQuery", callback_query_id=cq["id"], text=text[:200])
    await bot.call(
        "editMessageReplyMarkup", chat_id=chat_id, message_id=message.get("message_id"),
        reply_markup={"inline_keyboard": []},
    )
    if ok:
        await bot.send_message(html.escape(text), chat_id=chat_id)


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
        for update in updates:
            offset = update["update_id"] + 1
            try:
                if "callback_query" in update:
                    await _handle_callback(update["callback_query"])
                elif (update.get("message") or {}).get("text", "").startswith("/"):
                    await _handle_command(update["message"])
            except Exception:
                logger.exception("Failed to handle update %s", update.get("update_id"))
