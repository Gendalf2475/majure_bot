from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from app.config.settings import BotSettings
from app.utils.validation import parse_telegram_command


logger = logging.getLogger(__name__)

WRONG_CHAT_MESSAGE = "⛔ Этот бот работает только в разрешённой беседе."


class AccessMiddleware(BaseMiddleware):
    def __init__(self, settings: BotSettings) -> None:
        # Сохраняем настройки, чтобы на каждом сообщении сравнивать chat.id с ALLOWED_CHAT_ID.
        self.settings = settings

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        # Middleware может получить разные события Telegram, но нам нужны только сообщения.
        if not isinstance(event, Message):
            return await handler(event, data)

        text = event.text or ""
        is_topic_text_command = (
            bool(text.strip())
            and not text.startswith("/")
            and event.message_thread_id is not None
        )
        if not text.startswith("/") and not is_topic_text_command:
            return await handler(event, data)

        command = ""
        if text.startswith("/"):
            command, _ = parse_telegram_command(text)
        if command == "chatid":
            # /chatid работает в любом чате, чтобы можно было узнать ID нужной беседы.
            return await handler(event, data)

        # Все команды и RCON-текст в топиках бот выполняет только в одной разрешённой беседе.
        if event.chat.id != self.settings.allowed_chat_id:
            logger.warning(
                "Bot action from wrong chat: user_id=%s chat_id=%s",
                event.from_user.id if event.from_user else None,
                event.chat.id,
            )
            await event.answer(WRONG_CHAT_MESSAGE)
            return None

        return await handler(event, data)
