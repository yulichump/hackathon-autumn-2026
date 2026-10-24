from datetime import timedelta

from app.config import local_today

API = "/api/v1"


def _create(client, headers, **kw):
    body = {"name": "Сервер", "amount": 20, "currency": "usd", "next_payment_date": str(local_today() + timedelta(days=10))}
    body.update(kw)
    return client.post(f"{API}/recurring-payments", json=body, headers=headers)


def test_requires_auth(client):
    assert client.get(f"{API}/recurring-payments").status_code == 401


def test_login_is_case_insensitive_and_wrong_password_rejected(client):
    ok = client.post(f"{API}/auth/login", json={"login": "ADMIN", "password": "admin-pass"})
    bad = client.post(f"{API}/auth/login", json={"login": "admin", "password": "nope"})
    assert ok.status_code == 200 and bad.status_code == 401


def test_logout_revokes_token(client, admin_headers):
    assert client.get(f"{API}/auth/me", headers=admin_headers).status_code == 200
    assert client.post(f"{API}/auth/logout", headers=admin_headers).status_code == 200
    assert client.get(f"{API}/auth/me", headers=admin_headers).status_code == 401


def test_user_cannot_create_or_manage(client, user_headers):
    assert _create(client, user_headers).status_code == 403
    assert client.get(f"{API}/users", headers=user_headers).status_code == 403


def test_duplicate_login_conflicts_case_insensitively(client, admin_headers):
    first = client.post(f"{API}/users", json={"login": "Anna", "password": "secret1"}, headers=admin_headers)
    second = client.post(f"{API}/users", json={"login": "anna", "password": "secret1"}, headers=admin_headers)
    assert first.status_code == 201 and second.status_code == 409


def test_create_payment_generates_first_occurrence(client, admin_headers):
    r = _create(client, admin_headers)
    assert r.status_code == 201 and r.json()["currency"] == "USD"
    occ = client.get(f"{API}/payment-occurrences", headers=admin_headers).json()
    assert len(occ) == 1 and occ[0]["status"] == "unpaid" and not occ[0]["is_overdue"]


def test_paying_creates_next_period_and_unpaying_keeps_history(client, admin_headers):
    _create(client, admin_headers)
    first = client.get(f"{API}/payment-occurrences", headers=admin_headers).json()[0]
    paid = client.patch(f"{API}/payment-occurrences/{first['id']}", json={"status": "paid"}, headers=admin_headers).json()
    assert paid["status"] == "paid" and paid["paid_by"] == "admin" and paid["actual_payment_date"] == str(local_today())
    assert len(client.get(f"{API}/payment-occurrences", headers=admin_headers).json()) == 2  # появился следующий период
    back = client.patch(f"{API}/payment-occurrences/{first['id']}", json={"status": "unpaid"}, headers=admin_headers).json()
    assert back["status"] == "unpaid" and back["paid_by"] is None and back["actual_payment_date"] is None


def test_overdue_and_late_payment(client, admin_headers):
    past = str(local_today() - timedelta(days=5))
    _create(client, admin_headers, next_payment_date=past, period="yearly")
    occ = client.get(f"{API}/payment-occurrences", headers=admin_headers).json()[0]
    assert occ["is_overdue"] and occ["days_overdue"] == 5
    paid = client.patch(f"{API}/payment-occurrences/{occ['id']}", json={"status": "paid"}, headers=admin_headers).json()
    assert paid["is_overdue"] and paid["days_overdue"] == 5  # оплачен позже срока — остаётся просрочкой
    fixed = client.patch(
        f"{API}/payment-occurrences/{occ['id']}", json={"actual_payment_date": past}, headers=admin_headers
    ).json()
    assert not fixed["is_overdue"]  # исправили дату на срок — просрочка снята


def test_future_payment_date_rejected(client, admin_headers):
    _create(client, admin_headers)
    occ = client.get(f"{API}/payment-occurrences", headers=admin_headers).json()[0]
    r = client.patch(
        f"{API}/payment-occurrences/{occ['id']}",
        json={"status": "paid", "actual_payment_date": str(local_today() + timedelta(days=1))},
        headers=admin_headers,
    )
    assert r.status_code == 422


def test_summary_is_per_currency(client, admin_headers):
    past = str(local_today() - timedelta(days=2))
    _create(client, admin_headers, name="A", amount=100, currency="RUB", next_payment_date=past, period="yearly")
    _create(client, admin_headers, name="B", amount=7.5, currency="EUR", period="yearly")
    s = client.get(f"{API}/payments/summary", headers=admin_headers).json()
    # у просроченного платежа всегда есть ещё и следующий период → неоплачено 2 × 100, из них просрочено 100
    assert s["RUB"]["total_overdue"] == 100 and s["RUB"]["total_unpaid"] == 200 and s["RUB"]["total_planned"] == 200
    assert s["EUR"]["total_planned"] == 7.5 and s["EUR"]["total_overdue"] == 0
    assert s["USD"]["total_planned"] == 0


def test_delete_keeps_history_and_drops_future(client, admin_headers):
    past = str(local_today() - timedelta(days=40))
    pid = _create(client, admin_headers, next_payment_date=past, period="monthly").json()["id"]
    before = len(client.get(f"{API}/payment-occurrences", headers=admin_headers).json())
    assert client.delete(f"{API}/recurring-payments/{pid}", headers=admin_headers).status_code == 204
    after = client.get(f"{API}/payment-occurrences", headers=admin_headers).json()
    assert 0 < len(after) <= before and all(o["recurring_payment_is_deleted"] for o in after)
    assert client.get(f"{API}/recurring-payments", headers=admin_headers).json() == []  # скрыт из списка
    assert len(client.get(f"{API}/recurring-payments?include_deleted=true", headers=admin_headers).json()) == 1


def test_deleting_user_via_api_keeps_paid_by_name(client, admin_headers, user_headers):
    _create(client, admin_headers)
    occ = client.get(f"{API}/payment-occurrences", headers=admin_headers).json()[0]
    client.patch(f"{API}/payment-occurrences/{occ['id']}", json={"status": "paid"}, headers=user_headers)
    uid = [u["id"] for u in client.get(f"{API}/users", headers=admin_headers).json() if u["login"] == "worker"][0]
    assert client.delete(f"{API}/users/{uid}", headers=admin_headers).status_code == 204
    after = client.get(f"{API}/payment-occurrences/{occ['id']}", headers=admin_headers).json()
    assert after["paid_by"] == "worker"


def test_audit_log_stores_json(client, admin_headers):
    _create(client, admin_headers)
    logs = client.get(f"{API}/audit-logs", headers=admin_headers).json()
    created = next(e for e in logs if e["action"] == "recurring.create")
    assert isinstance(created["details"], dict) and created["details"]["name"] == "Сервер"
