from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


class ConfigError(Exception):
    """Ошибка конфигурации, из-за которой бот не должен запускаться."""


@dataclass(frozen=True)
class BotSettings:
    telegram_bot_token: str
    allowed_chat_id: int
    command_cooldown_seconds: float
    rcon_timeout_seconds: float
    dry_run: bool


def load_settings(base_dir: Path | None = None) -> BotSettings:
    # Определяем папку проекта и загружаем переменные из .env файла.
    project_dir = base_dir or Path(__file__).resolve().parents[2]
    load_dotenv(project_dir / ".env")

    # Собираем настройки бота в один объект, чтобы не читать .env по всему проекту.
    return BotSettings(
        telegram_bot_token=_get_required_env("TELEGRAM_BOT_TOKEN"),
        allowed_chat_id=_parse_required_int(_get_required_env("ALLOWED_CHAT_ID"), "ALLOWED_CHAT_ID"),
        command_cooldown_seconds=_parse_positive_float(
            os.getenv("COMMAND_COOLDOWN_SECONDS", "2"),
            "COMMAND_COOLDOWN_SECONDS",
        ),
        rcon_timeout_seconds=_parse_positive_float(
            os.getenv("RCON_TIMEOUT_SECONDS", "5"),
            "RCON_TIMEOUT_SECONDS",
        ),
        dry_run=_parse_bool(os.getenv("DRY_RUN", "false"), "DRY_RUN"),
    )


def _get_required_env(name: str) -> str:
    # Обязательная переменная должна существовать и быть не пустой.
    value = os.getenv(name)
    if value is None or not value.strip():
        raise ConfigError(f"Переменная {name} не настроена в .env.")
    return value.strip()


def _parse_required_int(value: str, name: str) -> int:
    # ALLOWED_CHAT_ID у супергрупп часто отрицательный, поэтому используем int().
    try:
        return int(value)
    except ValueError as error:
        raise ConfigError(f"{name} должен быть целым числом.") from error


def _parse_positive_float(value: str, name: str) -> float:
    # Таймауты и cooldown могут быть целыми или дробными числами.
    try:
        parsed = float(value)
    except ValueError as error:
        raise ConfigError(f"{name} должен быть числом.") from error

    if parsed < 0:
        raise ConfigError(f"{name} не может быть отрицательным.")
    return parsed


def _parse_bool(value: str, name: str) -> bool:
    # DRY_RUN удобно писать разными привычными способами: true/false, yes/no, 1/0.
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise ConfigError(f"{name} должен быть true или false.")
