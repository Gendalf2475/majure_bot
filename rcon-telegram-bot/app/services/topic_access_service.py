from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml

from app.config.bot_commands import (
    BOT_COMMAND_ACCESS_SUPERADMIN,
    BotCommandsConfig,
)
from app.config.settings import BotSettings, ConfigError


ACCESS_FILE_NAME = "topic_access.yml"
BOT_COMMAND_DENIAL_DISABLED = "disabled"
BOT_COMMAND_DENIAL_ADMIN_ONLY = "admin_only"
BOT_COMMAND_DENIAL_NO_BOT_ACCESS = "no_bot_access"

logger = logging.getLogger(__name__)


class TopicAccessStore:
    def __init__(self, path: Path | None = None) -> None:
        project_dir = Path(__file__).resolve().parents[2]
        self.path = path or project_dir / ACCESS_FILE_NAME
        self._user_topics = self._load()
        logger.info(
            "TopicAccessStore path=%s exists=%s is_file=%s users_count=%s",
            self.path,
            self.path.exists(),
            self.path.is_file(),
            len(self._user_topics),
        )

    def has_access(self, user_id: int, topic_key: str) -> bool:
        topic_key = _normalize_topic_key(topic_key)
        if not topic_key:
            return False
        return topic_key in self._user_topics.get(user_id, set())

    def grant_access(self, user_id: int, topic_key: str) -> bool:
        topic_key = _normalize_topic_key(topic_key)
        if not topic_key:
            return False
        topics = self._user_topics.setdefault(user_id, set())
        if topic_key in topics:
            return False
        topics.add(topic_key)
        try:
            self._save()
        except Exception:
            topics.remove(topic_key)
            if not topics:
                self._user_topics.pop(user_id, None)
            raise
        logger.info(
            "Topic access saved after grant: path=%s user_id=%s topic=%s users_count=%s",
            self.path,
            user_id,
            topic_key,
            len(self._user_topics),
        )
        return True

    def revoke_access(self, user_id: int, topic_key: str) -> bool:
        topic_key = _normalize_topic_key(topic_key)
        if not topic_key:
            return False
        topics = self._user_topics.get(user_id)
        if not topics or topic_key not in topics:
            return False
        topics.remove(topic_key)
        removed_user = False
        if not topics:
            self._user_topics.pop(user_id, None)
            removed_user = True
        try:
            self._save()
        except Exception:
            if removed_user:
                self._user_topics[user_id] = {topic_key}
            else:
                topics.add(topic_key)
            raise
        logger.info(
            "Topic access saved after revoke: path=%s user_id=%s topic=%s users_count=%s",
            self.path,
            user_id,
            topic_key,
            len(self._user_topics),
        )
        return True

    def get_user_topics(self, user_id: int) -> list[str]:
        return sorted(self._user_topics.get(user_id, set()))

    def users_count(self) -> int:
        return len(self._user_topics)

    def file_users_count(self) -> int:
        if not self.path.exists() or not self.path.is_file():
            return 0
        raw_data = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw_data, dict):
            return 0
        raw_users = raw_data.get("users", {})
        return len(raw_users) if isinstance(raw_users, dict) else 0

    def read_raw_file(self) -> str:
        if not self.path.exists() or not self.path.is_file():
            return ""
        return self.path.read_text(encoding="utf-8").strip()

    def _load(self) -> dict[int, set[str]]:
        if self.path.exists() and not self.path.is_file():
            raise ConfigError(f"{self.path.name} должен быть файлом, но сейчас это директория.")
        if not self.path.exists():
            self._write_empty_file()
            return {}

        try:
            raw_data = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as error:
            raise ConfigError(f"Не удалось прочитать {self.path.name}: {error}") from error

        if not isinstance(raw_data, dict):
            raise ConfigError(f"{self.path.name} должен содержать YAML-словарь.")

        raw_users = raw_data.get("users", {})
        if not isinstance(raw_users, dict):
            raise ConfigError(f"Раздел users в {self.path.name} должен быть словарём.")

        user_topics: dict[int, set[str]] = {}
        for raw_user_id, raw_user_data in raw_users.items():
            user_id = _parse_user_id(raw_user_id)
            raw_topics = _extract_topics(raw_user_data, user_id)
            topics = {
                str(topic_key).strip().lower()
                for topic_key in raw_topics
                if str(topic_key).strip()
            }
            if topics:
                user_topics[user_id] = topics
        return user_topics

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = self._build_yaml_data()
        serialized_data = yaml.safe_dump(data, allow_unicode=True, sort_keys=True)
        logger.info("Saving topic access: path=%s data=%s", self.path, data)
        try:
            with self.path.open("w", encoding="utf-8") as access_file:
                access_file.write(serialized_data)
                access_file.flush()
                os.fsync(access_file.fileno())
        except OSError as error:
            raise RuntimeError(f"Не удалось сохранить {self.path.name}: {error}") from error

        try:
            saved_text = self.path.read_text(encoding="utf-8")
            saved_data = yaml.safe_load(saved_text) or {}
        except (OSError, yaml.YAMLError) as error:
            raise RuntimeError(f"Не удалось проверить сохранение {self.path.name}: {error}") from error

        if saved_data != data:
            raise RuntimeError(
                f"После сохранения {self.path.name} содержимое файла не совпадает с памятью."
            )
        logger.info(
            "Topic access saved: path=%s bytes=%s users_count=%s",
            self.path,
            len(saved_text.encode("utf-8")),
            len(self._user_topics),
        )

    def _build_yaml_data(self) -> dict[str, dict[str, dict[str, list[str]]]]:
        return {
            "users": {
                str(user_id): {"topics": sorted(topics)}
                for user_id, topics in sorted(self._user_topics.items())
            }
        }

    def _write_empty_file(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as access_file:
            access_file.write("users: {}\n")
            access_file.flush()
            os.fsync(access_file.fileno())


def is_admin_user(user_id: int | None, settings: BotSettings) -> bool:
    return user_id is not None and user_id in settings.admin_ids


def is_superadmin(user_id: int | None, settings: BotSettings) -> bool:
    return is_admin_user(user_id, settings)


def get_user_topic_keys(user_id: int | None, store: TopicAccessStore) -> list[str]:
    if user_id is None:
        return []
    return store.get_user_topics(user_id)


def has_any_topic_access(
    user_id: int | None,
    settings: BotSettings,
    store: TopicAccessStore,
) -> bool:
    if is_superadmin(user_id, settings):
        return True
    return bool(get_user_topic_keys(user_id, store))


def can_use_bot_service_commands(
    user_id: int | None,
    settings: BotSettings,
    store: TopicAccessStore,
) -> bool:
    return has_any_topic_access(user_id, settings, store)


def can_use_bot_command(
    command_key: str,
    user_id: int | None,
    settings: BotSettings,
    store: TopicAccessStore,
    bot_commands_config: BotCommandsConfig,
) -> bool:
    return get_bot_command_denial_reason(
        command_key,
        user_id,
        settings,
        store,
        bot_commands_config,
    ) is None


def get_bot_command_denial_reason(
    command_key: str,
    user_id: int | None,
    settings: BotSettings,
    store: TopicAccessStore,
    bot_commands_config: BotCommandsConfig,
) -> str | None:
    command = bot_commands_config.commands[command_key]
    user_is_superadmin = is_superadmin(user_id, settings)
    logger.debug(
        "Access check: command=%s user_id=%s is_superadmin=%s access=%s enabled=%s",
        command_key,
        user_id,
        user_is_superadmin,
        command.access,
        command.enabled,
    )
    if not command.enabled:
        return BOT_COMMAND_DENIAL_DISABLED
    if command.access == BOT_COMMAND_ACCESS_SUPERADMIN:
        if user_is_superadmin:
            return None
        if has_any_topic_access(user_id, settings, store):
            return BOT_COMMAND_DENIAL_ADMIN_ONLY
        return BOT_COMMAND_DENIAL_NO_BOT_ACCESS
    if has_any_topic_access(user_id, settings, store):
        return None
    return BOT_COMMAND_DENIAL_NO_BOT_ACCESS


def can_manage_access(user_id: int | None, settings: BotSettings) -> bool:
    return is_superadmin(user_id, settings)


def can_use_topic(user_id: int | None, topic_key: str, settings: BotSettings, store: TopicAccessStore) -> bool:
    if is_superadmin(user_id, settings):
        return True
    if user_id is None:
        return False
    return store.has_access(user_id, topic_key)


def _parse_user_id(raw_user_id: Any) -> int:
    try:
        return int(raw_user_id)
    except (TypeError, ValueError) as error:
        raise ConfigError(f"user_id {raw_user_id} в {ACCESS_FILE_NAME} должен быть целым числом.") from error


def _normalize_topic_key(topic_key: str) -> str:
    return str(topic_key).strip().lower()


def _extract_topics(raw_user_data: Any, user_id: int) -> list[Any]:
    if isinstance(raw_user_data, dict):
        raw_topics = raw_user_data.get("topics", [])
    else:
        raw_topics = raw_user_data

    if not isinstance(raw_topics, list):
        raise ConfigError(f"topics пользователя {user_id} в {ACCESS_FILE_NAME} должен быть списком.")
    return raw_topics
