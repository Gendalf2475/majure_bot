from __future__ import annotations

import logging

from app.config.servers import ServersConfig
from app.config.settings import BotSettings


def setup_logging() -> None:
    # Настраиваем обычный вывод логов в консоль.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def log_startup(logger: logging.Logger, settings: BotSettings, servers_config: ServersConfig) -> None:
    # Логируем запуск без Telegram token, RCON-паролей, host:port и полного whitelist команд.
    logger.info("Запуск RCON Telegram-бота.")
    logger.info(
        "Загружены серверы: %s",
        ", ".join(
            f"{server.key}=/{server.telegram_command}"
            for server in servers_config.servers.values()
        ),
    )
    logger.info(
        "Загружено разрешённых Minecraft-команд: %s",
        len(servers_config.allowed_commands),
    )
    if settings.dry_run:
        logger.warning("DRY_RUN включён: серверные команды не будут отправляться в RCON.")
