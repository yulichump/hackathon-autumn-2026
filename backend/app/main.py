import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import notifications
from .bootstrap import prepare_data
from .config import settings
from .db import check_connection, upgrade_head
from .routers import auth, occurrences, recurring, summary, users
from .telegram import TelegramBot

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("app")

API_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.auto_migrate:
        upgrade_head()
    check_connection()
    prepare_data()

    tasks = []
    if settings.telegram_bot_token:
        notifications.bot = TelegramBot(settings.telegram_bot_token, settings.telegram_chat_id)
        tasks.append(asyncio.create_task(notifications.polling_loop()))
        if not settings.telegram_chat_id:
            logger.warning("TELEGRAM_CHAT_ID не задан: отправьте боту /chatid в нужном чате и пропишите ID в .env")
    else:
        logger.warning("TELEGRAM_BOT_TOKEN не задан: напоминания в Telegram отключены")
    tasks.append(asyncio.create_task(notifications.reminder_loop()))

    yield

    for task in tasks:
        task.cancel()
    for task in tasks:
        with contextlib.suppress(asyncio.CancelledError):
            await task
    if notifications.bot is not None:
        await notifications.bot.close()
        notifications.bot = None


app = FastAPI(
    title="Invoice Keeper API",
    description="Напоминания о регулярных платежах: периоды оплат, просрочки, итоги по валютам, Telegram-бот.",
    version="1.0.0",
    docs_url=f"{API_PREFIX}/docs",
    redoc_url=f"{API_PREFIX}/redoc",
    openapi_url=f"{API_PREFIX}/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (auth, recurring, occurrences, summary, users):
    app.include_router(module.router, prefix=API_PREFIX)


@app.get(f"{API_PREFIX}/health", tags=["System"], summary="Проверка работоспособности")
def health():
    return {"status": "ok"}
