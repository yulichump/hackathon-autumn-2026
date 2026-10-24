import asyncio
import json

import httpx

from app.telegram import TelegramBot, describe_route

OLD_CHAT = "-4000000001"
NEW_CHAT = -1009999999999


def _bot_with_fake_api(calls: list) -> TelegramBot:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        calls.append(payload["chat_id"])
        if str(payload["chat_id"]) == OLD_CHAT:
            return httpx.Response(200, json={
                "ok": False,
                "error_code": 400,
                "description": "Bad Request: group chat was upgraded to a supergroup chat",
                "parameters": {"migrate_to_chat_id": NEW_CHAT},
            })
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1, "chat": {"id": payload["chat_id"]}}})

    bot = TelegramBot("test-token", OLD_CHAT)
    bot._client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://api.telegram.org/bottest/")
    return bot


def test_send_follows_supergroup_migration():
    calls = []
    bot = _bot_with_fake_api(calls)

    message = asyncio.run(bot.send_message("hello"))

    assert message is not None
    assert calls == [OLD_CHAT, NEW_CHAT]
    assert bot.chat_id == str(NEW_CHAT)
    assert bot.is_target_chat(NEW_CHAT)

    asyncio.run(bot.send_message("again"))
    assert calls[-1] == str(NEW_CHAT)


def test_migration_of_other_chat_does_not_switch_target():
    calls = []
    bot = _bot_with_fake_api(calls)
    bot.chat_id = "-100777"

    message = asyncio.run(bot.send_message("hi", chat_id=OLD_CHAT))

    assert message is None
    assert bot.chat_id == "-100777"


def test_custom_api_url_is_used_for_requests():
    bot = TelegramBot("123:abc", "-1", api_url="https://tg-relay.example.workers.dev/")

    assert str(bot._client.base_url) == "https://tg-relay.example.workers.dev/bot123:abc/"


def test_socks_proxy_is_accepted():
    bot = TelegramBot("123:abc", "-1", proxy="socks5://user:secret@10.0.0.5:1080")

    assert bot.can_send


def test_route_description_hides_proxy_credentials():
    route = describe_route("https://api.telegram.org", "socks5://user:secret@10.0.0.5:1080")

    assert route == "api.telegram.org через прокси socks5://10.0.0.5:1080"
    assert "secret" not in route and "user" not in route
    assert describe_route("https://tg-relay.example.workers.dev", "") == "tg-relay.example.workers.dev"
