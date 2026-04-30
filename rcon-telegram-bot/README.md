# RCON Telegram Bot для Paper-серверов

Telegram-бот для управления несколькими Minecraft Paper-серверами через RCON. Подходит для сети через BungeeCord: бот подключается не к BungeeCord, а к каждому отдельному Paper-серверу.

## Возможности

- RCON-команды выполняются прямо в Telegram-топиках: например, напишите `list` в топике "Тест".
- Один Telegram-топик соответствует одному Minecraft-режиму из `topics.yml`.
- Серверы и Telegram-команды загружаются из локального `servers.yml`.
- Привязка Telegram-топиков к серверам загружается из локального `topics.yml`.
- Разрешённые Minecraft-команды задаются whitelist-списком `allowed_commands`.
- Доступ ограничен одной беседой из `ALLOWED_CHAT_ID`.
- Выдача доступа к режимам управляется через `ADMIN_IDS`, `/grant`, `/revoke` и локальный `topic_access.yml`.
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
      topics.py
    handlers/
      common.py
      server_commands.py
      topic_commands.py
    middlewares/
      access.py
      cooldown.py
    services/
      rcon_service.py
      server_service.py
      topic_access_service.py
    utils/
      logging.py
      text.py
      validation.py
  .env.example
  servers.yml.example
  topics.yml.example
  topic_access.yml.example
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
- `topics.yml.example`
- `topic_access.yml.example`

Реальные локальные файлы не коммитятся:

- `.env`
- `.env.*`
- `*.env`
- `servers.yml`
- `topics.yml`
- `topic_access.yml`
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
ADMIN_IDS=123456789
COMMAND_COOLDOWN_SECONDS=2
RCON_TIMEOUT_SECONDS=5
DRY_RUN=false
```

Пояснения:

- `TELEGRAM_BOT_TOKEN` — токен от BotFather.
- `ALLOWED_CHAT_ID` — ID единственной беседы, где бот выполняет команды.
- `ADMIN_IDS` — Telegram user_id суперадминов, которые могут выдавать и отзывать доступы к режимам.
- `COMMAND_COOLDOWN_SECONDS` — задержка между RCON-командами от одного пользователя.
- `RCON_TIMEOUT_SECONDS` — сколько секунд ждать ответа RCON.
- `DRY_RUN=true` — бот покажет, какую команду выполнил бы, но не отправит её в RCON. DRY_RUN применяется только к серверным командам; `/status` и `/players` выполняют реальные RCON-проверки.

Важно: бот принимает команды только в беседе `ALLOWED_CHAT_ID`. RCON-команды в топиках дополнительно требуют доступа к конкретному режиму или наличия пользователя в `ADMIN_IDS`.

## 5. Как заполнить servers.yml

Создайте локальный файл:

```bash
cp servers.yml.example servers.yml
```

Пример шаблона:

```yaml
servers:
  test:
    display_name: "Тест"
    host: "127.0.0.1"
    port: 25576
    password: "CHANGE_ME"
    telegram_command: "test"

  polit:
    display_name: "Полит"
    host: "127.0.0.1"
    port: 25577
    password: "CHANGE_ME"
    telegram_command: "polit"

allowed_commands:
  - "list"
  - "say"
```

`allowed_commands` — это whitelist. Бот берёт первую часть Minecraft-команды и сравнивает её со списком без учёта регистра. Если список пустой, запрещены все пользовательские Minecraft-команды.

Держите whitelist минимальным. Не добавляйте опасные команды вроде `op`, `deop`, `stop`, `reload`, permission-management-команды или произвольные plugin console-команды, если всем участникам Telegram-беседы нельзя полностью доверять.

Примеры:

- `list` в топике проверяет `list`.
- `say Привет` в топике проверяет `say`.

## 6. Как заполнить topics.yml

Создайте локальный файл:

```bash
cp topics.yml.example topics.yml
```

Пример:

```yaml
topics:
  test:
    display_name: "Тест"
    server: "test"
    thread_id: 22

  polit:
    display_name: "Полит"
    server: "polit"
    thread_id: 33
```

`thread_id` — это `message.message_thread_id` Telegram-топика. Не используйте название топика как идентификатор: название можно переименовать.

## 7. Доступы к режимам

Суперадмины задаются в `.env` через `ADMIN_IDS`. Они имеют доступ ко всем режимам и могут управлять локальным файлом `topic_access.yml` командами:

```text
/grant <user_id> <topic_key>
/revoke <user_id> <topic_key>
/access
```

Также можно ответить на сообщение пользователя:

```text
/grant test
/revoke polit
```

Пример локального файла:

```yaml
users:
  "123456789":
    topics:
      - "test"
      - "polit"
```

## 8. Как включить RCON на Paper-сервере

В файле `server.properties` каждого Paper-сервера включите RCON:

```properties
enable-rcon=true
rcon.port=25575
rcon.password=your_strong_unique_password
```

Для каждого сервера порт должен быть свой:

```text
test: 25576
polit: 25577
```

После изменения `server.properties` перезапустите Paper-сервер.

RCON — административный интерфейс. Не открывайте RCON-порты в публичный интернет без firewall, VPN или другой строгой сетевой защиты.

## 9. Установка зависимостей

Нужен Python 3.11+.

```bash
pip install -r requirements.txt
```

## 10. Запуск

Запускайте из папки проекта:

```bash
python bot.py
```

При старте бот проверит `.env`, `servers.yml`, `topics.yml`, список серверов, обязательные поля серверов и раздел `allowed_commands`. Если конфигурация некорректна, бот напишет понятную ошибку в консоль и не запустится.

## 11. Примеры использования

```text
list
say Привет
/test list
/polit list
/status
/players
/ping
```

Основной формат в топике:

```text
<minecraft_command>
```

Например, если сообщение отправлено в топике "Тест":

```text
list
```

бот отправит в RCON сервера `test` только:

```text
list
```

Старый формат `/<telegram_command> <minecraft_command>` сохранён для совместимости, но если сервер привязан к топику, доступ к режиму всё равно проверяется.

## 12. Частые ошибки

- Неправильный RCON-пароль в локальном `servers.yml`.
- RCON выключен в `server.properties`.
- Порт RCON занят другим процессом.
- Firewall или правила хостинга блокируют порт.
- Команда не добавлена в `allowed_commands`.
- `ALLOWED_CHAT_ID` не настроен или указан неверно.
- `ADMIN_IDS` не содержит user_id суперадмина.
- Топик не добавлен в `topics.yml` или указан неверный `thread_id`.
- Пользователю не выдан доступ к режиму через `/grant`.
- Команда отправлена не из разрешённой беседы.
- Бот запущен не из той папки.
- У Paper-сервера и `servers.yml` не совпадают `rcon.port` или `rcon.password`.

## 13. Команды для BotFather /setcommands

Отправьте BotFather команду `/setcommands` и вставьте:

```text
start - Информация о боте
help - Помощь
servers - Список серверов
status - Статус RCON-серверов
players - Онлайн игроков на всех серверах
chatid - Показать ID текущей беседы
ping - Проверить работу бота
grant - Выдать доступ к режиму
revoke - Отозвать доступ к режиму
access - Показать доступы к режимам
test - Выполнить команду на Тест
polit - Выполнить команду на Полит
```

## Безопасность

- Не храните реальные секреты в репозитории.
- Не отправляйте RCON-пароли в Telegram.
- Не публикуйте `.env`, `servers.yml`, `topics.yml` и `topic_access.yml`.
- Используйте `.env.example`, `servers.yml.example`, `topics.yml.example` и `topic_access.yml.example` только как шаблоны.
- Бот не пишет Telegram token и RCON-пароли в логи.
- Дополнительные рекомендации находятся в `SECURITY.md`.
