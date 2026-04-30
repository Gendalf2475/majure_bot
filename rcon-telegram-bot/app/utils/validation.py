from __future__ import annotations


SERVICE_COMMANDS = {
    "start",
    "help",
    "servers",
    "status",
    "players",
    "chatid",
    "ping",
}


def parse_telegram_command(text: str) -> tuple[str, str]:
    # Разбираем "/test list" на command="test" и arguments="list".
    # Если Telegram добавит username бота: "/test@MyBot list", username будет отрезан.
    stripped = text.strip()
    first_part, _, arguments = stripped.partition(" ")
    command = first_part.removeprefix("/").split("@", maxsplit=1)[0].lower()
    return command, arguments.strip()


def is_minecraft_command_allowed(minecraft_command: str, allowed_commands: frozenset[str]) -> bool:
    # Пустой whitelist означает, что пользовательские Minecraft-команды запрещены.
    if not allowed_commands:
        return False

    # Проверяем только первое слово: "lp user ..." разрешается по "lp".
    command_root = minecraft_command.strip().split(maxsplit=1)[0].lower()
    if not command_root:
        return False

    return command_root in allowed_commands
