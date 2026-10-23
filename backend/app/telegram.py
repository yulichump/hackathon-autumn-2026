"""Минимальный клиент Telegram Bot API (long polling) на httpx."""

import logging

import httpx

logger = logging.getLogger("telegram")


class TelegramBot:
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self._client = httpx.AsyncClient(base_url=f"https://api.telegram.org/bot{token}/", timeout=40)

    @property
    def can_send(self) -> bool:
        return bool(self.token and self.chat_id)

    def is_target_chat(self, chat_id) -> bool:
        return str(chat_id) == str(self.chat_id)

    async def call(self, method: str, **params) -> dict | list | None:
        try:
            resp = await self._client.post(method, json={k: v for k, v in params.items() if v is not None})
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Telegram %s failed: %s", method, exc)
            return None
        if not data.get("ok"):
            logger.warning("Telegram %s error: %s", method, data.get("description"))
            return None
        return data.get("result")

    async def send_message(self, text: str, chat_id=None, reply_markup: dict | None = None) -> bool:
        result = await self.call(
            "sendMessage",
            chat_id=chat_id or self.chat_id,
            text=text,
            parse_mode="HTML",
            reply_markup=reply_markup,
            disable_web_page_preview=True,
        )
        return result is not None

    async def get_updates(self, offset: int | None) -> list | None:
        """None — ошибка запроса (вызывающий код делает паузу)."""
        return await self.call(
            "getUpdates", offset=offset, timeout=30, allowed_updates=["message", "callback_query"]
        )

    async def close(self) -> None:
        await self._client.aclose()
