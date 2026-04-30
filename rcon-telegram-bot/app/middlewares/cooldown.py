from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from app.config.servers import ServersConfig
from app.config.settings import BotSettings
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
        if not text.startswith("/"):
            return await handler(event, data)

        command, _ = parse_telegram_command(text)
        if not self._should_apply_cooldown(command):
            return await handler(event, data)

        user_id = event.from_user.id if event.from_user else None
        if user_id is None or self.settings.command_cooldown_seconds <= 0:
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
