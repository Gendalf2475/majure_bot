from __future__ import annotations

from aiogram.types import Message

from app.config.settings import BotSettings
from app.middlewares.access import WRONG_CHAT_MESSAGE
from app.utils.validation import is_minecraft_command_allowed


FORBIDDEN_COMMAND_MESSAGE = "❌ Эта команда запрещена настройками бота."


def get_user_id(message: Message) -> int | None:
    # Этот файл оставлен для совместимости со старой структурой проекта.
    return message.from_user.id if message.from_user else None


def is_allowed_chat(chat_id: int, settings: BotSettings) -> bool:
    # Доступ проверяется только по ID разрешённой беседы.
    return chat_id == settings.allowed_chat_id
