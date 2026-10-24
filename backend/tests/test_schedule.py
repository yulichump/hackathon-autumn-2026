from datetime import date

import pytest

from app.models import Period
from app.payments import add_months, due_date_for


def test_add_months_clamps_to_last_day():
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_months(date(2028, 1, 31), 1) == date(2028, 2, 29)  # високосный год
    assert add_months(date(2026, 1, 31), 2) == date(2026, 3, 31)  # не «сползает» к 28-му


@pytest.mark.parametrize(
    ("period", "index", "expected"),
    [
        (Period.DAILY, 3, date(2026, 1, 4)),
        (Period.WEEKLY, 2, date(2026, 1, 15)),
        (Period.MONTHLY, 1, date(2026, 2, 1)),
        (Period.QUARTERLY, 1, date(2026, 4, 1)),
        (Period.YEARLY, 1, date(2027, 1, 1)),
    ],
)
def test_due_date_for(period, index, expected):
    assert due_date_for(date(2026, 1, 1), period, index) == expected


def test_due_dates_are_strictly_increasing_so_unique_constraint_holds():
    for period in Period:
        for start in (date(2024, 2, 29), date(2026, 1, 31), date(2026, 12, 31)):
            dates = [due_date_for(start, period, i) for i in range(60)]
            assert len(set(dates)) == 60 and dates == sorted(dates)
