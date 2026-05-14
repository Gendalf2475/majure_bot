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
    "diag",
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
    rcon_commands: tuple[str, ...]
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

    rcon_commands = _build_rcon_commands(alias, args)
    if not rcon_commands:
        return None

    return ParsedAliasCommand(
        alias=alias,
        input=alias.input,
        args=args,
        rcon_commands=rcon_commands,
        show_response=alias.show_response,
        success_message=alias.success_message,
    )


def _build_rcon_commands(alias: CommandAlias, args: str) -> tuple[str, ...]:
    templates = alias.execute if isinstance(alias.execute, list) else [alias.execute]
    commands: list[str] = []
    for template in templates:
        command = _build_rcon_command(template, args)
        if command:
            commands.append(command)
    return tuple(commands)


def _build_rcon_command(template: str, args: str) -> str:
    if "{args}" not in template:
        return template.strip()
    return template.replace("{args}", args).strip()
