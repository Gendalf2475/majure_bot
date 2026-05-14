from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from app.config.servers import CommandAlias


SERVICE_COMMANDS = {
    "start",
    "help",
    "servers",
    "status",
    "players",
    "chatid",
    "ping",
    "cmd",
    "grant",
    "revoke",
    "access",
}


@dataclass(frozen=True)
class ParsedAliasCommand:
    alias: CommandAlias
    input: str
    args: str
    rcon_command: str
    show_response: bool
    success_message: str | None


def parse_telegram_command(text: str) -> tuple[str, str]:
    # Разбираем "/test list" на command="test" и arguments="list".
    # Если Telegram добавит username бота: "/test@MyBot list", username будет отрезан.
    stripped = text.strip()
    first_part, _, arguments = stripped.partition(" ")
    command = first_part.removeprefix("/").split("@", maxsplit=1)[0].lower()
    return command, arguments.strip()


def parse_alias_command(
    text: str,
    command_aliases_by_input: Mapping[str, CommandAlias],
) -> ParsedAliasCommand | None:
    stripped = text.strip()
    if not stripped:
        return None

    parts = stripped.split(maxsplit=1)
    input_command = parts[0].lower()
    args = parts[1].strip() if len(parts) == 2 else ""

    alias = command_aliases_by_input.get(input_command)
    if alias is None:
        return None

    rcon_command = _build_rcon_command(alias, args)
    if not rcon_command:
        return None

    return ParsedAliasCommand(
        alias=alias,
        input=alias.input,
        args=args,
        rcon_command=rcon_command,
        show_response=alias.show_response,
        success_message=alias.success_message,
    )


def _build_rcon_command(alias: CommandAlias, args: str) -> str:
    if "{args}" not in alias.execute:
        return alias.execute.strip()
    return alias.execute.replace("{args}", args).strip()
