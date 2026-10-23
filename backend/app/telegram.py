"""Минимальный клиент Telegram Bot API (long polling) на httpx."""

import logging

import httpx

logger = logging.getLogger("telegram")

NOT_MODIFIED = "message is not modified"


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
            logger.warning("Telegram %s error: %s", method, description)
            return None
        return data.get("result")

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
