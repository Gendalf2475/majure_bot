# RCON Telegram Bot для Paper-серверов

Telegram-бот для управления несколькими Minecraft Paper-серверами через RCON. Подходит для сети через BungeeCord: бот подключается не к BungeeCord, а к каждому отдельному Paper-серверу.

## Возможности

- Команды вида `/test list`, `/lobby say Привет`, `/survival list`.
- Серверы и Telegram-команды загружаются из локального `servers.yml`.
- Разрешённые Minecraft-команды задаются whitelist-списком `allowed_commands`.
- Доступ ограничен одной беседой из `ALLOWED_CHAT_ID`.
- `/chatid` работает в любом чате, чтобы узнать ID нужной беседы.
- Есть cooldown, RCON timeout, DRY_RUN и техническое логирование без вывода токенов, RCON-паролей и приватных host:port.

## Структура

```text
rcon-telegram-bot/
  bot.py
  app/
    config/
      settings.py
      servers.py
    handlers/
      common.py
      server_commands.py
    middlewares/
      access.py
      cooldown.py
    services/
      rcon_service.py
      server_service.py
    utils/
      logging.py
      text.py
      validation.py
  .env.example
  servers.yml.example
  .gitignore
  SECURITY.md
  requirements.txt
  README.md
```

Файлы `config.py`, `permissions.py` и `rcon_client.py` оставлены как совместимые обёртки для старых импортов. Основная логика находится в папке `app/`.

## Безопасная подготовка к GitHub

В репозиторий должны попадать только шаблоны конфигов:

- `.env.example`
- `servers.yml.example`

Реальные локальные файлы не коммитятся:

- `.env`
- `.env.*`
- `*.env`
- `servers.yml`
- `allowed_commands.yml`
- логи, базы, backup-файлы и `.DS_Store`

Перед первым push проверьте staged-файлы:

```bash
git status --short
git diff --cached --name-only
```

Если секрет уже был закоммичен, простого удаления файла недостаточно: нужно отозвать токен или пароль, очистить git history и только потом публиковать репозиторий.

## 1. Создание Telegram-бота через BotFather

1. Откройте Telegram.
2. Найдите `@BotFather`.
3. Отправьте команду `/newbot`.
4. Укажите имя бота.
5. Укажите username бота, который заканчивается на `bot`, например `MyRconAdminBot`.

## 2. Как получить TELEGRAM_BOT_TOKEN

После создания бота BotFather выдаст токен вида:

```text
1234567890:AA...
```

Скопируйте его только в локальный `.env`:

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
```

Никому не отправляйте токен и не публикуйте `.env`. Для GitHub используйте только `.env.example`.

## 3. Как узнать ID беседы через /chatid

1. Добавьте бота в нужную группу или супергруппу.
2. Временно укажите любой числовой `ALLOWED_CHAT_ID` в `.env`, например:

```env
ALLOWED_CHAT_ID=0
```

3. Запустите бота.
4. В нужной беседе отправьте:

```text
/chatid
```

Бот ответит:

```text
Chat ID этой беседы: -1001234567890
```

5. Скопируйте это число в локальный `.env`.

## 4. Как заполнить .env

Создайте локальный файл `.env` рядом с `bot.py`:

```bash
cp .env.example .env
```

Заполните реальные значения только в `.env`:

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
ALLOWED_CHAT_ID=-1001234567890
COMMAND_COOLDOWN_SECONDS=2
RCON_TIMEOUT_SECONDS=5
DRY_RUN=false
```

Пояснения:

- `TELEGRAM_BOT_TOKEN` — токен от BotFather.
- `ALLOWED_CHAT_ID` — ID единственной беседы, где бот выполняет команды.
- `COMMAND_COOLDOWN_SECONDS` — задержка между RCON-командами от одного пользователя.
- `RCON_TIMEOUT_SECONDS` — сколько секунд ждать ответа RCON.
- `DRY_RUN=true` — бот покажет, какую команду выполнил бы, но не отправит её в RCON. DRY_RUN применяется только к серверным командам; `/status` и `/players` выполняют реальные RCON-проверки.

Важно: любой пользователь, который может писать в беседу `ALLOWED_CHAT_ID`, сможет отправлять разрешённые команды боту. Добавляйте бота только в доверенную беседу.

## 5. Как заполнить servers.yml

Создайте локальный файл:

```bash
cp servers.yml.example servers.yml
```

Пример шаблона:

```yaml
servers:
  lobby:
    display_name: "Lobby"
    host: "127.0.0.1"
    port: 25575
    password: "CHANGE_ME"
    telegram_command: "lobby"

  test:
    display_name: "Test"
    host: "127.0.0.1"
    port: 25576
    password: "CHANGE_ME"
    telegram_command: "test"

  survival:
    display_name: "Survival"
    host: "127.0.0.1"
    port: 25577
    password: "CHANGE_ME"
    telegram_command: "survival"

allowed_commands:
  - "list"
  - "say"
```

`allowed_commands` — это whitelist. Бот берёт первую часть Minecraft-команды и сравнивает её со списком без учёта регистра. Если список пустой, запрещены все пользовательские Minecraft-команды.

Держите whitelist минимальным. Не добавляйте опасные команды вроде `op`, `deop`, `stop`, `reload`, permission-management-команды или произвольные plugin console-команды, если всем участникам Telegram-беседы нельзя полностью доверять.

Примеры:

- `/test list` проверяет `list`.
- `/test say Привет` проверяет `say`.

## 6. Как включить RCON на Paper-сервере

В файле `server.properties` каждого Paper-сервера включите RCON:

```properties
enable-rcon=true
rcon.port=25575
rcon.password=your_strong_unique_password
```

Для каждого сервера порт должен быть свой:

```text
lobby: 25575
test: 25576
survival: 25577
```

После изменения `server.properties` перезапустите Paper-сервер.

RCON — административный интерфейс. Не открывайте RCON-порты в публичный интернет без firewall, VPN или другой строгой сетевой защиты.

## 7. Установка зависимостей

Нужен Python 3.11+.

```bash
pip install -r requirements.txt
```

## 8. Запуск

Запускайте из папки проекта:

```bash
python bot.py
```

При старте бот проверит `.env`, `servers.yml`, список серверов, обязательные поля серверов и раздел `allowed_commands`. Если конфигурация некорректна, бот напишет понятную ошибку в консоль и не запустится.

## 9. Примеры использования

```text
/test list
/test say Привет
/lobby list
/survival list
/status
/players
/ping
```

Формат серверной команды:

```text
/<telegram_command> <minecraft_command>
```

Например, при сообщении:

```text
/test list
```

бот отправит в RCON сервера `test` только:

```text
list
```

## 10. Частые ошибки

- Неправильный RCON-пароль в локальном `servers.yml`.
- RCON выключен в `server.properties`.
- Порт RCON занят другим процессом.
- Firewall или правила хостинга блокируют порт.
- Команда не добавлена в `allowed_commands`.
- `ALLOWED_CHAT_ID` не настроен или указан неверно.
- Команда отправлена не из разрешённой беседы.
- Бот запущен не из той папки.
- У Paper-сервера и `servers.yml` не совпадают `rcon.port` или `rcon.password`.

## 11. Команды для BotFather /setcommands

Отправьте BotFather команду `/setcommands` и вставьте:

```text
start - Информация о боте
help - Помощь
servers - Список серверов
status - Статус RCON-серверов
players - Онлайн игроков на всех серверах
chatid - Показать ID текущей беседы
ping - Проверить работу бота
lobby - Выполнить команду на Lobby
test - Выполнить команду на Test
survival - Выполнить команду на Survival
```

## Безопасность

- Не храните реальные секреты в репозитории.
- Не отправляйте RCON-пароли в Telegram.
- Не публикуйте `.env` и `servers.yml`.
- Используйте `.env.example` и `servers.yml.example` только как шаблоны.
- Бот не пишет Telegram token и RCON-пароли в логи.
- Дополнительные рекомендации находятся в `SECURITY.md`.
