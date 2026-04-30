# Security Policy

## Supported Versions

This project does not currently use versioned releases. Security fixes should be applied to the latest code in the repository.

## Reporting a Vulnerability

If you find a vulnerability, do not publish working exploits, Telegram bot tokens, RCON passwords, real server IP addresses, chat IDs, or private logs in a public issue.

Use GitHub Private Vulnerability Reporting if it is enabled for the repository. If it is not enabled, open a minimal issue that describes the affected area without secrets and share sensitive details only through a private channel chosen by the repository owner.

## Secrets

Never commit real local configuration:

- `.env`
- `.env.*`
- `*.env`
- `servers.yml`
- `topics.yml`
- `topic_access.yml`
- logs, databases, and backups

Commit only template files such as `.env.example`, `servers.yml.example`, `topics.yml.example`, and `topic_access.yml.example`.

If a Telegram bot token, RCON password, server IP, or chat ID was committed or shared by mistake, treat it as compromised:

1. Revoke the Telegram bot token in BotFather and create a new one.
2. Change all affected RCON passwords.
3. Remove the secret from git history before publishing or sharing the repository.
4. Check GitHub secret scanning alerts after pushing.

## RCON Safety

Minecraft RCON should be treated as an administrative interface.

- Do not expose RCON ports to the public internet unless access is strictly firewalled.
- Prefer localhost, VPN, private network, or host firewall rules.
- Use unique strong RCON passwords for every server.
- Keep `allowed_commands` as small as possible.
- Avoid allowing high-impact commands such as `op`, `deop`, `stop`, `reload`, permission-management commands, or arbitrary plugin console commands unless every chat member is trusted.
- Test new configuration with `DRY_RUN=true` before enabling real command execution.

## Telegram Access

The bot first restricts commands by `ALLOWED_CHAT_ID`. RCON commands in forum topics additionally require per-topic access from `topic_access.yml` or a user ID listed in `ADMIN_IDS`. Add the bot only to trusted chats and keep group membership under control.
