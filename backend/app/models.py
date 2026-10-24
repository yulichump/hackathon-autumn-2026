"""Схема БД (PostgreSQL).

Принципы:
- все моменты времени — timestamptz (UTC), «календарные» даты — date;
- перечисления — нативные PostgreSQL ENUM;
- деньги — numeric(14, 2);
- инварианты (сумма > 0, «оплачено ⇔ есть дата оплаты» и т. д.) защищены CHECK-ограничениями в самой БД;
- внешние ключи с явным ON DELETE, индексы на всех FK и под реальные запросы (частичные там, где это выгодно);
- «мягкое» удаление платежей — одно поле deleted_at, без дублирующего флага.
Подробности — в docs/DATABASE.md.
"""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Role(StrEnum):
    ADMIN = "admin"
    USER = "user"


class Currency(StrEnum):
    RUB = "RUB"
    USD = "USD"
    EUR = "EUR"


class Period(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class PaymentStatus(StrEnum):
    PAID = "paid"
    UNPAID = "unpaid"


class NotificationKind(StrEnum):
    REMINDER = "reminder"
    OVERDUE = "overdue"


def pg_enum(enum_cls: type[StrEnum], name: str) -> Enum:
    """Нативный ENUM PostgreSQL со значениями (а не именами) членов StrEnum."""
    return Enum(enum_cls, name=name, values_callable=lambda e: [m.value for m in e], validate_strings=True)


def created_at_column() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


def updated_at_column() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        # В системе ровно один активный администратор (его задаёт .env).
        Index(
            "uq_users_single_active_admin",
            "role",
            unique=True,
            postgresql_where=text("role = 'admin' AND is_active"),
        ),
        CheckConstraint("char_length(login) >= 3", name="login_min_length"),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(always=False), primary_key=True)
    login: Mapped[str] = mapped_column(String(50))
    password_hash: Mapped[str] = mapped_column(String(100))
    role: Mapped[Role] = mapped_column(pg_enum(Role, "user_role"), default=Role.USER, server_default=Role.USER.value)
    is_active: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()


# Логин уникален без учёта регистра: «Admin» и «admin» — один и тот же человек.
Index("uq_users_login_lower", func.lower(User.login), unique=True)


class RevokedToken(Base):
    """JWT, завершённые через /auth/logout. Строки старше expires_at можно безопасно чистить."""

    __tablename__ = "revoked_tokens"

    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class RecurringPayment(Base):
    """Шаблон регулярного платежа. Конкретные сроки живут в payment_occurrences."""

    __tablename__ = "recurring_payments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint("char_length(btrim(name)) > 0", name="name_not_blank"),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(always=False), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[Currency] = mapped_column(pg_enum(Currency, "currency_code"))
    start_date: Mapped[date] = mapped_column(Date)
    period: Mapped[Period] = mapped_column(
        pg_enum(Period, "payment_period"), default=Period.MONTHLY, server_default=Period.MONTHLY.value
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    occurrences: Mapped[list["PaymentOccurrence"]] = relationship(
        back_populates="recurring_payment", order_by="PaymentOccurrence.period_index"
    )

    @hybrid_property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    @is_deleted.inplace.expression
    @classmethod
    def _is_deleted_expression(cls):
        return cls.deleted_at.is_not(None)


class PaymentOccurrence(Base):
    """Конкретный период платежа: свой срок, своя отметка об оплате.

    amount/currency — намеренный снимок на момент создания периода: если шаблон
    потом изменится, история уже созданных периодов не «поплывёт».
    """

    __tablename__ = "payment_occurrences"
    __table_args__ = (
        UniqueConstraint("recurring_payment_id", "period_index"),
        UniqueConstraint("recurring_payment_id", "due_date"),
        CheckConstraint("period_index >= 0", name="period_index_non_negative"),
        CheckConstraint("amount > 0", name="amount_positive"),
        # «оплачено» ⇔ есть фактическая дата оплаты
        CheckConstraint("(status = 'paid') = (actual_payment_date IS NOT NULL)", name="paid_iff_has_date"),
        # «кто оплатил» заполняется только у оплаченных
        CheckConstraint("status = 'paid' OR (paid_by IS NULL AND paid_by_id IS NULL)", name="paid_by_only_if_paid"),
        # Выборки «неоплаченные по сроку» — основа напоминаний, просрочек и сводок
        Index("ix_payment_occurrences_unpaid_due", "due_date", postgresql_where=text("status = 'unpaid'")),
        Index("ix_payment_occurrences_due_date", "due_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    # RESTRICT: история платежей не должна пропадать вместе с шаблоном (платежи удаляются «мягко»).
    # Отдельный индекс не нужен: FK покрывает UNIQUE (recurring_payment_id, period_index).
    recurring_payment_id: Mapped[int] = mapped_column(ForeignKey("recurring_payments.id", ondelete="RESTRICT"))
    period_index: Mapped[int] = mapped_column(Integer)
    due_date: Mapped[date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[Currency] = mapped_column(pg_enum(Currency, "currency_code"))
    status: Mapped[PaymentStatus] = mapped_column(
        pg_enum(PaymentStatus, "payment_status"),
        default=PaymentStatus.UNPAID,
        server_default=PaymentStatus.UNPAID.value,
    )
    actual_payment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    receipt_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    # Пользователь системы (если оплату отметили в вебе) — ссылка, пропадающая при удалении пользователя…
    paid_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    # …и отображаемое имя-снимок: логин либо @username из Telegram — остаётся навсегда.
    paid_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()

    recurring_payment: Mapped[RecurringPayment] = relationship(back_populates="occurrences")
    notifications: Mapped[list["PaymentNotification"]] = relationship(
        back_populates="occurrence", cascade="all, delete-orphan", passive_deletes=True
    )


class PaymentNotification(Base):
    """Журнал отправленных оповещений: не более одного на (период, вид).

    Уникальность — это и есть защита от дублей: «занять» оповещение = INSERT ... ON CONFLICT DO NOTHING,
    что атомарно даже при нескольких запущенных экземплярах бэкенда.
    """

    __tablename__ = "payment_notifications"
    __table_args__ = (UniqueConstraint("occurrence_id", "kind"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    occurrence_id: Mapped[int] = mapped_column(ForeignKey("payment_occurrences.id", ondelete="CASCADE"))
    kind: Mapped[NotificationKind] = mapped_column(pg_enum(NotificationKind, "notification_kind"))
    sent_at: Mapped[datetime] = created_at_column()
    # id сообщения в Telegram — чтобы потом обновить его (кнопка «Оплачено», отметка об оплате)
    telegram_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    occurrence: Mapped[PaymentOccurrence] = relationship(back_populates="notifications")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_action_created_at", "action", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    actor: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(50))
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
