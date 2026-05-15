from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.config.bot_commands import BOT_COMMAND_ACCESS_SUPERADMIN, load_bot_commands_config
from app.config.servers import (
    ALIAS_ACCESS_ADMIN,
    ALIAS_ACCESS_SUPERADMIN,
    CommandAlias,
    ServerConfig,
    ServersConfig,
)
from app.config.settings import BotSettings, ConfigError
from app.config.topics import TopicConfig, TopicsConfig
from app.handlers.common import NO_BOT_ACCESS_MESSAGE, handle_help
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

    async def test_grant_notifies_current_chat_when_access_is_new(self) -> None:
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

            self.assertEqual(
                message.answers,
                ["✅ Пользователю 5344860685 выдан доступ к режиму Test."],
            )
            self.assertTrue(store.has_access(5344860685, "test"))

    async def test_grant_notifies_current_chat_when_access_already_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            message = _AnsweringMessage("/grant 5344860685 test", from_user_id=1)
            store = TopicAccessStore(Path(tmp_dir) / "topic_access.yml")
            store.grant_access(5344860685, "test")

            await handle_grant_access(
                message,
                settings=_settings(admin_ids=frozenset({1})),
                topics_config=_topics_config(),
                topic_access_store=store,
                bot_commands_config=load_bot_commands_config(Path(tmp_dir)),
            )

            self.assertEqual(
                message.answers,
                ["✅ У пользователя 5344860685 уже есть доступ к режиму Test."],
            )

    async def test_revoke_notifies_current_chat_when_access_is_removed(self) -> None:
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

            self.assertEqual(
                message.answers,
                ["✅ У пользователя 5344860685 отозван доступ к режиму Test."],
            )
            self.assertFalse(store.has_access(5344860685, "test"))

    async def test_revoke_notifies_current_chat_when_access_did_not_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            message = _AnsweringMessage("/revoke 5344860685 test", from_user_id=1)
            store = TopicAccessStore(Path(tmp_dir) / "topic_access.yml")

            await handle_revoke_access(
                message,
                settings=_settings(admin_ids=frozenset({1})),
                topics_config=_topics_config(),
                topic_access_store=store,
                bot_commands_config=load_bot_commands_config(Path(tmp_dir)),
            )

            self.assertEqual(
                message.answers,
                ["ℹ️ У пользователя 5344860685 не было доступа к режиму Test."],
            )

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


class HelpCommandTest(unittest.IsolatedAsyncioTestCase):
    async def test_superadmin_help_has_servers_and_server_commands_without_topics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            message = _AnsweringMessage("/help", from_user_id=1)

            await handle_help(
                message,
                settings=_settings(admin_ids=frozenset({1})),
                servers_config=_servers_config(),
                topics_config=_multi_topics_config(),
                topic_access_store=TopicAccessStore(Path(tmp_dir) / "topic_access.yml"),
                bot_commands_config=load_bot_commands_config(Path(tmp_dir)),
            )

            self.assertEqual(len(message.answers), 1)
            text = message.answers[0]
            self.assertIn("🛠 Команды администратора:", text)
            self.assertIn("Служебные:\n• /start — Информация о боте", text)
            self.assertIn("• /ping — Проверить работу бота", text)
            self.assertIn("• /grant <user_id> <topic_key> — Выдать доступ к режиму", text)
            self.assertIn("Серверы:\n• /test — Test\n• /polit — Polit", text)
            self.assertIn("Серверные команды:\n• ban — Забанить игрока", text)
            self.assertIn("• root — Суперадминская команда", text)
            self.assertNotIn("Топики:", text)
            self.assertNotIn("<alias>", text)
            self.assertNotIn("disabled", text)
            self.assertNotIn("Алиасы:", text)

    async def test_admin_help_shows_only_accessible_servers_and_admin_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            message = _AnsweringMessage("/help", from_user_id=2)
            store = TopicAccessStore(Path(tmp_dir) / "topic_access.yml")
            store.grant_access(2, "test")

            await handle_help(
                message,
                settings=_settings(admin_ids=frozenset({1})),
                servers_config=_servers_config(),
                topics_config=_multi_topics_config(),
                topic_access_store=store,
                bot_commands_config=load_bot_commands_config(Path(tmp_dir)),
            )

            self.assertEqual(len(message.answers), 1)
            text = message.answers[0]
            self.assertIn("🛠 Доступные команды:", text)
            self.assertIn("Серверы:\n• /test — Test", text)
            self.assertIn("Серверные команды:\n• ban — Забанить игрока", text)
            self.assertIn("• /access — Показать выданные доступы", text)
            self.assertNotIn("• /polit — Polit", text)
            self.assertNotIn("/grant", text)
            self.assertNotIn("/revoke", text)
            self.assertNotIn("/chatid", text)
            self.assertNotIn("/ping", text)
            self.assertNotIn("root", text)
            self.assertNotIn("Топики:", text)
            self.assertNotIn("<alias>", text)
            self.assertNotIn("Алиасы:", text)

    async def test_help_without_access_is_denied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            message = _AnsweringMessage("/help", from_user_id=3)

            await handle_help(
                message,
                settings=_settings(admin_ids=frozenset({1})),
                servers_config=_servers_config(),
                topics_config=_multi_topics_config(),
                topic_access_store=TopicAccessStore(Path(tmp_dir) / "topic_access.yml"),
                bot_commands_config=load_bot_commands_config(Path(tmp_dir)),
            )

            self.assertEqual(message.answers, [NO_BOT_ACCESS_MESSAGE])


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


def _multi_topics_config() -> TopicsConfig:
    test_topic = TopicConfig(
        key="test",
        display_name="Test",
        server_key="test",
        thread_id=1,
    )
    polit_topic = TopicConfig(
        key="polit",
        display_name="Polit",
        server_key="polit",
        thread_id=2,
    )
    return TopicsConfig(
        topics={"test": test_topic, "polit": polit_topic},
        topics_by_thread_id={1: test_topic, 2: polit_topic},
        topics_by_server_key={"test": test_topic, "polit": polit_topic},
    )


def _servers_config() -> ServersConfig:
    test_server = ServerConfig(
        key="test",
        display_name="Test",
        host="127.0.0.1",
        port=25575,
        password="password",
        telegram_command="test",
    )
    polit_server = ServerConfig(
        key="polit",
        display_name="Polit",
        host="127.0.0.1",
        port=25576,
        password="password",
        telegram_command="polit",
    )
    ban_alias = CommandAlias(
        key="ban",
        input="ban",
        execute="ban {args}",
        show_response=True,
        success_message=None,
        enabled=True,
        access=ALIAS_ACCESS_ADMIN,
        description="Забанить игрока",
    )
    root_alias = CommandAlias(
        key="root",
        input="root",
        execute="op {args}",
        show_response=True,
        success_message=None,
        enabled=True,
        access=ALIAS_ACCESS_SUPERADMIN,
        description="Суперадминская команда",
    )
    disabled_alias = CommandAlias(
        key="disabled",
        input="disabled",
        execute="say disabled",
        show_response=True,
        success_message=None,
        enabled=False,
        access=ALIAS_ACCESS_ADMIN,
        description="Отключённая команда",
    )
    return ServersConfig(
        servers={"test": test_server, "polit": polit_server},
        servers_by_command={"test": test_server, "polit": polit_server},
        command_aliases={
            "ban": ban_alias,
            "root": root_alias,
            "disabled": disabled_alias,
        },
        command_aliases_by_input={
            "ban": ban_alias,
            "root": root_alias,
            "disabled": disabled_alias,
        },
        source_path=Path("servers.yml"),
        source_exists=True,
        source_keys=("servers", "command_aliases"),
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
    def test_missing_access_file_is_created_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "topic_access.yml"

            store = TopicAccessStore(path)

            self.assertEqual(store.get_user_topics(5344860685), [])
            self.assertEqual(path.read_text(encoding="utf-8"), "users: {}\n")

    def test_access_path_must_be_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "topic_access.yml"
            path.mkdir()

            with self.assertRaisesRegex(
                ConfigError,
                "topic_access.yml должен быть файлом, но сейчас это директория.",
            ):
                TopicAccessStore(path)

    def test_saved_access_survives_store_reload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "topic_access.yml"
            store = TopicAccessStore(path)

            self.assertTrue(store.grant_access(5344860685, "test"))
            self.assertEqual(
                path.read_text(encoding="utf-8"),
                "users:\n"
                "  '5344860685':\n"
                "    topics:\n"
                "    - test\n",
            )
            self.assertEqual(store.users_count(), 1)
            self.assertEqual(store.file_users_count(), 1)
            reloaded_store = TopicAccessStore(path)

            self.assertTrue(reloaded_store.has_access(5344860685, "test"))

            self.assertTrue(reloaded_store.revoke_access(5344860685, "test"))
            self.assertEqual(path.read_text(encoding="utf-8"), "users: {}\n")
            self.assertEqual(reloaded_store.users_count(), 0)
            self.assertEqual(reloaded_store.file_users_count(), 0)

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
