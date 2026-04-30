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
from app.utils.text import MAX_TELEGRAM_CHUNK_SIZE, format_seconds


logger = logging.getLogger(__name__)

LIST_COMMAND = "list"
LIST_FALLBACK_COMMAND = "minecraft:list"
PLAYERS_EMPTY_LIST_MESSAGE = "сервер не вернул список игроков"
TRUNCATED_RESPONSE_SUFFIX = "\n…ответ обрезан"


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
        response = await _execute_list_command_with_fallback(server, settings.rcon_timeout_seconds)
        players_response = response.strip() or PLAYERS_EMPTY_LIST_MESSAGE
        return f"{server.display_name}\n{players_response}"
    except RconTimeoutError:
        logger.warning("RCON players timeout: server=%s", server.key)
        return (
            f"{server.display_name}\n"
            f"❌ Сервер не ответил за {format_seconds(settings.rcon_timeout_seconds)} секунд."
        )
    except (RconConnectionError, RconCommandError) as error:
        logger.warning(
            "RCON players error: server=%s error=%s",
            server.key,
            sanitize_error(error, server),
        )
        return f"{server.display_name}\n❌ Недоступен"


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
        response = await _execute_user_command_with_fallback(
            server,
            minecraft_command,
            settings.rcon_timeout_seconds,
        )
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

    response_text = response.strip()
    if not response_text:
        if _is_list_command(minecraft_command):
            await message.answer(
                f"✅ Команда list выполнена на {server.display_name}, "
                "но сервер не вернул список игроков."
            )
            return

        await message.answer(
            f"✅ Команда выполнена на {server.display_name}, "
            "но сервер не вернул текстовый ответ."
        )
        return

    await message.answer(_format_command_response(server, response_text))


def get_server_by_command(command: str, servers_config: ServersConfig) -> ServerConfig | None:
    # Ищем сервер по Telegram-команде, например "test" -> сервер test.
    return servers_config.servers_by_command.get(command)


async def _execute_user_command_with_fallback(
    server: ServerConfig,
    minecraft_command: str,
    timeout_seconds: float,
) -> str:
    response = await execute_rcon_command(server, minecraft_command, timeout_seconds)
    if _is_list_command(minecraft_command) and not response.strip():
        return await execute_rcon_command(server, LIST_FALLBACK_COMMAND, timeout_seconds)
    return response


async def _execute_list_command_with_fallback(server: ServerConfig, timeout_seconds: float) -> str:
    response = await execute_rcon_command(server, LIST_COMMAND, timeout_seconds)
    if response.strip():
        return response
    return await execute_rcon_command(server, LIST_FALLBACK_COMMAND, timeout_seconds)


def _format_command_response(server: ServerConfig, response: str) -> str:
    header = f"✅ Ответ от сервера {server.display_name}:\n"
    return header + _truncate_response(response, MAX_TELEGRAM_CHUNK_SIZE - len(header))


def _truncate_response(response: str, max_length: int) -> str:
    if len(response) <= max_length:
        return response

    response_length = max(1, max_length - len(TRUNCATED_RESPONSE_SUFFIX))
    return response[:response_length].rstrip() + TRUNCATED_RESPONSE_SUFFIX


def _is_list_command(minecraft_command: str) -> bool:
    return minecraft_command.strip().split(maxsplit=1)[0].lower() == LIST_COMMAND


def _get_user_id_for_log(message: Message) -> int | None:
    # В логах user_id нужен только для диагностики; доступа по user_id больше нет.
    return message.from_user.id if message.from_user else None
