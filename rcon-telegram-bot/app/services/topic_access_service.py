from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.config.settings import BotSettings, ConfigError


ACCESS_FILE_NAME = "topic_access.yml"


class TopicAccessStore:
    def __init__(self, path: Path | None = None) -> None:
        project_dir = Path(__file__).resolve().parents[2]
        self.path = path or project_dir / ACCESS_FILE_NAME
        self._user_topics = self._load()

    def has_access(self, user_id: int, topic_key: str) -> bool:
        return topic_key in self._user_topics.get(user_id, set())

    def grant_access(self, user_id: int, topic_key: str) -> bool:
        topics = self._user_topics.setdefault(user_id, set())
        if topic_key in topics:
            return False
        topics.add(topic_key)
        self._save()
        return True

    def revoke_access(self, user_id: int, topic_key: str) -> bool:
        topics = self._user_topics.get(user_id)
        if not topics or topic_key not in topics:
            return False
        topics.remove(topic_key)
        if not topics:
            self._user_topics.pop(user_id, None)
        self._save()
        return True

    def get_user_topics(self, user_id: int) -> list[str]:
        return sorted(self._user_topics.get(user_id, set()))

    def _load(self) -> dict[int, set[str]]:
        if not self.path.exists():
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
        data = {
            "users": {
                str(user_id): {"topics": sorted(topics)}
                for user_id, topics in sorted(self._user_topics.items())
            }
        }
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp_path.write_text(
            yaml.safe_dump(data, allow_unicode=True, sort_keys=True),
            encoding="utf-8",
        )
        tmp_path.replace(self.path)


def is_admin_user(user_id: int | None, settings: BotSettings) -> bool:
    return user_id is not None and user_id in settings.admin_ids


def can_use_topic(user_id: int | None, topic_key: str, settings: BotSettings, store: TopicAccessStore) -> bool:
    if is_admin_user(user_id, settings):
        return True
    if user_id is None:
        return False
    return store.has_access(user_id, topic_key)


def _parse_user_id(raw_user_id: Any) -> int:
    try:
        return int(raw_user_id)
    except (TypeError, ValueError) as error:
        raise ConfigError(f"user_id {raw_user_id} в {ACCESS_FILE_NAME} должен быть целым числом.") from error


def _extract_topics(raw_user_data: Any, user_id: int) -> list[Any]:
    if isinstance(raw_user_data, dict):
        raw_topics = raw_user_data.get("topics", [])
    else:
        raw_topics = raw_user_data

    if not isinstance(raw_topics, list):
        raise ConfigError(f"topics пользователя {user_id} в {ACCESS_FILE_NAME} должен быть списком.")
    return raw_topics
