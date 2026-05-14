from __future__ import annotations

import ipaddress
import socket

from mcrcon import MCRcon, MCRconException

from app.config.servers import ServerConfig


class RconError(Exception):
    """Базовая ошибка RCON, которую бот умеет безопасно обработать."""


class RconConnectionError(RconError):
    """Не удалось подключиться к RCON или пройти авторизацию."""


class RconCommandError(RconError):
    """Команда была отправлена, но во время выполнения произошла ошибка."""


class RconTimeoutError(RconError):
    """RCON-сервер не ответил за указанное время."""


async def execute_rcon_command(server: ServerConfig, command: str, timeout_seconds: float) -> str:
    # mcrcon использует signal, поэтому выполняем его в основном потоке.
    return _execute_rcon_command_sync(server, command, timeout_seconds)


async def check_rcon_available(server: ServerConfig, timeout_seconds: float) -> None:
    # Для /status достаточно открыть RCON-соединение и сразу его закрыть.
    _check_rcon_available_sync(server, timeout_seconds)


def sanitize_error(error: BaseException, server: ServerConfig) -> str:
    # Перед логами и сообщениями пользователю удаляем приватные данные из текста ошибки.
    message = str(error) or _get_cause_message(error) or error.__class__.__name__
    if server.host:
        message = message.replace(f"{server.host}:{server.port}", "***")
        message = message.replace(server.host, "***")
    if server.password:
        message = message.replace(server.password, "***")
    return message


def get_error_cause_class(error: BaseException) -> str | None:
    if error.__cause__ is None:
        return None
    return error.__cause__.__class__.__name__


def mask_host(host: str) -> str:
    stripped = host.strip()
    if not stripped:
        return "<empty>"

    try:
        ip_address = ipaddress.ip_address(stripped)
    except ValueError:
        return _mask_hostname(stripped)

    if ip_address.version == 4:
        octets = stripped.split(".")
        return ".".join([octets[0], octets[1], octets[2], "*"])
    return f"{stripped.split(':', maxsplit=1)[0]}:***"


def _get_cause_message(error: BaseException) -> str:
    if error.__cause__ is None:
        return ""
    return str(error.__cause__)


def _mask_hostname(host: str) -> str:
    parts = host.split(".")
    if len(parts) == 1:
        return _mask_label(host)
    return ".".join([_mask_label(parts[0]), *parts[1:]])


def _mask_label(label: str) -> str:
    if len(label) <= 2:
        return "*" * len(label)
    return f"{label[:2]}***"


def _execute_rcon_command_sync(server: ServerConfig, command: str, timeout_seconds: float) -> str:
    # Низкоуровневое выполнение Minecraft-команды через RCON.
    timeout = max(1, int(timeout_seconds))
    try:
        with MCRcon(
            server.host,
            server.password,
            port=server.port,
            timeout=timeout,
        ) as rcon:
            response = rcon.command(command)
            return response or ""
    except (socket.timeout, TimeoutError) as error:
        raise RconTimeoutError(str(error) or error.__class__.__name__) from error
    except (ConnectionError, OSError, MCRconException) as error:
        raise RconConnectionError(str(error) or error.__class__.__name__) from error
    except Exception as error:
        raise RconCommandError(str(error) or error.__class__.__name__) from error


def _check_rcon_available_sync(server: ServerConfig, timeout_seconds: float) -> None:
    # Низкоуровневая проверка RCON-соединения без выполнения команды.
    timeout = max(1, int(timeout_seconds))
    try:
        with MCRcon(
            server.host,
            server.password,
            port=server.port,
            timeout=timeout,
        ):
            return
    except (socket.timeout, TimeoutError) as error:
        raise RconTimeoutError(str(error) or error.__class__.__name__) from error
    except (ConnectionError, OSError, MCRconException) as error:
        raise RconConnectionError(str(error) or error.__class__.__name__) from error
    except Exception as error:
        raise RconCommandError(str(error) or error.__class__.__name__) from error
