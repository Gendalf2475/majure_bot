from __future__ import annotations

import asyncio
import platform
from importlib import metadata

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.config.servers import ServerConfig, ServersConfig
from app.config.settings import BotSettings
from app.config.topics import TopicConfig, TopicsConfig
from app.services.rcon_service import mask_host
from app.services.server_service import get_server_players_block, get_server_status_line
from app.services.topic_access_service import (
    TopicAccessStore,
    can_use_bot_service_commands,
    get_user_topic_keys,
    is_superadmin,
)
from app.utils.text import build_command_aliases_text, send_long_message


common_router = Router()

NO_BOT_ACCESS_MESSAGE = "⛔ У вас нет доступа к этому боту.\nОбратитесь к администратору."
ADMIN_ONLY_MESSAGE = "⛔ Команда доступна только администраторам."


@common_router.message(Command("start"))
async def handle_start(
    message: Message,
    settings: BotSettings,
    servers_config: ServersConfig,
    topics_config: TopicsConfig,
    topic_access_store: TopicAccessStore,
) -> None:
    user_id = _get_user_id(message)
    if not can_use_bot_service_commands(user_id, settings, topic_access_store):
        await message.answer(NO_BOT_ACCESS_MESSAGE)
        return

    superadmin = is_superadmin(user_id, settings)
    topics = _get_visible_topics(user_id, settings, topic_access_store, topics_config)
    servers = _get_visible_servers(user_id, settings, topic_access_store, servers_config, topics_config)
    text = (
        "👋 Это RCON-бот для управления Minecraft Paper-серверами.\n\n"
        "Доступные режимы:\n"
        f"{_format_topic_lines(topics, show_keys=superadmin)}\n\n"
        "Серверные команды:\n"
        f"{_format_server_command_lines(servers)}\n\n"
        "Пишите алиас обычным сообщением в нужном топике.\n"
        "Пример: list"
    )
    await message.answer(text)


@common_router.message(Command("help"))
async def handle_help(
    message: Message,
    settings: BotSettings,
    servers_config: ServersConfig,
    topics_config: TopicsConfig,
    topic_access_store: TopicAccessStore,
) -> None:
    user_id = _get_user_id(message)
    if not can_use_bot_service_commands(user_id, settings, topic_access_store):
        await message.answer(NO_BOT_ACCESS_MESSAGE)
        return

    superadmin = is_superadmin(user_id, settings)
    topics = _get_visible_topics(user_id, settings, topic_access_store, topics_config)
    servers = _get_visible_servers(user_id, settings, topic_access_store, servers_config, topics_config)
    command_aliases_text = build_command_aliases_text(
        servers_config,
        include_admin=True,
        include_superadmin=superadmin,
    )

    if superadmin:
        text = _build_superadmin_help(topics, servers, command_aliases_text)
    else:
        text = _build_user_help(servers, command_aliases_text)
    await message.answer(text)


@common_router.message(Command("servers"))
async def handle_servers(
    message: Message,
    settings: BotSettings,
    servers_config: ServersConfig,
    topics_config: TopicsConfig,
    topic_access_store: TopicAccessStore,
) -> None:
    user_id = _get_user_id(message)
    if not can_use_bot_service_commands(user_id, settings, topic_access_store):
        await message.answer(NO_BOT_ACCESS_MESSAGE)
        return

    servers = _get_visible_servers(user_id, settings, topic_access_store, servers_config, topics_config)
    await message.answer(f"Доступные серверы:\n{_format_server_lines(servers)}")


@common_router.message(Command("ping"))
async def handle_ping(message: Message, settings: BotSettings) -> None:
    if not is_superadmin(_get_user_id(message), settings):
        await message.answer(ADMIN_ONLY_MESSAGE)
        return
    await message.answer("✅ Бот работает.")


@common_router.message(Command("chatid"))
async def handle_chatid(message: Message, settings: BotSettings) -> None:
    if not is_superadmin(_get_user_id(message), settings):
        await message.answer(ADMIN_ONLY_MESSAGE)
        return
    await message.answer(f"Chat ID этой беседы: {message.chat.id}")


@common_router.message(Command("diag"))
async def handle_diag(
    message: Message,
    settings: BotSettings,
    servers_config: ServersConfig,
    topic_access_store: TopicAccessStore,
) -> None:
    if not is_superadmin(_get_user_id(message), settings):
        await message.answer(ADMIN_ONLY_MESSAGE)
        return

    lines = [
        "Диагностика бота:",
        f"servers.yml: {servers_config.source_path}",
        f"servers.yml exists: {servers_config.source_exists}",
        f"servers.yml keys: {', '.join(servers_config.source_keys) or 'нет'}",
        f"command_aliases: {len(servers_config.command_aliases)}",
        "servers:",
    ]
    lines.extend(_format_diag_server_lines(servers_config))
    lines.extend(
        [
            f"topic_access.yml: {topic_access_store.path}",
            f"topic_access.yml is_file: {topic_access_store.path.is_file()}",
            f"Python: {platform.python_version()}",
            f"mcrcon: {_get_package_version('mcrcon')}",
        ]
    )
    await message.answer("\n".join(lines))


@common_router.message(Command("status"))
async def handle_status(
    message: Message,
    settings: BotSettings,
    servers_config: ServersConfig,
    topics_config: TopicsConfig,
    topic_access_store: TopicAccessStore,
) -> None:
    user_id = _get_user_id(message)
    if not can_use_bot_service_commands(user_id, settings, topic_access_store):
        await message.answer(NO_BOT_ACCESS_MESSAGE)
        return

    servers = _get_visible_servers(user_id, settings, topic_access_store, servers_config, topics_config)
    lines = ["📡 Статус серверов:"]
    results = await asyncio.gather(
        *(get_server_status_line(server, settings) for server in servers)
    )
    lines.extend(results)
    await send_long_message(message, "\n".join(lines))


@common_router.message(Command("players"))
async def handle_players(
    message: Message,
    settings: BotSettings,
    servers_config: ServersConfig,
    topics_config: TopicsConfig,
    topic_access_store: TopicAccessStore,
) -> None:
    user_id = _get_user_id(message)
    if not can_use_bot_service_commands(user_id, settings, topic_access_store):
        await message.answer(NO_BOT_ACCESS_MESSAGE)
        return

    servers = _get_visible_servers(user_id, settings, topic_access_store, servers_config, topics_config)
    results = await asyncio.gather(
        *(get_server_players_block(server, settings) for server in servers)
    )
    await send_long_message(message, "👥 Онлайн игроков:\n\n" + "\n\n".join(results))


def _get_user_id(message: Message) -> int | None:
    return message.from_user.id if message.from_user else None


def _build_user_help(servers: list[ServerConfig], command_aliases_text: str) -> str:
    return (
        "🛠 Доступные команды:\n\n"
        "Серверы:\n"
        f"{_format_server_command_lines(servers)}\n\n"
        "Алиасы:\n"
        f"{command_aliases_text}\n\n"
        "Подсказка:\n"
        "Пишите алиас обычным сообщением в нужном топике.\n"
        "Пример: list"
    )


def _build_superadmin_help(
    topics: list[TopicConfig],
    servers: list[ServerConfig],
    command_aliases_text: str,
) -> str:
    return (
        "🛠 Команды администратора:\n\n"
        "Служебные:\n"
        "• /start — информация о боте\n"
        "• /help — помощь\n"
        "• /servers — список серверов\n"
        "• /status — статус RCON\n"
        "• /players — онлайн игроков\n"
        "• /grant <user_id> <topic_key> — выдать доступ\n"
        "• /revoke <user_id> <topic_key> — отозвать доступ\n"
        "• /access [user_id] — показать доступы\n"
        "• /chatid — ID текущей беседы\n"
        "• /ping — проверить бота\n\n"
        "Серверы:\n"
        f"{_format_server_command_lines(servers)}\n\n"
        "Топики:\n"
        f"{_format_topic_lines(topics, show_keys=True)}\n\n"
        "Алиасы:\n"
        f"{command_aliases_text}"
    )


def _format_diag_server_lines(servers_config: ServersConfig) -> list[str]:
    return [
        "  "
        f"{server.key}: display_name={server.display_name}, "
        f"host={mask_host(server.host)}, port={server.port}, "
        f"password_set={bool(server.password)}"
        for server in servers_config.servers.values()
    ]


def _get_visible_topics(
    user_id: int | None,
    settings: BotSettings,
    topic_access_store: TopicAccessStore,
    topics_config: TopicsConfig,
) -> list[TopicConfig]:
    if is_superadmin(user_id, settings):
        return list(topics_config.topics.values())
    topic_keys = set(get_user_topic_keys(user_id, topic_access_store))
    return [
        topic
        for topic in topics_config.topics.values()
        if topic.key in topic_keys
    ]


def _get_visible_servers(
    user_id: int | None,
    settings: BotSettings,
    topic_access_store: TopicAccessStore,
    servers_config: ServersConfig,
    topics_config: TopicsConfig,
) -> list[ServerConfig]:
    if is_superadmin(user_id, settings):
        return list(servers_config.servers.values())
    server_keys = {
        topic.server_key
        for topic in _get_visible_topics(user_id, settings, topic_access_store, topics_config)
    }
    return [
        server
        for server in servers_config.servers.values()
        if server.key in server_keys
    ]


def _format_topic_lines(topics: list[TopicConfig], *, show_keys: bool) -> str:
    if not topics:
        return "нет доступных режимов"
    if show_keys:
        return "\n".join(f"• {topic.display_name} ({topic.key})" for topic in topics)
    return "\n".join(f"• {topic.display_name}" for topic in topics)


def _format_server_lines(servers: list[ServerConfig]) -> str:
    if not servers:
        return "нет доступных серверов"
    return "\n".join(
        f"• /{server.telegram_command} — {server.display_name}"
        for server in servers
    )


def _format_server_command_lines(servers: list[ServerConfig]) -> str:
    if not servers:
        return "нет доступных серверов"
    return "\n".join(
        f"• /{server.telegram_command} <alias> — {server.display_name}"
        for server in servers
    )


def _get_package_version(package_name: str) -> str:
    try:
        return metadata.version(package_name)
    except metadata.PackageNotFoundError:
        return "not installed"
