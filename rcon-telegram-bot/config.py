from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.config.servers import ServerConfig, ServersConfig, load_servers_config
from app.config.settings import BotSettings, ConfigError, load_settings


@dataclass(frozen=True)
class AppConfig:
    settings: BotSettings
    servers: dict[str, ServerConfig]
    servers_by_command: dict[str, ServerConfig]
    allowed_commands: frozenset[str]


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
        allowed_commands=servers_config.allowed_commands,
    )
