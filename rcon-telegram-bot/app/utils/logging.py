from __future__ import annotations

import logging

from app.config.servers import ServersConfig
from app.config.settings import BotSettings
from app.services.rcon_service import mask_host


def setup_logging() -> None:
    # Настраиваем обычный вывод логов в консоль.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def log_startup(logger: logging.Logger, settings: BotSettings, servers_config: ServersConfig) -> None:
    # Логируем запуск без Telegram token, RCON-паролей, host:port и RCON-шаблонов команд.
    logger.info("Запуск RCON Telegram-бота.")
    logger.info(
        "servers.yml diagnostics: path=%s exists=%s keys=%s command_aliases=%s",
        servers_config.source_path,
        servers_config.source_exists,
        ",".join(servers_config.source_keys),
        len(servers_config.command_aliases),
    )
    logger.info(
        "Загружены серверы: %s",
        ", ".join(
            f"{server.key}=/{server.telegram_command}"
            for server in servers_config.servers.values()
        ),
    )
    for server in servers_config.servers.values():
        logger.info(
            "server config loaded: key=%s display_name=%s host=%s port=%s password_set=%s hidden=%s",
            server.key,
            server.display_name,
            mask_host(server.host),
            server.port,
            bool(server.password),
            server.hidden,
        )
        if _is_template_password(server.password):
            logger.warning(
                "server config may be a template: key=%s password_placeholder=true",
                server.key,
            )
        if _is_loopback_host(server.host):
            logger.warning(
                "server config uses loopback host: key=%s host=%s "
                "note=inside Docker this points to the bot container",
                server.key,
                mask_host(server.host),
            )
    if settings.dry_run:
        logger.warning("DRY_RUN включён: серверные команды не будут отправляться в RCON.")


def _is_template_password(password: str) -> bool:
    return password.strip().upper() in {"CHANGE_ME", "CHANGEME"}


def _is_loopback_host(host: str) -> bool:
    return host.strip().lower() in {"127.0.0.1", "localhost", "::1"}
