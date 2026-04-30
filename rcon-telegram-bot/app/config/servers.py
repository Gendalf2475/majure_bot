from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app.config.settings import ConfigError


@dataclass(frozen=True)
class ServerConfig:
    key: str
    display_name: str
    host: str
    port: int
    password: str
    telegram_command: str


@dataclass(frozen=True)
class ServersConfig:
    servers: dict[str, ServerConfig]
    servers_by_command: dict[str, ServerConfig]
    allowed_commands: frozenset[str]


def load_servers_config(base_dir: Path | None = None) -> ServersConfig:
    # servers.yml лежит в корне проекта рядом с bot.py.
    project_dir = base_dir or Path(__file__).resolve().parents[2]
    return _load_servers(project_dir / "servers.yml")


def _load_servers(path: Path) -> ServersConfig:
    # Проверяем наличие файла с серверами.
    if not path.exists():
        raise ConfigError(f"Файл {path.name} не найден в папке проекта.")

    # Читаем YAML-файл как обычный Python-словарь.
    try:
        raw_data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise ConfigError(f"Не удалось прочитать {path.name}: {error}") from error

    if not isinstance(raw_data, dict):
        raise ConfigError("servers.yml должен содержать YAML-словарь.")

    if "servers" not in raw_data:
        raise ConfigError("В servers.yml отсутствует раздел servers.")
    if "allowed_commands" not in raw_data:
        raise ConfigError("В servers.yml отсутствует раздел allowed_commands.")

    raw_servers = raw_data["servers"]
    if not isinstance(raw_servers, dict) or not raw_servers:
        raise ConfigError("В servers.yml должен быть хотя бы один сервер.")

    raw_allowed_commands = raw_data["allowed_commands"]
    if not isinstance(raw_allowed_commands, list):
        raise ConfigError("Раздел allowed_commands должен быть списком.")

    # Whitelist Minecraft-команд храним в нижнем регистре.
    allowed_commands = frozenset(
        str(command).strip().lower()
        for command in raw_allowed_commands
        if str(command).strip()
    )

    servers: dict[str, ServerConfig] = {}
    servers_by_command: dict[str, ServerConfig] = {}

    # Каждую запись из YAML превращаем в строгий ServerConfig.
    for server_key, server_data in raw_servers.items():
        if not isinstance(server_data, dict):
            raise ConfigError(f"Сервер {server_key} должен быть YAML-словарем.")

        key = str(server_key).strip()
        display_name = _get_required_yaml_string(server_data, "display_name", key)
        host = _get_required_yaml_string(server_data, "host", key)
        password = _get_required_yaml_string(server_data, "password", key)
        telegram_command = _normalize_telegram_command(
            _get_required_yaml_string(server_data, "telegram_command", key),
            key,
        )
        port = _parse_port(server_data.get("port"), key)

        server = ServerConfig(
            key=key,
            display_name=display_name,
            host=host,
            port=port,
            password=password,
            telegram_command=telegram_command,
        )
        servers[key] = server

        # Telegram-команды должны быть уникальными: нельзя дать двум серверам /test.
        if telegram_command in servers_by_command:
            other_server = servers_by_command[telegram_command]
            raise ConfigError(
                "Telegram-команда /"
                f"{telegram_command} используется сразу для серверов "
                f"{other_server.key} и {server.key}."
            )
        servers_by_command[telegram_command] = server

    return ServersConfig(
        servers=servers,
        servers_by_command=servers_by_command,
        allowed_commands=allowed_commands,
    )


def _get_required_yaml_string(data: dict[str, Any], field_name: str, server_key: str) -> str:
    # Обязательные строковые поля сервера не должны быть пустыми.
    value = data.get(field_name)
    if value is None or not str(value).strip():
        raise ConfigError(f"У сервера {server_key} не заполнено поле {field_name}.")
    return str(value).strip()


def _parse_port(value: Any, server_key: str) -> int:
    # RCON-порт должен быть числом от 1 до 65535.
    if value is None:
        raise ConfigError(f"У сервера {server_key} не заполнено поле port.")
    try:
        port = int(value)
    except (TypeError, ValueError) as error:
        raise ConfigError(f"У сервера {server_key} поле port должно быть числом.") from error

    if not 1 <= port <= 65535:
        raise ConfigError(f"У сервера {server_key} порт должен быть в диапазоне 1-65535.")
    return port


def _normalize_telegram_command(command: str, server_key: str) -> str:
    # В YAML можно написать "test" или "/test"; внутри проекта храним без слэша.
    normalized = command.strip().lower().lstrip("/")
    if not normalized:
        raise ConfigError(f"У сервера {server_key} не заполнено поле telegram_command.")
    if any(character.isspace() for character in normalized):
        raise ConfigError(f"telegram_command сервера {server_key} не должен содержать пробелы.")
    return normalized
