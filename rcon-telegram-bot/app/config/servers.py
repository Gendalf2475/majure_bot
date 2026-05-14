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
class CommandAlias:
    key: str
    input: str
    execute: str
    show_response: bool
    success_message: str | None = None


@dataclass(frozen=True)
class ServersConfig:
    servers: dict[str, ServerConfig]
    servers_by_command: dict[str, ServerConfig]
    command_aliases: dict[str, CommandAlias]
    command_aliases_by_input: dict[str, CommandAlias]


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
    if "command_aliases" not in raw_data:
        raise ConfigError("В servers.yml отсутствует раздел command_aliases.")

    raw_servers = raw_data["servers"]
    if not isinstance(raw_servers, dict) or not raw_servers:
        raise ConfigError("В servers.yml должен быть хотя бы один сервер.")

    command_aliases, command_aliases_by_input = _parse_command_aliases(
        raw_data["command_aliases"]
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
        command_aliases=command_aliases,
        command_aliases_by_input=command_aliases_by_input,
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


def _parse_command_aliases(
    raw_command_aliases: Any,
) -> tuple[dict[str, CommandAlias], dict[str, CommandAlias]]:
    if not isinstance(raw_command_aliases, dict):
        raise ConfigError("Раздел command_aliases должен быть YAML-словарем.")

    command_aliases: dict[str, CommandAlias] = {}
    command_aliases_by_input: dict[str, CommandAlias] = {}

    for alias_key, alias_data in raw_command_aliases.items():
        key = str(alias_key).strip()
        if not key:
            raise ConfigError("Ключ command_aliases не должен быть пустым.")
        if not isinstance(alias_data, dict):
            raise ConfigError(f"Алиас команды {key} должен быть YAML-словарем.")

        input_command = _normalize_alias_input(alias_data.get("input"), key)
        execute = _get_required_alias_string(alias_data, "execute", key)
        _validate_alias_execute(execute, key)
        show_response = _parse_alias_show_response(
            alias_data.get("show_response", True),
            key,
        )
        success_message = _parse_alias_success_message(alias_data.get("success_message"), key)

        alias = CommandAlias(
            key=key,
            input=input_command,
            execute=execute,
            show_response=show_response,
            success_message=success_message,
        )

        if input_command in command_aliases_by_input:
            other_alias = command_aliases_by_input[input_command]
            raise ConfigError(
                "input команды "
                f"{input_command} используется сразу для алиасов "
                f"{other_alias.key} и {alias.key}."
            )

        command_aliases[key] = alias
        command_aliases_by_input[input_command] = alias

    return command_aliases, command_aliases_by_input


def _get_required_alias_string(data: dict[str, Any], field_name: str, alias_key: str) -> str:
    value = data.get(field_name)
    if value is None or not str(value).strip():
        raise ConfigError(f"У алиаса команды {alias_key} не заполнено поле {field_name}.")
    return str(value).strip()


def _normalize_alias_input(value: Any, alias_key: str) -> str:
    input_command = _get_required_alias_string(
        {"input": value},
        "input",
        alias_key,
    ).lower()
    if input_command.startswith("/"):
        raise ConfigError(f"input алиаса команды {alias_key} не должен начинаться со slash.")
    if any(character.isspace() for character in input_command):
        raise ConfigError(f"input алиаса команды {alias_key} не должен содержать пробелы.")
    return input_command


def _validate_alias_execute(execute: str, alias_key: str) -> None:
    if not execute.replace("{args}", "").strip():
        raise ConfigError(
            f"execute алиаса команды {alias_key} не должен состоять только из {{args}}."
        )


def _parse_alias_show_response(value: Any, alias_key: str) -> bool:
    if not isinstance(value, bool):
        raise ConfigError(f"show_response алиаса команды {alias_key} должен быть bool.")
    return value


def _parse_alias_success_message(value: Any, alias_key: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ConfigError(f"success_message алиаса команды {alias_key} должен быть строкой.")

    success_message = value.strip()
    if not success_message:
        return None
    return success_message
