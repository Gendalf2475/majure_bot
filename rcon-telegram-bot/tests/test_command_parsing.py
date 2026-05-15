from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.config.bot_commands import BOT_COMMAND_ACCESS_SUPERADMIN, load_bot_commands_config
from app.config.servers import ALIAS_ACCESS_ADMIN, CommandAlias
from app.config.settings import BotSettings, ConfigError
from app.config.topics import TopicConfig, TopicsConfig
from app.handlers.server_commands import handle_server_command
from app.handlers.topic_commands import (
    ADMIN_ONLY_MESSAGE,
    USER_ID_MUST_BE_NUMBER_MESSAGE,
    _parse_access_change_target,
    _parse_access_view_target,
    handle_access_list,
    handle_grant_access,
    handle_revoke_access,
    parse_access_target_from_args,
)
from app.services.topic_access_service import TopicAccessStore
from app.utils.validation import (
    SERVICE_COMMANDS,
    is_service_command,
    parse_alias_command,
    parse_telegram_command,
)


class CommandParsingTest(unittest.TestCase):
    def test_parse_telegram_command_splits_arguments_and_bot_username(self) -> None:
        self.assertEqual(
            parse_telegram_command("/grant 5344860685 test"),
            ("grant", "5344860685 test"),
        )
        self.assertEqual(
            parse_telegram_command("/grant@MajureRconBot 5344860685 test"),
            ("grant", "5344860685 test"),
        )
        self.assertEqual(
            parse_telegram_command("/revoke 5344860685 test"),
            ("revoke", "5344860685 test"),
        )
        self.assertEqual(
            parse_telegram_command("/revoke@MajureRconBot 5344860685 test"),
            ("revoke", "5344860685 test"),
        )

    def test_service_commands_include_reserved_names(self) -> None:
        expected = {
            "start",
            "help",
            "servers",
            "status",
            "players",
            "ping",
            "chatid",
            "grant",
            "revoke",
            "access",
            "cmd",
        }
        self.assertTrue(expected.issubset(SERVICE_COMMANDS))
        for command in expected:
            self.assertTrue(is_service_command(f"/{command}@MajureRconBot"))

    def test_service_command_names_are_not_aliases(self) -> None:
        alias = CommandAlias(
            key="grant_alias",
            input="grant",
            execute="say {args}",
            show_response=True,
            success_message=None,
            enabled=True,
            access=ALIAS_ACCESS_ADMIN,
            description="",
        )

        self.assertIsNone(parse_alias_command("grant test", {"grant": alias}))


class AccessCommandParsingTest(unittest.TestCase):
    def setUp(self) -> None:
        topic = TopicConfig(
            key="test",
            display_name="Test",
            server_key="test",
            thread_id=1,
        )
        self.topics_config = TopicsConfig(
            topics={"test": topic},
            topics_by_thread_id={1: topic},
            topics_by_server_key={"test": topic},
        )

    def test_two_argument_format_uses_explicit_user_id(self) -> None:
        target = parse_access_target_from_args("5344860685 test", self.topics_config)
        self.assertIsNotNone(target)
        assert target is not None
        user_id, topic = target
        self.assertEqual(user_id, 5344860685)
        self.assertEqual(topic.key, "test")

    def test_one_argument_format_is_invalid_even_with_reply(self) -> None:
        self.assertIsNone(parse_access_target_from_args("test", self.topics_config))
        self.assertEqual(
            _parse_access_change_target(
                _message("/grant test", reply_user_id=5344860685),
                self.topics_config,
                "grant",
            ),
            "❌ Неверный формат.\n"
            "Используйте: /grant <user_id> <topic_key>\n"
            "Пример: /grant 5344860685 test",
        )

    def test_invalid_user_id_has_specific_error(self) -> None:
        self.assertIsNone(parse_access_target_from_args("abc test", self.topics_config))
        self.assertEqual(
            _parse_access_change_target(
                _message("/grant abc test"),
                self.topics_config,
                "grant",
            ),
            USER_ID_MUST_BE_NUMBER_MESSAGE,
        )

    def test_unknown_topic_has_specific_error(self) -> None:
        self.assertIsNone(parse_access_target_from_args("5344860685 unknown", self.topics_config))
        self.assertEqual(
            _parse_access_change_target(
                _message("/revoke 5344860685 unknown"),
                self.topics_config,
                "revoke",
            ),
            "❌ Режим unknown не найден.",
        )

    def test_revoke_usage_text_is_strict(self) -> None:
        self.assertEqual(
            _parse_access_change_target(
                _message("/revoke test"),
                self.topics_config,
                "revoke",
            ),
            "❌ Неверный формат.\n"
            "Используйте: /revoke <user_id> <topic_key>\n"
            "Пример: /revoke 5344860685 test",
        )

    def test_access_view_usage_text_is_strict(self) -> None:
        self.assertEqual(
            _parse_access_view_target("abc"),
            "❌ Неверный формат.\n"
            "Используйте: /access [user_id]\n"
            "Пример: /access 5344860685",
        )


class AccessCommandHandlerTest(unittest.IsolatedAsyncioTestCase):
    async def test_grant_is_superadmin_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            message = _AnsweringMessage("/grant 5344860685 test", from_user_id=111)
            store = TopicAccessStore(Path(tmp_dir) / "topic_access.yml")

            await handle_grant_access(
                message,
                settings=_settings(admin_ids=frozenset()),
                topics_config=_topics_config(),
                topic_access_store=store,
                bot_commands_config=load_bot_commands_config(Path(tmp_dir)),
            )

            self.assertEqual(message.answers, [ADMIN_ONLY_MESSAGE])
            self.assertFalse(store.has_access(5344860685, "test"))

    async def test_grant_uses_strict_two_argument_format(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            message = _AnsweringMessage("/grant 5344860685 test", from_user_id=1)
            store = TopicAccessStore(Path(tmp_dir) / "topic_access.yml")

            await handle_grant_access(
                message,
                settings=_settings(admin_ids=frozenset({1})),
                topics_config=_topics_config(),
                topic_access_store=store,
                bot_commands_config=load_bot_commands_config(Path(tmp_dir)),
            )

            self.assertEqual(message.answers, ["✅ Доступ к Test выдан пользователю 5344860685."])
            self.assertTrue(store.has_access(5344860685, "test"))

    async def test_revoke_uses_strict_two_argument_format(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            message = _AnsweringMessage("/revoke 5344860685 test", from_user_id=1)
            store = TopicAccessStore(Path(tmp_dir) / "topic_access.yml")
            store.grant_access(5344860685, "test")

            await handle_revoke_access(
                message,
                settings=_settings(admin_ids=frozenset({1})),
                topics_config=_topics_config(),
                topic_access_store=store,
                bot_commands_config=load_bot_commands_config(Path(tmp_dir)),
            )

            self.assertEqual(message.answers, ["✅ Доступ к Test отозван у пользователя 5344860685."])
            self.assertFalse(store.has_access(5344860685, "test"))

    async def test_access_target_user_shows_topic_keys_for_superadmin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            message = _AnsweringMessage("/access 5344860685", from_user_id=1)
            store = TopicAccessStore(Path(tmp_dir) / "topic_access.yml")
            store.grant_access(5344860685, "test")

            await handle_access_list(
                message,
                settings=_settings(admin_ids=frozenset({1})),
                topics_config=_topics_config(),
                topic_access_store=store,
                bot_commands_config=load_bot_commands_config(Path(tmp_dir)),
            )

            self.assertEqual(
                message.answers,
                ["✅ Доступ пользователя 5344860685:\n• Test (test)"],
            )

    async def test_access_without_args_ignores_reply_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            message = _AnsweringMessage(
                "/access",
                from_user_id=1,
                reply_user_id=5344860685,
            )
            store = TopicAccessStore(Path(tmp_dir) / "topic_access.yml")

            await handle_access_list(
                message,
                settings=_settings(admin_ids=frozenset({1})),
                topics_config=_topics_config(),
                topic_access_store=store,
                bot_commands_config=load_bot_commands_config(Path(tmp_dir)),
            )

            self.assertEqual(
                message.answers,
                ["✅ Вы суперадмин\nДоступны все режимы:\n• Test (test)"],
            )


def _settings(*, admin_ids: frozenset[int]) -> BotSettings:
    return BotSettings(
        telegram_bot_token="token",
        allowed_chat_id=1,
        admin_ids=admin_ids,
        command_cooldown_seconds=0,
        rcon_timeout_seconds=5,
        dry_run=False,
    )


def _topics_config() -> TopicsConfig:
    topic = TopicConfig(
        key="test",
        display_name="Test",
        server_key="test",
        thread_id=1,
    )
    return TopicsConfig(
        topics={"test": topic},
        topics_by_thread_id={1: topic},
        topics_by_server_key={"test": topic},
    )


class ServerCommandRoutingTest(unittest.IsolatedAsyncioTestCase):
    async def test_service_command_is_ignored_by_server_handler(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            message = _AnsweringMessage("/grant 5344860685 test")

            await handle_server_command(
                message,
                settings=None,
                servers_config=None,
                topics_config=None,
                topic_access_store=None,
                bot_commands_config=load_bot_commands_config(Path(tmp_dir)),
            )

            self.assertEqual(message.answers, [])


class TopicAccessStoreTest(unittest.TestCase):
    def test_grant_and_revoke_normalize_topic_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = TopicAccessStore(Path(tmp_dir) / "topic_access.yml")

            self.assertTrue(store.grant_access(5344860685, " Test "))
            self.assertTrue(store.has_access(5344860685, "test"))
            self.assertFalse(store.grant_access(5344860685, "TEST"))
            self.assertTrue(store.revoke_access(5344860685, " test "))
            self.assertFalse(store.has_access(5344860685, "test"))


class BotCommandsConfigTest(unittest.TestCase):
    def test_partial_superadmin_command_keeps_default_access(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "bot_commands.yml"
            path.write_text("bot_commands:\n  ping:\n    description: Pong\n", encoding="utf-8")

            config = load_bot_commands_config(Path(tmp_dir))

            self.assertEqual(config.commands["ping"].access, BOT_COMMAND_ACCESS_SUPERADMIN)
            self.assertEqual(config.commands["ping"].description, "Pong")

    def test_superadmin_only_command_rejects_admin_access(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "bot_commands.yml"
            path.write_text("bot_commands:\n  chatid:\n    access: admin\n", encoding="utf-8")

            with self.assertRaises(ConfigError):
                load_bot_commands_config(Path(tmp_dir))


def _message(
    text: str,
    *,
    reply_user_id: int | None = None,
    reply_is_bot: bool = False,
) -> SimpleNamespace:
    reply_to_message = None
    if reply_user_id is not None:
        reply_to_message = SimpleNamespace(
            from_user=SimpleNamespace(id=reply_user_id, is_bot=reply_is_bot),
        )
    return SimpleNamespace(text=text, reply_to_message=reply_to_message)


class _AnsweringMessage(SimpleNamespace):
    def __init__(
        self,
        text: str,
        *,
        from_user_id: int | None = None,
        reply_user_id: int | None = None,
    ) -> None:
        from_user = None
        if from_user_id is not None:
            from_user = SimpleNamespace(id=from_user_id)
        reply_to_message = None
        if reply_user_id is not None:
            reply_to_message = SimpleNamespace(from_user=SimpleNamespace(id=reply_user_id))
        super().__init__(text=text, from_user=from_user, reply_to_message=reply_to_message)
        self.answers: list[str] = []

    async def answer(self, text: str) -> None:
        self.answers.append(text)


if __name__ == "__main__":
    unittest.main()
