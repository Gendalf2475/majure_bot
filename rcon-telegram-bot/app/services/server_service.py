from __future__ import annotations

import logging

from aiogram.types import Message

from app.config.servers import ServerConfig, ServersConfig
from app.config.settings import BotSettings
from app.services.rcon_service import (
    RconCommandError,
    RconConnectionError,
    RconTimeoutError,
    check_rcon_available,
    execute_rcon_command,
    sanitize_error,
)
from app.utils.text import MAX_TELEGRAM_CHUNK_SIZE, format_seconds, send_long_message


logger = logging.getLogger(__name__)


async def get_server_status_line(server: ServerConfig, settings: BotSettings) -> str:
    # Для статуса сервера достаточно успешно подключиться к RCON.
    try:
        await check_rcon_available(server, settings.rcon_timeout_seconds)
        return f"✅ {server.display_name} — доступен"
    except RconTimeoutError:
        logger.warning("RCON status timeout: server=%s", server.key)
        return (
            f"❌ {server.display_name} — сервер не ответил за "
            f"{format_seconds(settings.rcon_timeout_seconds)} секунд"
        )
    except (RconConnectionError, RconCommandError) as error:
        logger.warning(
            "RCON status error: server=%s error=%s",
            server.key,
            sanitize_error(error, server),
        )
        return f"❌ {server.display_name} — RCON недоступен"


async def get_server_players_block(server: ServerConfig, settings: BotSettings) -> str:
    # Для /players на каждом сервере выполняется служебная команда Minecraft "list".
    try:
        response = await execute_rcon_command(server, "list", settings.rcon_timeout_seconds)
        players_response = response.strip() or "✅ Команда выполнена, но сервер не вернул текстовый ответ."
        return f"{server.display_name}:\n{players_response}"
    except RconTimeoutError:
        logger.warning("RCON players timeout: server=%s", server.key)
        return (
            f"{server.display_name}:\n"
            f"❌ Сервер не ответил за {format_seconds(settings.rcon_timeout_seconds)} секунд."
        )
    except (RconConnectionError, RconCommandError) as error:
        logger.warning(
            "RCON players error: server=%s error=%s",
            server.key,
            sanitize_error(error, server),
        )
        return f"{server.display_name}:\n❌ Недоступен"


async def execute_server_command(
    message: Message,
    server: ServerConfig,
    minecraft_command: str,
    settings: BotSettings,
) -> None:
    # В логи пишем только первое слово команды, чтобы не хранить полную историю действий.
    command_root = minecraft_command.split(maxsplit=1)[0].lower()
    try:
        # Отправляем Minecraft-команду в RCON конкретного Paper-сервера.
        response = await execute_rcon_command(server, minecraft_command, settings.rcon_timeout_seconds)
    except RconTimeoutError:
        logger.warning(
            "RCON command timeout: server=%s user_id=%s command=%s",
            server.key,
            _get_user_id_for_log(message),
            command_root,
        )
        await message.answer(f"❌ Сервер не ответил за {format_seconds(settings.rcon_timeout_seconds)} секунд.")
        return
    except RconConnectionError as error:
        logger.warning(
            "RCON connection error: server=%s user_id=%s command=%s error=%s",
            server.key,
            _get_user_id_for_log(message),
            command_root,
            sanitize_error(error, server),
        )
        await message.answer(
            f"❌ Не удалось подключиться к RCON сервера {server.display_name}. "
            "Проверьте host, port, password и включён ли enable-rcon."
        )
        return
    except RconCommandError as error:
        logger.warning(
            "RCON command error: server=%s user_id=%s command=%s error=%s",
            server.key,
            _get_user_id_for_log(message),
            command_root,
            sanitize_error(error, server),
        )
        await message.answer(f"❌ Ошибка выполнения команды: {sanitize_error(error, server)}")
        return

    # Успешное выполнение логируем без RCON-паролей и без Telegram token.
    logger.info(
        "RCON command executed: server=%s user_id=%s command=%s",
        server.key,
        _get_user_id_for_log(message),
        command_root,
    )

    if not response.strip():
        await message.answer("✅ Команда выполнена, но сервер не вернул текстовый ответ.")
        return

    # Короткий ответ отправляем одним сообщением, длинный режем на несколько частей.
    header = f"✅ Ответ от сервера {server.display_name}:\n"
    if len(header) + len(response) <= MAX_TELEGRAM_CHUNK_SIZE:
        await message.answer(header + response)
        return

    await message.answer(header.rstrip())
    await send_long_message(message, response)


def get_server_by_command(command: str, servers_config: ServersConfig) -> ServerConfig | None:
    # Ищем сервер по Telegram-команде, например "test" -> сервер test.
    return servers_config.servers_by_command.get(command)


def _get_user_id_for_log(message: Message) -> int | None:
    # В логах user_id нужен только для диагностики; доступа по user_id больше нет.
    return message.from_user.id if message.from_user else None
