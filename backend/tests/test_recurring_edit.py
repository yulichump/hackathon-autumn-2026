from datetime import timedelta

from sqlalchemy import delete, select

from app.config import local_today
from app.models import PaymentOccurrence, PaymentStatus

API = "/api/v1"


def _create(client, headers, days_from_today, **kw):
    body = {
        "name": "Аренда",
        "amount": 20,
        "currency": "RUB",
        "next_payment_date": str(local_today() + timedelta(days=days_from_today)),
        "period": "monthly",
    }
    body.update(kw)
    response = client.post(f"{API}/recurring-payments", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def _occurrences(client, headers, payment_id):
    response = client.get(f"{API}/payment-occurrences", params={"recurring_payment_id": payment_id}, headers=headers)
    return sorted(response.json(), key=lambda o: o["due_date"])


def test_edit_money_changes_only_future_unpaid_periods(client, admin_headers):
    payment = _create(client, admin_headers, -40)
    before = _occurrences(client, admin_headers, payment["id"])
    past_ids = {o["id"] for o in before if o["due_date"] < str(local_today())}
    assert past_ids

    r = client.patch(
        f"{API}/recurring-payments/{payment['id']}",
        json={"name": "Аренда офиса", "amount": 99.5, "currency": "eur"},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Аренда офиса" and r.json()["amount"] == 99.5 and r.json()["currency"] == "EUR"

    for occ in _occurrences(client, admin_headers, payment["id"]):
        if occ["id"] in past_ids:
            assert (occ["amount"], occ["currency"]) == (20, "RUB")
        else:
            assert (occ["amount"], occ["currency"]) == (99.5, "EUR")
        assert occ["name"] == "Аренда офиса"


def test_edit_schedule_rebuilds_future_and_keeps_history(client, admin_headers):
    payment = _create(client, admin_headers, -40)
    history = [o for o in _occurrences(client, admin_headers, payment["id"]) if o["due_date"] < str(local_today())]
    new_date = local_today() + timedelta(days=20)

    r = client.patch(
        f"{API}/recurring-payments/{payment['id']}",
        json={"next_payment_date": str(new_date), "period": "weekly"},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["period"] == "weekly"

    after = _occurrences(client, admin_headers, payment["id"])
    assert [o["id"] for o in after[: len(history)]] == [o["id"] for o in history]
    future = after[len(history):]
    assert future and future[0]["due_date"] == str(new_date)


def test_paying_after_reschedule_continues_new_cadence(client, admin_headers):
    payment = _create(client, admin_headers, 5)
    new_date = local_today() + timedelta(days=9)
    client.patch(
        f"{API}/recurring-payments/{payment['id']}",
        json={"next_payment_date": str(new_date), "period": "weekly"},
        headers=admin_headers,
    )
    first = _occurrences(client, admin_headers, payment["id"])[0]
    client.patch(f"{API}/payment-occurrences/{first['id']}", json={"status": "paid"}, headers=admin_headers)

    dates = [o["due_date"] for o in _occurrences(client, admin_headers, payment["id"])]
    assert dates == [str(new_date), str(new_date + timedelta(weeks=1))]


def test_schedule_cannot_overlap_kept_periods(client, admin_headers):
    payment = _create(client, admin_headers, -40)
    r = client.patch(
        f"{API}/recurring-payments/{payment['id']}",
        json={"next_payment_date": str(local_today() - timedelta(days=60))},
        headers=admin_headers,
    )
    assert r.status_code == 409
    assert len(_occurrences(client, admin_headers, payment["id"])) >= 2


def test_user_cannot_edit_or_restore(client, admin_headers, user_headers):
    payment = _create(client, admin_headers, 10)
    assert client.patch(f"{API}/recurring-payments/{payment['id']}", json={"amount": 1}, headers=user_headers).status_code == 403
    assert client.post(f"{API}/recurring-payments/{payment['id']}/restore", headers=user_headers).status_code == 403


def test_deleted_payment_must_be_restored_before_edit(client, admin_headers):
    payment = _create(client, admin_headers, 10)
    client.delete(f"{API}/recurring-payments/{payment['id']}", headers=admin_headers)
    r = client.patch(f"{API}/recurring-payments/{payment['id']}", json={"amount": 5}, headers=admin_headers)
    assert r.status_code == 409


def test_restore_resumes_without_backfilling_skipped_periods(client, admin_headers, db):
    payment = _create(client, admin_headers, -100)
    client.delete(f"{API}/recurring-payments/{payment['id']}", headers=admin_headers)
    first = db.scalar(
        select(PaymentOccurrence)
        .where(PaymentOccurrence.recurring_payment_id == payment["id"])
        .order_by(PaymentOccurrence.period_index)
    )
    db.execute(
        delete(PaymentOccurrence).where(
            PaymentOccurrence.recurring_payment_id == payment["id"], PaymentOccurrence.id != first.id
        )
    )
    db.commit()

    r = client.post(f"{API}/recurring-payments/{payment['id']}/restore", headers=admin_headers)
    assert r.status_code == 200 and r.json()["is_deleted"] is False

    occurrences = _occurrences(client, admin_headers, payment["id"])
    assert occurrences[0]["id"] == first.id
    resumed = occurrences[1:]
    assert resumed and all(o["due_date"] >= str(local_today()) for o in resumed)
    assert resumed[0]["status"] == PaymentStatus.UNPAID
    listed = client.get(f"{API}/recurring-payments", headers=admin_headers).json()
    assert payment["id"] in {p["id"] for p in listed}


def test_restore_active_payment_is_noop(client, admin_headers):
    payment = _create(client, admin_headers, 10)
    before = _occurrences(client, admin_headers, payment["id"])
    r = client.post(f"{API}/recurring-payments/{payment['id']}/restore", headers=admin_headers)
    assert r.status_code == 200
    assert _occurrences(client, admin_headers, payment["id"]) == before
