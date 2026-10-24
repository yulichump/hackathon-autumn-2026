# Invoice Keeper

Напоминания о регулярных платежах: веб-панель (React + MUI), API (FastAPI + PostgreSQL) и Telegram-бот.

- `backend/` — API, база, напоминания в Telegram. Подробно: [backend/README.md](backend/README.md), описание API — [backend/API.md](backend/API.md).
- `frontend/` — веб-панель.

## Запуск

Нужны Python 3.11+, Node.js 20+ и PostgreSQL 14+ (или Docker).

### 1. Бекенд

Быстрый старт через Docker (PostgreSQL + бэкенд, миграции применяются сами), из корня репозитория:

```bash
docker compose up --build
```

Тестовые данные: `docker compose exec backend python -m app.seed`.

Либо вручную (нужен запущенный PostgreSQL; можно поднять только его: `docker compose up -d db`):

```bash
cd backend
```

```bash
python -m venv .venv
```

Windows: `.venv\Scripts\activate`, Linux/macOS: `source .venv/bin/activate`

```bash
pip install -r requirements.txt
```

Скопируйте `.env.example` в `.env` и заполните (адрес БД, админ, `SECRET_KEY`, токен бота и ID чата).

```bash
alembic upgrade head
python -m app.seed
```

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Swagger: http://localhost:8000/api/v1/docs. Схема БД: [backend/docs/DATABASE.md](backend/docs/DATABASE.md).

### 2. Фронтенд

Во втором терминале:

```bash
cd frontend
```

```bash
npm ci
```

```bash
npm run dev -- --host 127.0.0.1
```

Панель: http://127.0.0.1:5173. Запросы `/api/*` dev-сервер Vite проксирует на `http://127.0.0.1:8000`
(другой адрес — переменная `VITE_BACKEND_URL`). Если фронтенд и API на разных доменах, задайте `VITE_API_URL`,
например `https://api.example.com/api/v1`.

### Учётные записи

- администратор — `ADMIN_LOGIN` / `ADMIN_PASSWORD` из `backend/.env`;
- пользователи из тестовых данных — `user1 / user1pass`, `user2 / user2pass`.
