from __future__ import annotations

from aiogram import F, Router
from aiogram.types import Message

from app.config.servers import ALIAS_ACCESS_SUPERADMIN, ServersConfig
from app.config.settings import BotSettings
from app.config.topics import TopicConfig, TopicsConfig
from app.services.server_service import execute_server_command, get_server_by_command
from app.services.topic_access_service import (
    TopicAccessStore,
    can_use_topic,
    is_admin_user,
)
from app.utils.validation import (
    ParsedAliasCommand,
    SERVICE_COMMANDS,
    parse_alias_command,
    parse_telegram_command,
)


server_commands_router = Router()

FORBIDDEN_COMMAND_MESSAGE = "❌ Эта команда запрещена настройками бота."
DISABLED_COMMAND_MESSAGE = "❌ Эта команда временно отключена."
COMMAND_ACCESS_DENIED_MESSAGE = "⛔ У вас нет доступа к этой команде."


@server_commands_router.message(F.text.startswith("/"))
async def handle_server_command(
    message: Message,
    settings: BotSettings,
    servers_config: ServersConfig,
    topics_config: TopicsConfig,
    topic_access_store: TopicAccessStore,
) -> None:
    # Разбираем Telegram-команду: из "/test list" получаем command="test", arguments="list".
    command, arguments = parse_telegram_command(message.text or "")

    # Служебные команды уже обработаны в common.py.
    if command in SERVICE_COMMANDS:
        return

    # Telegram-команда должна совпасть с telegram_command одного из серверов.
    server = get_server_by_command(command, servers_config)
    if server is None:
        await message.answer("❌ Сервер не найден.")
        return

    if not arguments:
        await message.answer(
            "❌ Укажите алиас команды.\n"
            f"Пример: /{server.telegram_command} list"
        )
        return

    parsed_command = parse_alias_command(
        arguments,
        servers_config.command_aliases_by_input,
    )
    if parsed_command is None:
        await message.answer(FORBIDDEN_COMMAND_MESSAGE)
        return

    topic = topics_config.topics_by_server_key.get(server.key)
    user_id = message.from_user.id if message.from_user else None
    if not parsed_command.alias.enabled:
        await message.answer(DISABLED_COMMAND_MESSAGE)
        return

    if not _can_execute_alias_command(
        parsed_command,
        user_id,
        topic,
        settings,
        topic_access_store,
    ):
        await message.answer(COMMAND_ACCESS_DENIED_MESSAGE)
        return

    # DRY_RUN полезен для проверки: бот покажет команду, но не отправит её в RCON.
    if settings.dry_run:
        await message.answer(
            "🧪 DRY RUN:\n"
            f"Сервер: {server.display_name}\n"
            f"Input alias: {parsed_command.input}\n"
            f"{_format_dry_run_commands(parsed_command.rcon_commands)}\n"
            f"show_response: {str(parsed_command.show_response).lower()}"
        )
        return

    await execute_server_command(
        message,
        server,
        parsed_command.rcon_commands,
        settings,
        show_response=parsed_command.show_response,
        success_message=parsed_command.success_message,
    )


def _can_execute_alias_command(
    parsed_command: ParsedAliasCommand,
    user_id: int | None,
    topic: TopicConfig | None,
    settings: BotSettings,
    topic_access_store: TopicAccessStore,
) -> bool:
    if parsed_command.alias.access == ALIAS_ACCESS_SUPERADMIN:
        return is_admin_user(user_id, settings)

    if topic is None:
        return True
    return can_use_topic(user_id, topic.key, settings, topic_access_store)


def _format_dry_run_commands(rcon_commands: tuple[str, ...]) -> str:
    if len(rcon_commands) == 1:
        return f"RCON-команда: {rcon_commands[0]}"
    return "RCON-команды:\n" + "\n".join(f"• {command}" for command in rcon_commands)
