from __future__ import annotations

from aiogram.types import Message

from app.config.servers import ServersConfig
from app.config.topics import TopicsConfig


MAX_TELEGRAM_CHUNK_SIZE = 3500


def format_seconds(seconds: float) -> str:
    # Показываем "5" вместо "5.0", чтобы сообщения были аккуратнее.
    if seconds.is_integer():
        return str(int(seconds))
    return str(seconds)


async def send_long_message(message: Message, text: str) -> None:
    # Telegram ограничивает длину сообщения, поэтому длинный RCON-ответ режем на части.
    if len(text) <= MAX_TELEGRAM_CHUNK_SIZE:
        await message.answer(text)
        return

    for index in range(0, len(text), MAX_TELEGRAM_CHUNK_SIZE):
        await message.answer(text[index : index + MAX_TELEGRAM_CHUNK_SIZE])


def build_server_lines(servers_config: ServersConfig) -> str:
    # Формат списка серверов для /start и /servers.
    return "\n".join(
        f"• /{server.telegram_command} — {server.display_name}"
        for server in servers_config.servers.values()
    )


def build_server_command_lines(servers_config: ServersConfig) -> str:
    # Формат списка серверных команд для /help.
    return "\n".join(
        f"/{server.telegram_command} <команда> — {server.display_name}"
        for server in servers_config.servers.values()
    )


def build_topic_lines(topics_config: TopicsConfig) -> str:
    if not topics_config.topics:
        return "нет настроенных топиков"
    return "\n".join(
        f"• {topic.display_name} — пишите RCON-команды в топике, ключ доступа: {topic.key}"
        for topic in topics_config.topics.values()
    )


def build_allowed_commands_text(servers_config: ServersConfig) -> str:
    # Если whitelist пустой, так и пишем: пользовательские команды будут запрещены.
    if not servers_config.allowed_commands:
        return "нет"
    return ", ".join(sorted(servers_config.allowed_commands))
