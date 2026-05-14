from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.config.servers import CommandAlias, ServerConfig, ServersConfig, load_servers_config
from app.config.settings import BotSettings, ConfigError, load_settings


@dataclass(frozen=True)
class AppConfig:
    settings: BotSettings
    servers: dict[str, ServerConfig]
    servers_by_command: dict[str, ServerConfig]
    command_aliases: dict[str, CommandAlias]
    command_aliases_by_input: dict[str, CommandAlias]


def load_config(base_dir: Path | None = None) -> AppConfig:
    # Этот файл оставлен как совместимая обёртка для старых импортов.
    # Основная логика загрузки настроек теперь находится в app/config/settings.py
    # и app/config/servers.py.
    settings = load_settings(base_dir)
    servers_config: ServersConfig = load_servers_config(base_dir)
    return AppConfig(
        settings=settings,
        servers=servers_config.servers,
        servers_by_command=servers_config.servers_by_command,
        command_aliases=servers_config.command_aliases,
        command_aliases_by_input=servers_config.command_aliases_by_input,
    )
