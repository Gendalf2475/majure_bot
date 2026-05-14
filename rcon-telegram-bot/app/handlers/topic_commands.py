from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from app.config.servers import ALIAS_ACCESS_SUPERADMIN, ServersConfig
from app.config.settings import BotSettings
from app.config.topics import TopicConfig, TopicsConfig
from app.services.server_service import execute_server_command
from app.services.topic_access_service import (
    TopicAccessStore,
    can_manage_access,
    can_use_topic,
    can_use_bot_service_commands,
    get_user_topic_keys,
    is_superadmin,
)
from app.utils.validation import ParsedAliasCommand, parse_alias_command, parse_telegram_command


topic_commands_router = Router()

FORBIDDEN_COMMAND_MESSAGE = "❌ Эта команда запрещена настройками бота."
DISABLED_COMMAND_MESSAGE = "❌ Эта команда временно отключена."
COMMAND_ACCESS_DENIED_MESSAGE = "⛔ У вас нет доступа к этой команде."
NO_TOPIC_MESSAGE = "❌ RCON-команды работают только внутри топика, привязанного к серверу."
UNKNOWN_TOPIC_MESSAGE = "❌ Этот топик не привязан к серверу в topics.yml."
ADMIN_ONLY_MESSAGE = "⛔ Команда доступна только администраторам."
NO_BOT_ACCESS_MESSAGE = "⛔ У вас нет доступа к этому боту.\nОбратитесь к администратору."
BOT_ACCESS_TARGET_MESSAGE = "❌ Нельзя изменить доступ боту."


@topic_commands_router.message(Command("cmd"))
async def handle_topic_command(
    message: Message,
    settings: BotSettings,
    servers_config: ServersConfig,
    topics_config: TopicsConfig,
    topic_access_store: TopicAccessStore,
) -> None:
    _, minecraft_command = parse_telegram_command(message.text or "")
    await _execute_topic_alias_command(
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
    command_text = (message.text or "").strip()
    if not command_text:
        return

    await _execute_topic_alias_command(
        message,
        command_text,
        settings,
        servers_config,
        topics_config,
        topic_access_store,
    )


async def _execute_topic_alias_command(
    message: Message,
    command_text: str,
    settings: BotSettings,
    servers_config: ServersConfig,
    topics_config: TopicsConfig,
    topic_access_store: TopicAccessStore,
) -> None:
    user_id = _get_user_id(message)
    if not can_use_bot_service_commands(user_id, settings, topic_access_store):
        await message.answer(NO_BOT_ACCESS_MESSAGE)
        return

    topic = await _get_topic_for_message(message, topics_config)
    if topic is None:
        return

    if not can_use_topic(user_id, topic.key, settings, topic_access_store):
        await message.answer(f"⛔ У вас нет доступа к режиму {topic.display_name}.")
        return

    if not command_text.strip():
        await message.answer("❌ Укажите алиас команды.\nПример: напишите list в нужном топике")
        return

    parsed_command = parse_alias_command(
        command_text,
        servers_config.command_aliases_by_input,
    )
    if parsed_command is None:
        await message.answer(FORBIDDEN_COMMAND_MESSAGE)
        return

    if not parsed_command.alias.enabled:
        await message.answer(DISABLED_COMMAND_MESSAGE)
        return

    if not _can_execute_alias_command(
        parsed_command,
        user_id,
        topic,
        settings,
        topic_access_store,
    ):
        await message.answer(COMMAND_ACCESS_DENIED_MESSAGE)
        return

    server = servers_config.servers[topic.server_key]
    if settings.dry_run:
        await message.answer(
            "🧪 DRY RUN:\n"
            f"Топик: {topic.display_name}\n"
            f"Сервер: {server.display_name}\n"
            f"Input alias: {parsed_command.input}\n"
            f"{_format_dry_run_commands(parsed_command.rcon_commands)}\n"
            f"show_response: {str(parsed_command.show_response).lower()}"
        )
        return

    await execute_server_command(
        message,
        server,
        parsed_command.rcon_commands,
        settings,
        show_response=parsed_command.show_response,
        success_message=parsed_command.success_message,
    )


def _can_execute_alias_command(
    parsed_command: ParsedAliasCommand,
    user_id: int | None,
    topic: TopicConfig,
    settings: BotSettings,
    topic_access_store: TopicAccessStore,
) -> bool:
    if parsed_command.alias.access == ALIAS_ACCESS_SUPERADMIN:
        return is_superadmin(user_id, settings)
    return can_use_topic(user_id, topic.key, settings, topic_access_store)


def _format_dry_run_commands(rcon_commands: tuple[str, ...]) -> str:
    if len(rcon_commands) == 1:
        return f"RCON-команда: {rcon_commands[0]}"
    return "RCON-команды:\n" + "\n".join(f"• {command}" for command in rcon_commands)


@topic_commands_router.message(Command("grant"))
async def handle_grant_access(
    message: Message,
    settings: BotSettings,
    topics_config: TopicsConfig,
    topic_access_store: TopicAccessStore,
) -> None:
    if not can_manage_access(_get_user_id(message), settings):
        await message.answer(ADMIN_ONLY_MESSAGE)
        return

    target = _parse_access_change_target(message, topics_config, "grant")
    if isinstance(target, str):
        await message.answer(target)
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
    if not can_manage_access(_get_user_id(message), settings):
        await message.answer(ADMIN_ONLY_MESSAGE)
        return

    target = _parse_access_change_target(message, topics_config, "revoke")
    if isinstance(target, str):
        await message.answer(target)
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
    sender_user_id = _get_user_id(message)
    _, arguments = parse_telegram_command(message.text or "")
    if not can_use_bot_service_commands(sender_user_id, settings, topic_access_store):
        await message.answer(NO_BOT_ACCESS_MESSAGE)
        return

    if arguments or message.reply_to_message:
        if not can_manage_access(sender_user_id, settings):
            await message.answer(ADMIN_ONLY_MESSAGE)
            return
        target_user_id = _parse_access_view_target(message, arguments)
        if isinstance(target_user_id, str):
            await message.answer(target_user_id)
            return
    else:
        target_user_id = sender_user_id

    if target_user_id is None:
        await message.answer("❌ Не удалось определить Telegram user_id.")
        return

    if is_superadmin(target_user_id, settings):
        await message.answer(_format_superadmin_access(target_user_id, message, topics_config))
        return

    topic_keys = get_user_topic_keys(target_user_id, topic_access_store)
    if not topic_keys:
        if target_user_id == sender_user_id and not can_use_bot_service_commands(
            sender_user_id,
            settings,
            topic_access_store,
        ):
            await message.answer(NO_BOT_ACCESS_MESSAGE)
            return
        await message.answer(f"ℹ️ У пользователя {target_user_id} нет выданных режимов.")
        return

    access_text = _format_topic_keys(
        topic_keys,
        topics_config,
        show_keys=can_manage_access(sender_user_id, settings),
    )
    await message.answer(f"✅ Доступ пользователя {target_user_id}:\n{access_text}")


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


def _parse_access_change_target(
    message: Message,
    topics_config: TopicsConfig,
    command: str,
) -> tuple[int, TopicConfig] | str:
    _, arguments = parse_telegram_command(message.text or "")
    parts = arguments.split()

    if message.reply_to_message is None:
        if len(parts) != 2:
            return _access_usage(command)
        user_id = _parse_user_id(parts[0])
        if user_id is None:
            return _access_usage(command)
        topic = _get_topic_by_key(parts[1], topics_config)
        if topic is None:
            return f"❌ Режим {parts[1]} не найден."
        return user_id, topic

    if len(parts) != 1:
        return _access_usage(command)

    user_id = _get_reply_user_id(message)
    if user_id is None:
        return _access_usage(command)
    if _is_reply_to_bot(message):
        return BOT_ACCESS_TARGET_MESSAGE
    topic = _get_topic_by_key(parts[0], topics_config)
    if topic is None:
        return f"❌ Режим {parts[0]} не найден."
    return user_id, topic


def _parse_access_view_target(message: Message, arguments: str) -> int | str | None:
    parts = arguments.split()

    if message.reply_to_message is None:
        if len(parts) != 1:
            return "❌ Неверный формат.\nИспользуйте: /access <user_id>"
        user_id = _parse_user_id(parts[0])
        if user_id is None:
            return "❌ Неверный формат.\nИспользуйте: /access <user_id>"
        return user_id

    if parts:
        return "❌ Неверный формат.\nИспользуйте /access ответом на сообщение пользователя."
    return _get_reply_user_id(message)


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


def _is_reply_to_bot(message: Message) -> bool:
    if message.reply_to_message is None or message.reply_to_message.from_user is None:
        return False
    return bool(message.reply_to_message.from_user.is_bot)


def _get_user_id(message: Message) -> int | None:
    return message.from_user.id if message.from_user else None


def _access_usage(command: str) -> str:
    return (
        "❌ Неверный формат.\n"
        f"Используйте: /{command} <user_id> <topic_key>\n"
        f"Или ответом на сообщение пользователя: /{command} <topic_key>"
    )


def _format_topic_keys(
    topic_keys: list[str],
    topics_config: TopicsConfig,
    *,
    show_keys: bool,
) -> str:
    lines: list[str] = []
    for topic_key in topic_keys:
        topic = topics_config.topics.get(topic_key)
        if topic is None:
            lines.append(f"• {topic_key}")
        elif show_keys:
            lines.append(f"• {topic.display_name} ({topic.key})")
        else:
            lines.append(f"• {topic.display_name}")
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
    topic_lines = _format_topic_keys(
        sorted(topics_config.topics),
        topics_config,
        show_keys=True,
    )
    return f"{prefix}\nДоступны все режимы:\n{topic_lines}"
