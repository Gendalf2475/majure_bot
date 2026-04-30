from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from app.config.servers import load_servers_config
from app.config.settings import ConfigError, load_settings
from app.handlers.common import common_router
from app.handlers.server_commands import server_commands_router
from app.middlewares.access import AccessMiddleware
from app.middlewares.cooldown import CommandCooldownMiddleware
from app.utils.logging import log_startup, setup_logging


logger = logging.getLogger(__name__)


async def main() -> None:
    # Включаем понятный вывод логов в консоль.
    setup_logging()

    # Загружаем .env и servers.yml. Если конфигурация неверная, бот не запускается.
    try:
        settings = load_settings()
        servers_config = load_servers_config()
    except ConfigError as error:
        logger.error("Ошибка конфигурации: %s", error)
        raise SystemExit(1) from error

    log_startup(logger, settings, servers_config)

    # Создаём объект Telegram-бота. Токен берётся только из .env.
    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=None),
    )

    # Dispatcher принимает сообщения от Telegram и передаёт их middleware/handler-ам.
    dispatcher = Dispatcher()

    # AccessMiddleware ограничивает выполнение команд одной разрешённой беседой.
    dispatcher.message.middleware(AccessMiddleware(settings))

    # CooldownMiddleware защищает RCON от слишком частых команд одного пользователя.
    dispatcher.message.middleware(CommandCooldownMiddleware(settings, servers_config))

    # Регистрируем обработчики обычных команд: /start, /help, /servers, /status и т.д.
    dispatcher.include_router(common_router)

    # Регистрируем обработчик серверных команд: /lobby, /test, /polit и другие из servers.yml.
    dispatcher.include_router(server_commands_router)

    # Запускаем long polling: бот постоянно ждёт новые сообщения из Telegram.
    await dispatcher.start_polling(
        bot,
        settings=settings,
        servers_config=servers_config,
        allowed_updates=dispatcher.resolve_used_update_types(),
    )


if __name__ == "__main__":
    asyncio.run(main())
