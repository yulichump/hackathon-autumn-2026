from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .config import utcnow
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


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    login: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(10), default=Role.USER)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class RevokedToken(Base):
    """Токены, завершённые через /auth/logout."""

    __tablename__ = "revoked_tokens"

    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)


class RecurringPayment(Base):
    __tablename__ = "recurring_payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3))
    start_date: Mapped[date] = mapped_column(Date)
    period: Mapped[str] = mapped_column(String(10), default=Period.MONTHLY)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    occurrences: Mapped[list["PaymentOccurrence"]] = relationship(
        back_populates="recurring_payment", order_by="PaymentOccurrence.period_index"
    )


class PaymentOccurrence(Base):
    """Конкретный период регулярного платежа: своя дата и своя отметка об оплате."""

    __tablename__ = "payment_occurrences"
    __table_args__ = (UniqueConstraint("recurring_payment_id", "period_index"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    recurring_payment_id: Mapped[int] = mapped_column(ForeignKey("recurring_payments.id"), index=True)
    period_index: Mapped[int] = mapped_column(Integer)
    due_date: Mapped[date] = mapped_column(Date, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(10), default=PaymentStatus.UNPAID, index=True)
    actual_payment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    receipt_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    paid_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    paid_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    overdue_notice_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reminder_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    overdue_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    recurring_payment: Mapped[RecurringPayment] = relationship(back_populates="occurrences")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actor: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(50))
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
