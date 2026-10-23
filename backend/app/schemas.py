from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, field_validator

from .models import Currency, PaymentStatus, Period, Role

Money = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]

Login = Annotated[str, Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.\-]+$")]
Password = Annotated[str, Field(min_length=6, max_length=72)]



class LoginRequest(BaseModel):
    login: str = Field(examples=["admin"])
    password: str = Field(examples=["password123"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    role: Role


class MeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    login: str
    role: Role


class MessageResponse(BaseModel):
    message: str



class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    login: str
    role: Role
    is_active: bool


class UserCreate(BaseModel):
    login: Login
    password: Password
    role: Literal[Role.USER] = Role.USER


class UserUpdate(BaseModel):
    login: Login | None = None
    password: Password | None = None
    is_active: bool | None = None



class RecurringPaymentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200, examples=["Сервер"])
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2, examples=[20.00])
    currency: Currency = Field(examples=["USD"])
    next_payment_date: date = Field(description="Дата ближайшей (первой) оплаты", examples=["2026-11-01"])
    period: Period = Period.MONTHLY

    @field_validator("currency", mode="before")
    @classmethod
    def _normalize_currency(cls, v):
        return v.upper().strip() if isinstance(v, str) else v

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Название не может быть пустым")
        return v


class RecurringPaymentOut(BaseModel):
    id: int
    name: str
    amount: Money
    currency: Currency
    next_payment_date: date | None = Field(description="Ближайший неоплаченный период (включая просроченные)")
    period: Period
    is_deleted: bool
    start_date: date
    created_at: datetime



class PaymentOccurrenceOut(BaseModel):
    id: int
    recurring_payment_id: int
    name: str
    amount: Money
    currency: Currency
    due_date: date
    status: PaymentStatus
    actual_payment_date: date | None
    is_overdue: bool = Field(description="Не оплачен и срок прошёл, либо оплачен позже срока")
    days_overdue: int
    receipt_url: str | None
    period: Period
    recurring_payment_is_deleted: bool
    reminder_sent: bool


class PaymentOccurrenceUpdate(BaseModel):
    status: PaymentStatus | None = None
    actual_payment_date: date | None = Field(
        default=None, description="Фактическая дата оплаты; при status=paid без даты подставляется сегодня"
    )
    receipt_url: str | None = Field(default=None, max_length=1000, description="Ссылка на чек")

    @field_validator("status", mode="before")
    @classmethod
    def _normalize_status(cls, v):
        return v.lower().strip() if isinstance(v, str) else v



class CurrencySummary(BaseModel):
    total_planned: Money = Decimal("0")
    total_paid: Money = Decimal("0")
    total_unpaid: Money = Decimal("0")
    total_overdue: Money = Decimal("0")


class BudgetCurrency(BaseModel):
    planned: Money = Decimal("0")
    paid: Money = Decimal("0")


class BudgetResponse(BaseModel):
    date_from: date
    date_to: date
    currencies: dict[Currency, BudgetCurrency]


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    actor: str
    action: str
    details: str | None
