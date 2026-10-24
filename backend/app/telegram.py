"""Минимальный клиент Telegram Bot API (long polling) на httpx."""

import logging
from urllib.parse import urlsplit

import httpx

logger = logging.getLogger("telegram")

NOT_MODIFIED = "message is not modified"
DEFAULT_API_URL = "https://api.telegram.org"


def describe_route(api_url: str, proxy: str) -> str:
    """Куда реально уходят запросы к Bot API — без логинов и паролей прокси, для логов."""
    target = urlsplit(api_url).netloc or api_url
    if not proxy:
        return target
    parts = urlsplit(proxy)
    return f"{target} через прокси {parts.scheme}://{parts.hostname}:{parts.port or ''}".rstrip(":")


class TelegramBot:
    def __init__(self, token: str, chat_id: str, api_url: str = DEFAULT_API_URL, proxy: str = ""):
        """`api_url` — Bot API или посредник вроде Cloudflare Worker; `proxy` — http(s)/socks5 прокси."""
        self.token = token
        self.chat_id = chat_id
        self._client = httpx.AsyncClient(
            base_url=f"{(api_url or DEFAULT_API_URL).rstrip('/')}/bot{token}/",
            proxy=proxy or None,
            timeout=40,
        )

    @property
    def can_send(self) -> bool:
        return bool(self.token and self.chat_id)

    def is_target_chat(self, chat_id) -> bool:
        return str(chat_id) == str(self.chat_id)

    async def call(self, method: str, **params) -> dict | list | bool | None:
        try:
            resp = await self._client.post(method, json={k: v for k, v in params.items() if v is not None})
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Telegram %s failed: %s", method, exc)
            return None
        if not data.get("ok"):
            description = data.get("description") or ""
            if NOT_MODIFIED in description:
                return True
            new_chat_id = (data.get("parameters") or {}).get("migrate_to_chat_id")
            if new_chat_id and self.is_target_chat(params.get("chat_id")):
                self._follow_migration(new_chat_id)
                return await self.call(method, **(params | {"chat_id": new_chat_id}))
            logger.warning("Telegram %s error: %s", method, description)
            return None
        return data.get("result")

    def _follow_migration(self, new_chat_id: int) -> None:
        """Группа стала супергруппой и сменила ID: продолжаем писать в новый чат до перезапуска."""
        logger.warning(
            "Чат %s преобразован в супергруппу %s. Укажите TELEGRAM_CHAT_ID=%s в .env, иначе после перезапуска "
            "бот снова начнёт с устаревшего ID.",
            self.chat_id, new_chat_id, new_chat_id,
        )
        self.chat_id = str(new_chat_id)

    async def send_message(
        self, text: str, chat_id=None, reply_markup: dict | None = None, reply_to: int | None = None
    ) -> dict | None:
        """Отправляет HTML-сообщение. Возвращает объект Message или None при ошибке."""
        result = await self.call(
            "sendMessage",
            chat_id=chat_id or self.chat_id,
            text=text,
            parse_mode="HTML",
            reply_markup=reply_markup,
            link_preview_options={"is_disabled": True},
            reply_parameters={"message_id": reply_to, "allow_sending_without_reply": True} if reply_to else None,
        )
        return result if isinstance(result, dict) else None

    async def edit_message(self, message_id: int, text: str, reply_markup: dict | None = None, chat_id=None) -> bool:
        result = await self.call(
            "editMessageText",
            chat_id=chat_id or self.chat_id,
            message_id=message_id,
            text=text,
            parse_mode="HTML",
            reply_markup=reply_markup,
            link_preview_options={"is_disabled": True},
        )
        return result is not None

    async def remove_buttons(self, message_id: int, chat_id=None) -> bool:
        result = await self.call(
            "editMessageReplyMarkup",
            chat_id=chat_id or self.chat_id,
            message_id=message_id,
            reply_markup={"inline_keyboard": []},
        )
        return result is not None

    async def get_updates(self, offset: int | None) -> list | None:
        """None — ошибка запроса (вызывающий код делает паузу)."""
        return await self.call(
            "getUpdates", offset=offset, timeout=30, allowed_updates=["message", "callback_query"]
        )

    async def close(self) -> None:
        await self._client.aclose()
