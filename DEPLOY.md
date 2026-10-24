# Деплой на VPS через Docker

Продакшен-стек (`docker-compose.prod.yml`) — три контейнера:

| Сервис | Что делает | Наружу |
|---|---|---|
| `db` | PostgreSQL 16, данные в томе `pgdata` | закрыт |
| `backend` | FastAPI + Telegram-бот, при старте применяет миграции | закрыт |
| `web` | Caddy: отдаёт собранный фронтенд, проксирует `/api/*` на бекенд, сам получает HTTPS-сертификат | 80, 443 |

Фронтенд и API живут на одном адресе, поэтому CORS не нужен. Логи контейнеров ротируются (3 × 10 МБ).

Требования к серверу: Ubuntu 22.04/24.04, 1 vCPU, 2 ГБ RAM, 20+ ГБ диска.

## 1. Подготовка сервера

Подключитесь по SSH (`ssh root@IP_СЕРВЕРА`) и выполните:

```bash
apt update && apt upgrade -y
```

```bash
curl -fsSL https://get.docker.com | sh
```

Swap на 2 ГБ — чтобы сборка фронтенда не упёрлась в память:

```bash
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile && echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

Файрвол: открыты только SSH, HTTP и HTTPS.

```bash
ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443/tcp && ufw allow 443/udp && ufw --force enable
```

## 2. Код

```bash
git clone https://github.com/yulichump/hackathon-autumn-2026.git
```

```bash
cd hackathon-autumn-2026
```

Пока ветка не влита в `master`:

```bash
git switch postgresql-docker
```

Если репозиторий приватный, при клонировании GitHub попросит логин и [personal access token](https://github.com/settings/tokens) вместо пароля.

## 3. Настройки

Два файла, оба не попадают в git.

**`.env` в корне** — параметры инфраструктуры:

```bash
cp .env.example .env
```

```bash
sed -i "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$(openssl rand -hex 24)/" .env
```

- `SITE_ADDRESS=:80` — сайт по `http://IP_СЕРВЕРА`. Когда появится домен, см. раздел 6.
- `COMPOSE_FILE=docker-compose.prod.yml` — благодаря этому все команды ниже пишутся просто `docker compose ...`.

**`backend/.env`** — настройки приложения:

```bash
cp backend/.env.example backend/.env
```

```bash
sed -i "s/^SECRET_KEY=.*/SECRET_KEY=$(openssl rand -hex 32)/" backend/.env
```

```bash
nano backend/.env
```

Заполните `ADMIN_LOGIN`, `ADMIN_PASSWORD`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`. `DATABASE_URL` трогать не нужно — compose подставляет адрес базы сам.

## 4. Запуск

Если бекенд с этим же токеном бота запущен где-то ещё (например, локально) — остановите его: Telegram отдаёт кнопки и команды только одному экземпляру.

```bash
docker compose up -d --build
```

Первая сборка занимает несколько минут. Проверка:

```bash
docker compose ps
```

```bash
curl http://localhost/api/v1/health
```

Все три сервиса должны быть `Up`, `backend` — `healthy`, а health-check вернуть `{"status":"ok"}`.
Панель: `http://IP_СЕРВЕРА`, Swagger: `http://IP_СЕРВЕРА/api/v1/docs`.

## 5. Данные

**Вариант А — чистая база с тестовыми данными:**

```bash
docker compose exec backend python -m app.seed
```

**Вариант Б — перенести текущую локальную базу.**

На своём компьютере, в папке проекта (локальный PostgreSQL должен быть запущен: `docker compose up -d db`):

```bash
docker compose exec db pg_dump -U invoice -Fc -f /tmp/invoice_keeper.dump invoice_keeper
```

```bash
docker compose cp db:/tmp/invoice_keeper.dump ./invoice_keeper.dump
```

```bash
scp invoice_keeper.dump root@IP_СЕРВЕРА:~/hackathon-autumn-2026/
```

На сервере:

```bash
docker compose stop backend
```

```bash
docker compose cp invoice_keeper.dump db:/tmp/invoice_keeper.dump
```

```bash
docker compose exec db pg_restore -U invoice -d invoice_keeper --clean --if-exists --no-owner /tmp/invoice_keeper.dump
```

```bash
docker compose start backend
```

Дамп копируется через `docker compose cp`, а не перенаправлением `>`: в PowerShell `>` портит бинарные файлы.

## 6. Домен и HTTPS

1. У регистратора домена создайте A-запись `invoice.example.com → IP_СЕРВЕРА`.
2. Дождитесь, пока `ping invoice.example.com` покажет IP сервера.
3. В корневом `.env`: `SITE_ADDRESS=invoice.example.com`.
4. Пересоздайте веб-контейнер:

```bash
docker compose up -d web
```

Caddy сам получит и будет продлевать сертификат Let's Encrypt (для этого нужны открытые порты 80 и 443). HTTP будет перенаправлять на HTTPS.

## 7. Обновление

```bash
git pull
```

```bash
docker compose up -d --build
```

Миграции базы применяются при старте бекенда. Старые образы иногда стоит чистить: `docker image prune -f`.

## 8. Бэкапы

Ежедневный дамп в 03:00 с хранением 14 дней:

```bash
mkdir -p /root/backups
```

```bash
crontab -e
```

Добавьте строку:

```
0 3 * * * cd /root/hackathon-autumn-2026 && docker compose exec -T db pg_dump -U invoice -Fc invoice_keeper > /root/backups/invoice_keeper_$(date +\%F).dump && find /root/backups -name '*.dump' -mtime +14 -delete
```

Восстановление — как в разделе 5, вариант Б (шаги на сервере).

## 9. Обслуживание

| Задача | Команда |
|---|---|
| Статус | `docker compose ps` |
| Логи бекенда | `docker compose logs -f backend` |
| Логи Caddy | `docker compose logs -f web` |
| Перезапуск бекенда (после правки `backend/.env`) | `docker compose up -d backend` |
| Консоль PostgreSQL | `docker compose exec db psql -U invoice invoice_keeper` |
| Остановить всё | `docker compose down` (данные сохраняются; `down -v` удалит и базу) |

## Если что-то не так

- **502 Bad Gateway** сразу после запуска — бекенд ещё стартует, подождите 20–30 секунд. Если не проходит — `docker compose logs backend`.
- **`Conflict: terminated by other getUpdates request`** в логах — этим токеном бота пользуется ещё один бекенд. Остановите лишний.
- **Бот перестал писать в группу** — группа могла стать супергруппой и сменить ID. Бот перейдёт на новый сам и напишет в логе нужный `TELEGRAM_CHAT_ID`; пропишите его в `backend/.env` и выполните `docker compose up -d backend`.
- **Нет HTTPS** — проверьте A-запись домена и что порты 80/443 открыты (`ufw status`), затем `docker compose logs web`.
