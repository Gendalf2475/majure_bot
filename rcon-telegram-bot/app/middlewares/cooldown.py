from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from app.config.servers import ServersConfig
from app.config.settings import BotSettings
from app.services.topic_access_service import (
    can_use_bot_service_commands,
    can_use_topic,
    is_superadmin,
)
from app.utils.validation import parse_telegram_command


COOLDOWN_MESSAGE = "⏳ Не так быстро. Подождите пару секунд."


class CommandCooldownMiddleware(BaseMiddleware):
    def __init__(self, settings: BotSettings, servers_config: ServersConfig) -> None:
        # Cooldown хранится в памяти процесса: после перезапуска бота счётчик обнулится.
        self.settings = settings
        self.servers_config = servers_config
        self.last_command_at: dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        # Cooldown нужен только для сообщений-команд.
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

        command = "topic_text"
        if text.startswith("/"):
            command, _ = parse_telegram_command(text)
        if not is_topic_text_command and not self._should_apply_cooldown(command):
            return await handler(event, data)

        user_id = event.from_user.id if event.from_user else None
        if user_id is None or self.settings.command_cooldown_seconds <= 0:
            return await handler(event, data)
        if not self._has_access_for_cooldown(event, command, is_topic_text_command, user_id, data):
            return await handler(event, data)

        # Если пользователь отправил команду слишком быстро, не пропускаем её дальше.
        now = time.monotonic()
        previous = self.last_command_at.get(user_id)
        if previous is not None and now - previous < self.settings.command_cooldown_seconds:
            await event.answer(COOLDOWN_MESSAGE)
            return None

        self.last_command_at[user_id] = now
        return await handler(event, data)

    def _should_apply_cooldown(self, command: str) -> bool:
        # Cooldown применяем к RCON-командам и статусным проверкам.
        return command in {"status", "players", "cmd"} or command in self.servers_config.servers_by_command

    def _has_access_for_cooldown(
        self,
        event: Message,
        command: str,
        is_topic_text_command: bool,
        user_id: int,
        data: dict[str, Any],
    ) -> bool:
        topic_access_store = data.get("topic_access_store")
        topics_config = data.get("topics_config")
        if topic_access_store is None or topics_config is None:
            return True

        if command in {"status", "players"}:
            return can_use_bot_service_commands(user_id, self.settings, topic_access_store)

        if is_topic_text_command or command == "cmd":
            topic = topics_config.topics_by_thread_id.get(event.message_thread_id)
            if topic is None:
                return False
            return can_use_topic(user_id, topic.key, self.settings, topic_access_store)

        server = self.servers_config.servers_by_command.get(command)
        if server is None:
            return True
        if is_superadmin(user_id, self.settings):
            return True
        topic = topics_config.topics_by_server_key.get(server.key)
        if topic is None:
            return False
        return can_use_topic(user_id, topic.key, self.settings, topic_access_store)
