from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app.config.settings import ConfigError


BOT_COMMAND_ACCESS_ADMIN = "admin"
BOT_COMMAND_ACCESS_SUPERADMIN = "superadmin"
BOT_COMMAND_ACCESS_LEVELS = frozenset(
    {BOT_COMMAND_ACCESS_ADMIN, BOT_COMMAND_ACCESS_SUPERADMIN}
)
BOT_COMMAND_KEYS = (
    "start",
    "help",
    "servers",
    "status",
    "players",
    "ping",
    "chatid",
    "grant",
    "revoke",
    "access",
)
SUPERADMIN_ONLY_BOT_COMMANDS = frozenset({"grant", "revoke"})


@dataclass(frozen=True)
class BotCommandConfig:
    key: str
    enabled: bool
    access: str
    description: str


@dataclass(frozen=True)
class BotCommandsConfig:
    commands: dict[str, BotCommandConfig]


DEFAULT_BOT_COMMANDS: dict[str, BotCommandConfig] = {
    "start": BotCommandConfig("start", True, BOT_COMMAND_ACCESS_ADMIN, "Информация о боте"),
    "help": BotCommandConfig("help", True, BOT_COMMAND_ACCESS_ADMIN, "Показывает помощь"),
    "servers": BotCommandConfig("servers", True, BOT_COMMAND_ACCESS_ADMIN, "Список доступных серверов"),
    "status": BotCommandConfig(
        "status",
        True,
        BOT_COMMAND_ACCESS_ADMIN,
        "Проверить доступность RCON-серверов",
    ),
    "players": BotCommandConfig(
        "players",
        True,
        BOT_COMMAND_ACCESS_ADMIN,
        "Онлайн игроков на доступных серверах",
    ),
    "ping": BotCommandConfig("ping", True, BOT_COMMAND_ACCESS_SUPERADMIN, "Проверить работу бота"),
    "chatid": BotCommandConfig(
        "chatid",
        True,
        BOT_COMMAND_ACCESS_SUPERADMIN,
        "Показать ID текущей беседы",
    ),
    "grant": BotCommandConfig(
        "grant",
        True,
        BOT_COMMAND_ACCESS_SUPERADMIN,
        "Выдать доступ к режиму",
    ),
    "revoke": BotCommandConfig(
        "revoke",
        True,
        BOT_COMMAND_ACCESS_SUPERADMIN,
        "Отозвать доступ к режиму",
    ),
    "access": BotCommandConfig("access", True, BOT_COMMAND_ACCESS_ADMIN, "Показать выданные доступы"),
}


def load_bot_commands_config(base_dir: Path | None = None) -> BotCommandsConfig:
    project_dir = base_dir or Path(__file__).resolve().parents[2]
    path = project_dir / "bot_commands.yml"
    if not path.exists():
        return BotCommandsConfig(commands=DEFAULT_BOT_COMMANDS.copy())
    return _load_bot_commands(path)


def _load_bot_commands(path: Path) -> BotCommandsConfig:
    if not path.is_file():
        raise ConfigError(f"{path.name} должен быть файлом, а не директорией.")

    try:
        raw_data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise ConfigError(f"Не удалось прочитать {path.name}: {error}") from error

    if not isinstance(raw_data, dict):
        raise ConfigError("bot_commands.yml должен содержать YAML-словарь.")

    raw_commands = raw_data.get("bot_commands")
    if not isinstance(raw_commands, dict):
        raise ConfigError("Раздел bot_commands в bot_commands.yml должен быть словарём.")

    parsed_commands = DEFAULT_BOT_COMMANDS.copy()
    seen_keys: set[str] = set()
    for raw_command_key, raw_command_data in raw_commands.items():
        command_key = str(raw_command_key).strip().lower()
        if command_key in seen_keys:
            raise ConfigError(f"Команда {command_key} в bot_commands.yml указана несколько раз.")
        seen_keys.add(command_key)

        if command_key not in DEFAULT_BOT_COMMANDS:
            raise ConfigError(f"Неизвестная служебная команда {raw_command_key} в bot_commands.yml.")
        if raw_command_data is None:
            raw_command_data = {}
        if not isinstance(raw_command_data, dict):
            raise ConfigError(f"Команда {command_key} в bot_commands.yml должна быть YAML-словарём.")

        parsed_commands[command_key] = _parse_bot_command(command_key, raw_command_data)

    return BotCommandsConfig(commands=parsed_commands)


def _parse_bot_command(command_key: str, raw_command_data: dict[str, Any]) -> BotCommandConfig:
    enabled = _parse_enabled(raw_command_data.get("enabled", True), command_key)
    access = _parse_access(raw_command_data.get("access", BOT_COMMAND_ACCESS_ADMIN), command_key)
    description = _parse_description(raw_command_data.get("description"), command_key)

    if command_key in SUPERADMIN_ONLY_BOT_COMMANDS and access != BOT_COMMAND_ACCESS_SUPERADMIN:
        raise ConfigError(f"Команда {command_key} не может иметь access ниже superadmin.")

    return BotCommandConfig(
        key=command_key,
        enabled=enabled,
        access=access,
        description=description,
    )


def _parse_enabled(value: Any, command_key: str) -> bool:
    if not isinstance(value, bool):
        raise ConfigError(f"enabled служебной команды {command_key} должен быть bool.")
    return value


def _parse_access(value: Any, command_key: str) -> str:
    access = str(value).strip().lower()
    if access not in BOT_COMMAND_ACCESS_LEVELS:
        raise ConfigError(
            f"access служебной команды {command_key} должен быть admin или superadmin."
        )
    return access


def _parse_description(value: Any, command_key: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ConfigError(f"description служебной команды {command_key} должен быть строкой.")
    return value.strip()
