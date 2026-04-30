from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from app.config.servers import ServersConfig
from app.config.settings import BotSettings
from app.config.topics import TopicConfig, TopicsConfig
from app.services.server_service import execute_server_command
from app.services.topic_access_service import (
    TopicAccessStore,
    can_use_topic,
    is_admin_user,
)
from app.utils.validation import is_minecraft_command_allowed, parse_telegram_command


topic_commands_router = Router()

FORBIDDEN_COMMAND_MESSAGE = "❌ Эта команда запрещена настройками бота."
NO_TOPIC_MESSAGE = "❌ RCON-команды работают только внутри топика, привязанного к серверу."
UNKNOWN_TOPIC_MESSAGE = "❌ Этот топик не привязан к серверу в topics.yml."
ADMIN_ONLY_MESSAGE = "⛔ Команда доступна только администраторам."


@topic_commands_router.message(Command("cmd"))
async def handle_topic_command(
    message: Message,
    settings: BotSettings,
    servers_config: ServersConfig,
    topics_config: TopicsConfig,
    topic_access_store: TopicAccessStore,
) -> None:
    _, minecraft_command = parse_telegram_command(message.text or "")
    if not minecraft_command:
        await message.answer("❌ Укажите команду Minecraft.\nПример: напишите list в нужном топике")
        return

    await _execute_topic_minecraft_command(
        message,
        minecraft_command,
        settings,
        servers_config,
        topics_config,
        topic_access_store,
    )


@topic_commands_router.message(F.text & ~F.text.startswith("/") & F.message_thread_id)
async def handle_topic_text_command(
    message: Message,
    settings: BotSettings,
    servers_config: ServersConfig,
    topics_config: TopicsConfig,
    topic_access_store: TopicAccessStore,
) -> None:
    minecraft_command = (message.text or "").strip()
    if not minecraft_command:
        return

    await _execute_topic_minecraft_command(
        message,
        minecraft_command,
        settings,
        servers_config,
        topics_config,
        topic_access_store,
    )


async def _execute_topic_minecraft_command(
    message: Message,
    minecraft_command: str,
    settings: BotSettings,
    servers_config: ServersConfig,
    topics_config: TopicsConfig,
    topic_access_store: TopicAccessStore,
) -> None:
    topic = await _get_topic_for_message(message, topics_config)
    if topic is None:
        return

    user_id = _get_user_id(message)
    if not can_use_topic(user_id, topic.key, settings, topic_access_store):
        await message.answer(f"⛔ У вас нет доступа к режиму {topic.display_name}.")
        return

    if not is_minecraft_command_allowed(minecraft_command, servers_config.allowed_commands):
        await message.answer(FORBIDDEN_COMMAND_MESSAGE)
        return

    server = servers_config.servers[topic.server_key]
    if settings.dry_run:
        await message.answer(
            "🧪 DRY RUN:\n"
            f"Топик: {topic.display_name}\n"
            f"Сервер: {server.display_name}\n"
            f"Команда: {minecraft_command}"
        )
        return

    await execute_server_command(message, server, minecraft_command, settings)


@topic_commands_router.message(Command("grant"))
async def handle_grant_access(
    message: Message,
    settings: BotSettings,
    topics_config: TopicsConfig,
    topic_access_store: TopicAccessStore,
) -> None:
    if not is_admin_user(_get_user_id(message), settings):
        await message.answer(ADMIN_ONLY_MESSAGE)
        return

    target = _parse_access_target(message, topics_config)
    if target is None:
        await message.answer(_access_usage("grant"))
        return

    user_id, topic = target
    changed = topic_access_store.grant_access(user_id, topic.key)
    if changed:
        await message.answer(f"✅ Доступ к {topic.display_name} выдан пользователю {user_id}.")
        return
    await message.answer(f"✅ У пользователя {user_id} уже есть доступ к {topic.display_name}.")


@topic_commands_router.message(Command("revoke"))
async def handle_revoke_access(
    message: Message,
    settings: BotSettings,
    topics_config: TopicsConfig,
    topic_access_store: TopicAccessStore,
) -> None:
    if not is_admin_user(_get_user_id(message), settings):
        await message.answer(ADMIN_ONLY_MESSAGE)
        return

    target = _parse_access_target(message, topics_config)
    if target is None:
        await message.answer(_access_usage("revoke"))
        return

    user_id, topic = target
    changed = topic_access_store.revoke_access(user_id, topic.key)
    if changed:
        await message.answer(f"✅ Доступ к {topic.display_name} отозван у пользователя {user_id}.")
        return
    await message.answer(f"✅ У пользователя {user_id} не было доступа к {topic.display_name}.")


@topic_commands_router.message(Command("access"))
async def handle_access_list(
    message: Message,
    settings: BotSettings,
    topics_config: TopicsConfig,
    topic_access_store: TopicAccessStore,
) -> None:
    target_user_id = _get_user_id(message)
    _, arguments = parse_telegram_command(message.text or "")
    if arguments or message.reply_to_message:
        if not is_admin_user(target_user_id, settings):
            await message.answer(ADMIN_ONLY_MESSAGE)
            return
        parsed_user_id = _parse_user_id_from_text(arguments) or _get_reply_user_id(message)
        if parsed_user_id is None:
            await message.answer(
                "❌ Укажите Telegram user_id или ответьте командой /access "
                "на сообщение пользователя."
            )
            return
        target_user_id = parsed_user_id

    if target_user_id is None:
        await message.answer("❌ Не удалось определить Telegram user_id.")
        return

    if is_admin_user(target_user_id, settings):
        await message.answer(_format_superadmin_access(target_user_id, message, topics_config))
        return

    topic_keys = topic_access_store.get_user_topics(target_user_id)
    if not topic_keys:
        await message.answer(f"ℹ️ У пользователя {target_user_id} нет выданных режимов.")
        return

    await message.answer(
        f"✅ Доступ пользователя {target_user_id}:\n"
        f"{_format_topic_keys(topic_keys, topics_config)}"
    )


async def _get_topic_for_message(message: Message, topics_config: TopicsConfig) -> TopicConfig | None:
    thread_id = message.message_thread_id
    if thread_id is None:
        await message.answer(NO_TOPIC_MESSAGE)
        return None
    topic = topics_config.topics_by_thread_id.get(thread_id)
    if topic is None:
        await message.answer(UNKNOWN_TOPIC_MESSAGE)
        return None
    return topic


def _parse_access_target(message: Message, topics_config: TopicsConfig) -> tuple[int, TopicConfig] | None:
    _, arguments = parse_telegram_command(message.text or "")
    parts = arguments.split()

    if len(parts) == 2:
        user_id = _parse_user_id(parts[0])
        topic = _get_topic_by_key(parts[1], topics_config)
        if user_id is None or topic is None:
            return None
        return user_id, topic

    if len(parts) == 1:
        user_id = _get_reply_user_id(message)
        topic = _get_topic_by_key(parts[0], topics_config)
        if user_id is None or topic is None:
            return None
        return user_id, topic

    return None


def _get_topic_by_key(topic_key: str, topics_config: TopicsConfig) -> TopicConfig | None:
    return topics_config.topics.get(topic_key.strip().lower())


def _parse_user_id(raw_user_id: str) -> int | None:
    try:
        return int(raw_user_id)
    except ValueError:
        return None


def _parse_user_id_from_text(text: str) -> int | None:
    parts = text.split()
    if len(parts) != 1:
        return None
    return _parse_user_id(parts[0])


def _get_reply_user_id(message: Message) -> int | None:
    if message.reply_to_message is None or message.reply_to_message.from_user is None:
        return None
    return message.reply_to_message.from_user.id


def _get_user_id(message: Message) -> int | None:
    return message.from_user.id if message.from_user else None


def _access_usage(command: str) -> str:
    return (
        "❌ Неверный формат.\n"
        f"Используйте: /{command} <user_id> <topic_key>\n"
        f"Или ответом на сообщение пользователя: /{command} <topic_key>"
    )


def _format_topic_keys(topic_keys: list[str], topics_config: TopicsConfig) -> str:
    lines: list[str] = []
    for topic_key in topic_keys:
        topic = topics_config.topics.get(topic_key)
        if topic is None:
            lines.append(f"• {topic_key}")
        else:
            lines.append(f"• {topic.display_name} ({topic.key})")
    return "\n".join(lines)


def _format_superadmin_access(
    target_user_id: int,
    message: Message,
    topics_config: TopicsConfig,
) -> str:
    if target_user_id == _get_user_id(message):
        prefix = "✅ Вы суперадмин"
    else:
        prefix = f"✅ Пользователь {target_user_id} — суперадмин."

    if not topics_config.topics:
        return f"{prefix}\nДоступны все режимы, но topics.yml пока пуст."
    topic_lines = _format_topic_keys(sorted(topics_config.topics), topics_config)
    return f"{prefix}\nДоступны все режимы:\n{topic_lines}"
