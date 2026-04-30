from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app.config.servers import ServersConfig
from app.config.settings import ConfigError


@dataclass(frozen=True)
class TopicConfig:
    key: str
    display_name: str
    server_key: str
    thread_id: int


@dataclass(frozen=True)
class TopicsConfig:
    topics: dict[str, TopicConfig]
    topics_by_thread_id: dict[int, TopicConfig]
    topics_by_server_key: dict[str, TopicConfig]


def load_topics_config(
    servers_config: ServersConfig,
    base_dir: Path | None = None,
) -> TopicsConfig:
    # topics.yml лежит рядом с bot.py. Если файла нет, топиковая логика просто не активируется.
    project_dir = base_dir or Path(__file__).resolve().parents[2]
    path = project_dir / "topics.yml"
    if not path.exists():
        return TopicsConfig(topics={}, topics_by_thread_id={}, topics_by_server_key={})
    return _load_topics(path, servers_config)


def _load_topics(path: Path, servers_config: ServersConfig) -> TopicsConfig:
    try:
        raw_data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise ConfigError(f"Не удалось прочитать {path.name}: {error}") from error

    if not isinstance(raw_data, dict):
        raise ConfigError("topics.yml должен содержать YAML-словарь.")

    raw_topics = raw_data.get("topics")
    if raw_topics is None:
        return TopicsConfig(topics={}, topics_by_thread_id={}, topics_by_server_key={})
    if not isinstance(raw_topics, dict):
        raise ConfigError("Раздел topics в topics.yml должен быть словарём.")

    topics: dict[str, TopicConfig] = {}
    topics_by_thread_id: dict[int, TopicConfig] = {}
    topics_by_server_key: dict[str, TopicConfig] = {}

    for raw_topic_key, raw_topic_data in raw_topics.items():
        if not isinstance(raw_topic_data, dict):
            raise ConfigError(f"Топик {raw_topic_key} должен быть YAML-словарём.")

        topic_key = str(raw_topic_key).strip().lower()
        if not topic_key:
            raise ConfigError("Ключ топика в topics.yml не должен быть пустым.")

        display_name = _get_required_yaml_string(raw_topic_data, "display_name", topic_key)
        server_key = _get_required_yaml_string(raw_topic_data, "server", topic_key).lower()
        if server_key not in servers_config.servers:
            raise ConfigError(
                f"Топик {topic_key} ссылается на неизвестный сервер {server_key}."
            )

        thread_id = _parse_thread_id(raw_topic_data.get("thread_id"), topic_key)
        topic = TopicConfig(
            key=topic_key,
            display_name=display_name,
            server_key=server_key,
            thread_id=thread_id,
        )

        if topic_key in topics:
            raise ConfigError(f"Топик {topic_key} указан несколько раз.")
        if thread_id in topics_by_thread_id:
            other_topic = topics_by_thread_id[thread_id]
            raise ConfigError(
                f"thread_id {thread_id} используется сразу для топиков "
                f"{other_topic.key} и {topic.key}."
            )
        if server_key in topics_by_server_key:
            other_topic = topics_by_server_key[server_key]
            raise ConfigError(
                f"Сервер {server_key} привязан сразу к топикам "
                f"{other_topic.key} и {topic.key}."
            )

        topics[topic_key] = topic
        topics_by_thread_id[thread_id] = topic
        topics_by_server_key[server_key] = topic

    return TopicsConfig(
        topics=topics,
        topics_by_thread_id=topics_by_thread_id,
        topics_by_server_key=topics_by_server_key,
    )


def _get_required_yaml_string(data: dict[str, Any], field_name: str, topic_key: str) -> str:
    value = data.get(field_name)
    if value is None or not str(value).strip():
        raise ConfigError(f"У топика {topic_key} не заполнено поле {field_name}.")
    return str(value).strip()


def _parse_thread_id(value: Any, topic_key: str) -> int:
    if value is None:
        raise ConfigError(f"У топика {topic_key} не заполнено поле thread_id.")
    try:
        thread_id = int(value)
    except (TypeError, ValueError) as error:
        raise ConfigError(f"У топика {topic_key} поле thread_id должно быть числом.") from error
    if thread_id <= 0:
        raise ConfigError(f"У топика {topic_key} thread_id должен быть положительным числом.")
    return thread_id
