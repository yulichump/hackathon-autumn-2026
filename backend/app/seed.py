from datetime import timedelta

from sqlalchemy import select

from .bootstrap import sync_admin
from .config import local_today
from .db import SessionLocal, init_db
from .models import PaymentOccurrence, PaymentStatus, Period, RecurringPayment, Role, User
from .payments import add_months, ensure_occurrences
from .security import hash_password

DEMO_USERS = [("user1", "user1pass"), ("user2", "user2pass")]


def seed() -> None:
    init_db()
    sync_admin()
    today = local_today()
    with SessionLocal() as db:
        for login, password in DEMO_USERS:
            if not db.scalar(select(User).where(User.login == login)):
                db.add(User(login=login, password_hash=hash_password(password), role=Role.USER))

        if db.scalar(select(RecurringPayment.id).limit(1)) is None:
            demo = [
                ("Аренда офиса", "50000.00", "RUB", add_months(today, -2).replace(day=1), Period.MONTHLY),
                ("Сервер Aeza", "20.00", "USD", today + timedelta(days=2), Period.MONTHLY),
                ("Подписка на сервис", "15.00", "EUR", today + timedelta(days=10), Period.MONTHLY),
                ("Домен", "1500.00", "RUB", today - timedelta(days=5), Period.YEARLY),
            ]
            payments = []
            for name, amount, currency, start, period in demo:
                payment = RecurringPayment(name=name, amount=amount, currency=currency, start_date=start, period=period)
                db.add(payment)
                payments.append(payment)
            db.commit()
            ensure_occurrences(db, payments)

            rent_first = db.scalar(
                select(PaymentOccurrence)
                .where(PaymentOccurrence.recurring_payment_id == payments[0].id)
                .order_by(PaymentOccurrence.period_index)
            )
            rent_first.status = PaymentStatus.PAID
            rent_first.actual_payment_date = rent_first.due_date
            db.commit()
            ensure_occurrences(db, payments)
        db.commit()
    print("Тестовые данные готовы. Пользователи:", ", ".join(f"{u}/{p}" for u, p in DEMO_USERS))


if __name__ == "__main__":
    seed()
