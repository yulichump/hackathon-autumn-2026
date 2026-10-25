# Invoice Keeper — API (исправленная версия ТЗ для фронтенда)

Все эндпоинты под префиксом `/api/v1`. Все, кроме `POST /auth/login`, `GET /docs` и `GET /health`, требуют заголовок
`Authorization: Bearer <access_token>`. Без токена → `401`, не та роль → `403`. Ошибки: `{"detail": "текст"}`
(у ошибок валидации `422` поле `detail` — массив).

Даты — `YYYY-MM-DD`, суммы — числа (`50000.0`), валюты — только `RUB`, `USD`, `EUR`.

## Что было исправлено в «хакатон. начало.docx»

| # | Было в документе | Как правильно (по ТЗ Aeza) |
|---|---|---|
| 1 | У списков платежей/периодов/итогов «Доступ: Все» | Только авторизованные (admin и user). Без авторизации данные недоступны — критерий приёмки |
| 2 | `PATCH /payment-occurrences/{id}` — «исправить дату» | Исправляется только **фактическая** дата оплаты. Срок (`due_date`) не меняется, просрочка пересчитывается |
| 3 | `POST /users` принимает `role` | Создаются только обычные пользователи. Админ один, задаётся в `.env`, через API его не создать/изменить/удалить (`403`) |
| 4 | Пример периода: срок `2026-11-01` и `is_overdue: true` | Просрочка — со **следующего дня** после срока; оплата в день срока — вовремя. Пример противоречивый |
| 5 | Нет правил для `is_overdue` у оплаченного периода | Оплачен позже срока → `is_overdue: true`; исправили дату на срок или раньше → `false` |
| 6 | `{"status": "unpaid", "actual_payment_date": null}` | При отмене оплаты дата очищается всегда (даже если её не прислали) |
| 7 | Не указаны допустимые валюты и периоды | Валюты: `RUB`, `USD`, `EUR`. Период: `monthly` (обязательный), плюс `daily`, `weekly`, `quarterly`, `yearly` |
| 8 | Фильтры у списка периодов упомянуты, но не описаны | Описаны ниже (query-параметры) |
| 9 | Не описаны ответы `POST/PATCH /users` | Возвращают объект пользователя |
| 10 | Нумерация разделов сбита (1, 2, без номера, 6) | Разделы перенумерованы |
| 11 | Нет Telegram-бота и OpenAPI-файла | Бот — на бекенде; спецификация в `docs/openapi.json` и `docs/openapi.yml` |

## 1. Авторизация

| Метод | Путь | Доступ | Тело / ответ |
|---|---|---|---|
| POST | `/auth/login` | все | `{"login","password"}` → `{"access_token","token_type":"bearer","role"}`; `401` неверный пароль, `403` пользователь отключён |
| GET | `/auth/me` | авторизованные | `{"id","login","role"}` |
| POST | `/auth/logout` | авторизованные | `{"message":"Successfully logged out"}`; токен перестаёт работать |

## 2. Регулярные платежи

| Метод | Путь | Доступ |
|---|---|---|
| GET | `/recurring-payments?include_deleted=false` | авторизованные |
| GET | `/recurring-payments/{id}` | авторизованные |
| POST | `/recurring-payments` | admin |
| PATCH | `/recurring-payments/{id}` | admin |
| DELETE | `/recurring-payments/{id}` | admin → `204` |
| POST | `/recurring-payments/{id}/restore` | admin |

Создание:
```json
{"name": "Сервер", "amount": 20.00, "currency": "USD", "next_payment_date": "2026-11-01", "period": "monthly"}
```
Ответ (`201`):
```json
{"id": 1, "name": "Сервер", "amount": 20.0, "currency": "USD", "next_payment_date": "2026-11-01",
 "period": "monthly", "is_deleted": false, "start_date": "2026-11-01", "created_at": "..."}
```
`next_payment_date` в ответе — ближайший **неоплаченный** период (в том числе просроченный).
Удаление — мягкое: `is_deleted = true`, напоминания прекращаются, прошлые периоды остаются в истории.

Изменение (`PATCH`) — любое подмножество полей создания:
```json
{"amount": 25.00, "next_payment_date": "2026-12-05", "period": "monthly"}
```
- затрагиваются только будущие неоплаченные периоды (срок сегодня и позже); прошлые, просроченные и оплаченные
  не меняются — у них остаются прежние сумма и валюта;
- смена `next_payment_date` или `period` пересоздаёт будущие периоды по новому расписанию;
  новая дата должна быть позже последнего сохранённого периода, иначе `409`;
- прекращённый платёж редактировать нельзя (`409`) — сначала восстановите его.

Восстановление (`POST .../restore`) возвращает платёж в работу: снова появляются периоды и напоминания.
Сроки, прошедшие, пока платёж был прекращён, не создаются — расписание продолжается с ближайшей даты
не раньше сегодняшней. Для активного платежа ничего не меняет. Ответ — объект платежа.

## 3. Периоды оплаты

| Метод | Путь | Доступ |
|---|---|---|
| GET | `/payment-occurrences` | авторизованные |
| GET | `/payment-occurrences/{id}` | авторизованные |
| PATCH | `/payment-occurrences/{id}` | авторизованные (admin и user) |

Фильтры `GET /payment-occurrences`: `status=paid|unpaid`, `currency=RUB|USD|EUR`, `is_overdue=true|false`,
`recurring_payment_id`, `date_from`, `date_to` (по сроку), `include_deleted=true|false`. Сортировка по сроку.

Объект:
```json
{"id": 101, "recurring_payment_id": 1, "name": "Аренда офиса", "amount": 50000.0, "currency": "RUB",
 "due_date": "2026-11-01", "status": "unpaid", "actual_payment_date": null, "is_overdue": false,
 "days_overdue": 0, "paid_by": null, "receipt_url": null, "period": "monthly",
 "recurring_payment_is_deleted": false, "reminder_sent": false}
```
`paid_by` — кто отметил оплату: логин из панели или `@username` из Telegram (`null`, пока не оплачено).

PATCH:
- отметить оплату: `{"status": "paid", "actual_payment_date": "2026-10-30"}` (без даты → сегодня; дата в будущем → `422`)
- отменить оплату: `{"status": "unpaid"}` → `actual_payment_date` очищается
- исправить фактическую дату: `{"actual_payment_date": "2026-10-28"}`
- приложить чек: `{"receipt_url": "https://..."}`

Каждое изменение статуса или фактической даты отправляет событие в Telegram-чат (и на `WEBHOOK_URL`, если задан:
`payment.paid`, `payment.unpaid`, `payment.date_changed`).

У активного платежа всегда есть следующий период: после оплаты текущего сразу появляется следующий со своим статусом.

## 4. Итоги

`GET /payments/summary?date_from=&date_to=` — по каждой валюте отдельно, всегда все три валюты:
```json
{"RUB": {"total_planned": 50000.0, "total_paid": 0.0, "total_unpaid": 50000.0, "total_overdue": 50000.0},
 "USD": {...}, "EUR": {...}}
```
`total_overdue` — неоплаченные периоды с прошедшим сроком.

`GET /payments/budget?year=2026&month=11` — бюджет на месяц (без `month` — на год): `planned` и `paid` по валютам.

## 5. Пользователи (только admin)

| Метод | Путь | Тело | Ответ |
|---|---|---|---|
| GET | `/users` | — | `[{"id","login","role":"user","is_active"}]` (админ в списке не показывается) |
| POST | `/users` | `{"login","password"}` (`role` можно не слать, только `"user"`) | `201` + пользователь; `409` логин занят |
| PATCH | `/users/{id}` | любые из `{"login","password","is_active"}` | пользователь |
| DELETE | `/users/{id}` | — | `204` |

Логин: 3–50 символов `A-Z a-z 0-9 _ . -`; пароль: 6–72 символа.

## 6. Прочее

- `GET /docs` — Swagger UI, `GET /openapi.json` — схема, `GET /redoc`
- `GET /audit-logs?limit=100` — журнал входов и действий (admin); `details` — JSON-объект или `null`
- `GET /health`
