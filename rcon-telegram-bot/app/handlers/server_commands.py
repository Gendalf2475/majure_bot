from __future__ import annotations

from aiogram import F, Router
from aiogram.types import Message

from app.config.servers import ServersConfig
from app.config.settings import BotSettings
from app.config.topics import TopicsConfig
from app.services.server_service import execute_server_command, get_server_by_command
from app.services.topic_access_service import TopicAccessStore, can_use_topic
from app.utils.validation import (
    SERVICE_COMMANDS,
    is_minecraft_command_allowed,
    parse_telegram_command,
)


server_commands_router = Router()

FORBIDDEN_COMMAND_MESSAGE = "❌ Эта команда запрещена настройками бота."


@server_commands_router.message(F.text.startswith("/"))
async def handle_server_command(
    message: Message,
    settings: BotSettings,
    servers_config: ServersConfig,
    topics_config: TopicsConfig,
    topic_access_store: TopicAccessStore,
) -> None:
    # Разбираем Telegram-команду: из "/test list" получаем command="test", minecraft_command="list".
    command, minecraft_command = parse_telegram_command(message.text or "")

    # Служебные команды уже обработаны в common.py.
    if command in SERVICE_COMMANDS:
        return

    # Telegram-команда должна совпасть с telegram_command одного из серверов.
    server = get_server_by_command(command, servers_config)
    if server is None:
        await message.answer("❌ Сервер не найден.")
        return

    if not minecraft_command:
        await message.answer(
            "❌ Укажите команду Minecraft.\n"
            f"Пример: /{server.telegram_command} list"
        )
        return

    # Проверяем whitelist из allowed_commands: берётся только первое слово Minecraft-команды.
    if not is_minecraft_command_allowed(minecraft_command, servers_config.allowed_commands):
        await message.answer(FORBIDDEN_COMMAND_MESSAGE)
        return

    topic = topics_config.topics_by_server_key.get(server.key)
    user_id = message.from_user.id if message.from_user else None
    if topic is not None and not can_use_topic(user_id, topic.key, settings, topic_access_store):
        await message.answer(f"⛔ У вас нет доступа к режиму {topic.display_name}.")
        return

    # DRY_RUN полезен для проверки: бот покажет команду, но не отправит её в RCON.
    if settings.dry_run:
        await message.answer(
            "🧪 DRY RUN:\n"
            f"Сервер: {server.display_name}\n"
            f"Команда: {minecraft_command}"
        )
        return

    await execute_server_command(message, server, minecraft_command, settings)
