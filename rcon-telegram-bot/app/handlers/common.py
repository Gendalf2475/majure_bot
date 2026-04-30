from __future__ import annotations

import asyncio

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.config.servers import ServersConfig
from app.config.settings import BotSettings
from app.config.topics import TopicsConfig
from app.services.server_service import get_server_players_block, get_server_status_line
from app.utils.text import (
    build_allowed_commands_text,
    build_server_command_lines,
    build_server_lines,
    build_topic_lines,
    send_long_message,
)


common_router = Router()


@common_router.message(Command("start"))
async def handle_start(
    message: Message,
    servers_config: ServersConfig,
    topics_config: TopicsConfig,
) -> None:
    # Короткое приветствие и пример формата серверной команды.
    text = (
        "👋 Это RCON-бот для управления Minecraft Paper-серверами.\n\n"
        "Доступные серверы:\n"
        f"{build_server_lines(servers_config)}\n\n"
        "Топики:\n"
        f"{build_topic_lines(topics_config)}\n\n"
        "Пример использования:\n"
        "напишите list в нужном топике"
    )
    await message.answer(text)


@common_router.message(Command("help"))
async def handle_help(
    message: Message,
    servers_config: ServersConfig,
    topics_config: TopicsConfig,
) -> None:
    # Подробная справка: служебные команды, серверные команды и whitelist Minecraft-команд.
    text = (
        "📌 Команды бота:\n\n"
        "/start — информация о боте\n"
        "/help — помощь\n"
        "/servers — список серверов\n"
        "/status — проверить доступность RCON-серверов\n"
        "/players — онлайн игроков на всех серверах\n"
        "RCON в топике — напишите Minecraft-команду обычным сообщением\n"
        "/grant <user_id> <topic_key> — выдать доступ к режиму\n"
        "/revoke <user_id> <topic_key> — отозвать доступ к режиму\n"
        "/access — показать выданные режимы\n"
        "/chatid — показать ID текущей беседы\n"
        "/ping — проверить работу бота\n\n"
        "🧵 Топики:\n"
        f"{build_topic_lines(topics_config)}\n\n"
        "🎮 Команды серверов:\n"
        f"{build_server_command_lines(servers_config)}\n\n"
        "Примеры:\n"
        "list\n"
        "say Проверка\n"
        "/polit list\n\n"
        "✅ Разрешённые Minecraft-команды:\n"
        f"{build_allowed_commands_text(servers_config)}"
    )
    await message.answer(text)


@common_router.message(Command("servers"))
async def handle_servers(message: Message, servers_config: ServersConfig) -> None:
    # Показываем серверы из servers.yml, без хардкода в коде.
    await message.answer(f"Доступные серверы:\n{build_server_lines(servers_config)}")


@common_router.message(Command("ping"))
async def handle_ping(message: Message) -> None:
    # Простая проверка, что бот живой и отвечает.
    await message.answer("✅ Бот работает.")


@common_router.message(Command("chatid"))
async def handle_chatid(message: Message) -> None:
    # /chatid работает в любом чате, чтобы можно было узнать значение для ALLOWED_CHAT_ID.
    await message.answer(f"Chat ID этой беседы: {message.chat.id}")


@common_router.message(Command("status"))
async def handle_status(
    message: Message,
    settings: BotSettings,
    servers_config: ServersConfig,
) -> None:
    # Проверяем все серверы параллельно, чтобы один недоступный сервер не тормозил остальные.
    lines = ["📡 Статус серверов:"]
    results = await asyncio.gather(
        *(
            get_server_status_line(server, settings)
            for server in servers_config.servers.values()
        )
    )
    lines.extend(results)
    await send_long_message(message, "\n".join(lines))


@common_router.message(Command("players"))
async def handle_players(
    message: Message,
    settings: BotSettings,
    servers_config: ServersConfig,
) -> None:
    # Эта команда всегда выполняет "list" как служебную команду бота.
    results = await asyncio.gather(
        *(
            get_server_players_block(server, settings)
            for server in servers_config.servers.values()
        )
    )
    await send_long_message(message, "👥 Онлайн игроков:\n\n" + "\n\n".join(results))
