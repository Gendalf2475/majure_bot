from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import Message

from app.config.bot_commands import BotCommandsConfig
from app.config.servers import ALIAS_ACCESS_SUPERADMIN, ServerConfig, ServersConfig
from app.config.settings import BotSettings
from app.config.topics import TopicConfig, TopicsConfig
from app.services.server_service import execute_server_command, get_server_by_command
from app.services.topic_access_service import (
    TopicAccessStore,
    can_use_bot_service_commands,
    can_use_topic,
    is_superadmin,
)
from app.utils.validation import (
    ParsedAliasCommand,
    is_service_command,
    parse_alias_command,
    parse_telegram_command,
)


server_commands_router = Router()
logger = logging.getLogger(__name__)

FORBIDDEN_COMMAND_MESSAGE = "❌ Эта команда запрещена настройками бота."
DISABLED_COMMAND_MESSAGE = "❌ Эта команда временно отключена."
COMMAND_ACCESS_DENIED_MESSAGE = "⛔ У вас нет доступа к этой команде."
NO_BOT_ACCESS_MESSAGE = "⛔ У вас нет доступа к этому боту.\nОбратитесь к администратору."


@server_commands_router.message(F.text.startswith("/"))
async def handle_server_command(
    message: Message,
    settings: BotSettings,
    servers_config: ServersConfig,
    topics_config: TopicsConfig,
    topic_access_store: TopicAccessStore,
    bot_commands_config: BotCommandsConfig,
) -> None:
    # Разбираем Telegram-команду: из "/test list" получаем command="test", arguments="list".
    command, arguments = parse_telegram_command(message.text or "")

    # Служебные команды обрабатываются отдельными Telegram handler-ами.
    if is_service_command(command, bot_commands_config):
        return

    user_id = message.from_user.id if message.from_user else None
    if not can_use_bot_service_commands(user_id, settings, topic_access_store):
        await message.answer(NO_BOT_ACCESS_MESSAGE)
        return

    # Telegram-команда должна совпасть с telegram_command одного из серверов.
    requested_server = get_server_by_command(command, servers_config)
    if requested_server is None:
        await message.answer("❌ Сервер не найден.")
        return

    topic = topics_config.topics_by_server_key.get(requested_server.key)
    if not _can_use_server_mode(user_id, topic, settings, topic_access_store):
        await message.answer(f"⛔ У вас нет доступа к режиму {requested_server.display_name}.")
        return

    if not arguments:
        await message.answer(
            "❌ Укажите алиас команды.\n"
            f"Пример: /{requested_server.telegram_command} list"
        )
        return

    parsed_command = parse_alias_command(
        arguments,
        servers_config.command_aliases_by_input,
    )
    if parsed_command is None:
        await message.answer(FORBIDDEN_COMMAND_MESSAGE)
        return

    if not parsed_command.alias.enabled:
        await message.answer(DISABLED_COMMAND_MESSAGE)
        return

    if parsed_command.alias.access == ALIAS_ACCESS_SUPERADMIN and not is_superadmin(user_id, settings):
        await message.answer(COMMAND_ACCESS_DENIED_MESSAGE)
        return

    target_server = _get_alias_target_server(
        parsed_command,
        requested_server,
        servers_config,
    )
    # DRY_RUN полезен для проверки: бот покажет команду, но не отправит её в RCON.
    if settings.dry_run:
        await message.answer(
            "🧪 DRY RUN:\n"
            f"Requested server: {requested_server.key} ({requested_server.display_name})\n"
            f"Actual target server: {target_server.key} ({target_server.display_name})\n"
            f"Input alias: {parsed_command.input}\n"
            f"{_format_dry_run_commands(parsed_command.rcon_commands)}\n"
            f"show_response: {str(parsed_command.show_response).lower()}"
        )
        return

    logger.info(
        "RCON alias executed: alias=%s requested_topic=%s requested_server=%s target_server=%s user_id=%s",
        parsed_command.input,
        topic.key if topic else "",
        requested_server.key,
        target_server.key,
        user_id,
    )
    await execute_server_command(
        message,
        target_server,
        parsed_command.rcon_commands,
        settings,
        show_response=parsed_command.show_response,
        success_message=parsed_command.success_message,
    )


def _can_use_server_mode(
    user_id: int | None,
    topic: TopicConfig | None,
    settings: BotSettings,
    topic_access_store: TopicAccessStore,
) -> bool:
    if is_superadmin(user_id, settings):
        return True
    if topic is None:
        return False
    return can_use_topic(user_id, topic.key, settings, topic_access_store)


def _format_dry_run_commands(rcon_commands: tuple[str, ...]) -> str:
    if len(rcon_commands) == 1:
        return f"RCON-команда: {rcon_commands[0]}"
    return "RCON-команды:\n" + "\n".join(f"• {command}" for command in rcon_commands)


def _get_alias_target_server(
    parsed_command: ParsedAliasCommand,
    requested_server: ServerConfig,
    servers_config: ServersConfig,
) -> ServerConfig:
    if parsed_command.alias.target_server is None:
        return requested_server
    return servers_config.servers[parsed_command.alias.target_server]
