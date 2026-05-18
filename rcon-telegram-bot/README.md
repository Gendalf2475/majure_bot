# RCON Telegram Bot для Paper-серверов

Telegram-бот для управления несколькими Minecraft Paper-серверами через RCON. Подходит для сети через BungeeCord: бот подключается не к BungeeCord, а к каждому отдельному Paper-серверу.

## Возможности

- RCON-команды выполняются прямо в Telegram-топиках через безопасные алиасы: например, напишите `list` в топике "Тест".
- Один Telegram-топик соответствует одному Minecraft-режиму из `topics.yml`.
- Серверы и Telegram-команды загружаются из локального `servers.yml`.
- Привязка Telegram-топиков к серверам загружается из локального `topics.yml`.
- Доступные действия задаются в `command_aliases`: человек пишет `input`, а в RCON уходит только команда из `execute`.
- Служебные Telegram-команды настраиваются через локальный `bot_commands.yml`.
- Доступ ограничен одной беседой из `ALLOWED_CHAT_ID`.
- Выдача доступа к режимам управляется через `ADMIN_IDS`, `/grant`, `/revoke` и локальный `topic_access.yml`.
- `/chatid` по умолчанию доступен только суперадминам, чтобы не раскрывать ID чатов обычным пользователям.
- Есть cooldown, RCON timeout, DRY_RUN и техническое логирование без вывода токенов, RCON-паролей и приватных host:port.

## Структура

```text
rcon-telegram-bot/
  bot.py
  Dockerfile
  docker-compose.yml
  app/
    config/
      bot_commands.py
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
  bot_commands.yml.example
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
- `bot_commands.yml.example`
- `servers.yml.example`
- `topics.yml.example`
- `topic_access.yml.example`

Реальные локальные файлы не коммитятся:

- `.env`
- `.env.*`
- `*.env`
- `bot_commands.yml`
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
2. Укажите свой Telegram user_id в `ADMIN_IDS`. Команда `/chatid` доступна только суперадминам.
3. Временно укажите любой числовой `ALLOWED_CHAT_ID` в `.env`, например:

```env
ALLOWED_CHAT_ID=0
```

4. Запустите бота.
5. В нужной беседе отправьте:

```text
/chatid
```

Бот ответит:

```text
Chat ID этой беседы: -1001234567890
```

6. Скопируйте это число в локальный `.env`.

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

## 5. Как заполнить bot_commands.yml

`bot_commands.yml` управляет служебными Telegram-командами бота: включены ли они, кому доступны и как отображаются в `/help`.

Файл необязателен. Если `bot_commands.yml` отсутствует, бот использует безопасные дефолты:

- `/start`, `/help`, `/servers`, `/status`, `/players`, `/access` — `access: admin`.
- `/ping`, `/chatid`, `/grant`, `/revoke` — `access: superadmin`.

Создайте локальный файл, если хотите изменить описание, доступ или отключить отдельные команды:

```bash
cp bot_commands.yml.example bot_commands.yml
```

Пример:

```yaml
bot_commands:
  start:
    enabled: true
    access: admin
    description: "Информация о боте"

  help:
    enabled: true
    access: admin
    description: "Показывает помощь"

  servers:
    enabled: true
    access: admin
    description: "Список доступных серверов"

  status:
    enabled: true
    access: admin
    description: "Проверить доступность RCON-серверов"

  players:
    enabled: true
    access: admin
    description: "Онлайн игроков на доступных серверах"

  ping:
    enabled: true
    access: superadmin
    description: "Проверить работу бота"

  chatid:
    enabled: true
    access: superadmin
    description: "Показать ID текущей беседы"

  grant:
    enabled: true
    access: superadmin
    description: "Выдать доступ к режиму"

  revoke:
    enabled: true
    access: superadmin
    description: "Отозвать доступ к режиму"

  access:
    enabled: true
    access: admin
    description: "Показать выданные доступы"
```

Поля команды:

- `enabled` — включает или отключает команду. По умолчанию `true`.
- `access` — `admin` для пользователей с любым доступом к режиму и суперадминов, `superadmin` только для `ADMIN_IDS`. По умолчанию используется дефолт конкретной команды.
- `description` — текст для `/help`. По умолчанию пустая строка.

Неизвестные ключи команд считаются ошибкой конфигурации, чтобы опечатки не проходили молча. Если команда отсутствует в файле, для неё используется дефолт. `/ping`, `/chatid`, `/grant` и `/revoke` не могут иметь доступ ниже `superadmin`.

В `/help` бот показывает только включённые служебные команды, доступные конкретному пользователю. Пользователь без доступа к боту не видит help вообще.

## 6. Как заполнить servers.yml

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
    hidden: false

  polit:
    display_name: "Полит"
    host: "127.0.0.1"
    port: 25577
    password: "CHANGE_ME"
    telegram_command: "polit"
    hidden: false

  hidden_proxy:
    display_name: "Hidden Proxy"
    host: "127.0.0.1"
    port: 25578
    password: "CHANGE_ME"
    telegram_command: "hidden_proxy"
    hidden: true

command_aliases:
  ban:
    input: "ban"
    execute: "ban {args}"
    show_response: true
    enabled: true
    access: "admin"
    description: "Забанить игрока"

  mute:
    input: "mute"
    execute: "tempmute {args}"
    show_response: true
    enabled: true
    access: "admin"
    description: "Выдать временный мут"

  list:
    input: "list"
    execute: "list"
    show_response: true
    enabled: true
    access: "admin"
    description: "Список игроков на сервере"

  say:
    input: "say"
    execute: "say {args}"
    show_response: false
    enabled: true
    access: "admin"
    description: "Отправить сообщение в чат сервера"

  sync:
    input: "sync"
    execute: "say Sync {args}"
    show_response: false
    success_message: "✅ Sync выполнен."
    enabled: true
    access: "admin"
    target_server: "hidden_proxy"
    description: "Выполнить sync на скрытом сервере"

  clearmoder:
    input: "clearmoder"
    execute:
      - "lp user {args} parent remove moderator"
      - "lp user {args} permission clear"
    show_response: false
    success_message: "✅ Права модератора сняты."
    enabled: false
    access: "superadmin"
    description: "Снять права модератора"

  srestart:
    input: "srestart"
    execute: "uar now 300"
    show_response: false
    success_message: "✅ Рестарт сервера запущен."
    enabled: true
    access: "superadmin"
    description: "Запустить рестарт сервера"
```

`command_aliases` — это безопасная карта команд. Пользователь пишет `input` в Telegram, бот берёт всё после `input` как `{args}` и отправляет в RCON только команду, собранную из `execute`.

У сервера можно указать `hidden: true`. Такой сервер остаётся доступным для RCON и `target_server`, но не показывается в `/help`, `/servers`, `/status`, `/players` и списке доступных режимов. Поле необязательное, по умолчанию `hidden: false`; значение должно быть `true` или `false`.

Поля алиаса:

- `input` — что пишет человек в Telegram. Значение приводится к lowercase, не должно начинаться с `/` и не должно содержать пробелы.
- `execute` — RCON-шаблон из конфига. Если в нём есть `{args}`, туда подставляется текст после `input`. Шаблон не должен состоять только из `{args}`.
- `execute` может быть строкой или списком строк. Если указан список, бот выполнит команды по порядку.
- `show_response` — показывать ли реальный ответ RCON-сервера. По умолчанию `true`.
- `success_message` — необязательный текст успешного выполнения для `show_response: false`. Если он пустой или не указан, бот отправит стандартное `✅ Команда выполнена на <server.display_name>.`
- `enabled` — включает или отключает алиас. По умолчанию `true`. Отключённые алиасы не видны в `/help` и не выполняются.
- `access` — `admin` для пользователей с доступом к режиму и суперадминов, `superadmin` только для `ADMIN_IDS`. По умолчанию `admin`.
- `target_server` — необязательный ключ сервера из `servers.yml`. Если указан, алиас всегда выполняется на этом сервере, даже когда команда вызвана из другого топика или через `/test <alias>`. Доступ всё равно проверяется по текущему топику или выбранной серверной команде.
- `description` — текст для `/help`. Если пустой, в `/help` показывается только `input`.

В `/help` бот показывает только `input` и `description`, без RCON-шаблонов:

```text
Серверные команды:
• ban — Забанить игрока
• list — Список игроков на сервере
```

Обычный пользователь с доступом к режиму видит только включённые алиасы `access: admin`. Суперадмин видит включённые алиасы `access: admin` и `access: superadmin`.

Примеры сборки:

- Пользователь пишет `ban Gendalf2475 7d Читы`, `execute: "ban {args}"` превращается в `ban Gendalf2475 7d Читы`.
- Пользователь пишет `srestart test test`, `execute: "uar now 300"` не содержит `{args}`, поэтому в RCON уходит только `uar now 300`.
- Пользователь пишет `sync Gendalf2475` в доступном ему топике, а алиас с `target_server: "hidden_proxy"` выполняет команду на сервере `hidden_proxy`.

Держите набор алиасов минимальным. Бот не отправляет пользовательский текст в RCON напрямую: команда всегда собирается из `execute`.

## 7. Как заполнить topics.yml

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

## 8. Доступы к режимам

Суперадмины задаются в `.env` через `ADMIN_IDS`. Они имеют доступ ко всем режимам и могут управлять локальным файлом `topic_access.yml` командами:

```text
/grant <user_id> <topic_key>
/revoke <user_id> <topic_key>
/access [user_id]
```

Пользователь без прав получает отказ на служебные команды. Пользователь с доступом к одному режиму видит в `/help`, `/servers`, `/status` и `/players` только доступные ему режимы. По умолчанию `/ping`, `/chatid`, `/grant`, `/revoke` и просмотр чужих доступов через `/access <user_id>` доступны только суперадминам.

Пример локального файла:

```yaml
users:
  "123456789":
    topics:
      - "test"
      - "polit"
```

## 9. Как включить RCON на Paper-сервере

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

## 10. Установка зависимостей

Нужен Python 3.11+.

```bash
pip install -r requirements.txt
```

## 11. Запуск

Запускайте из папки проекта:

```bash
python bot.py
```

При старте бот проверит `.env`, `servers.yml`, `topics.yml`, список серверов, обязательные поля серверов, раздел `command_aliases` и `bot_commands.yml`, если он есть. Если конфигурация некорректна, бот напишет понятную ошибку в консоль и не запустится.

При запуске бот пишет безопасную диагностику конфига: путь к `servers.yml`, найденные верхние YAML-ключи, количество алиасов, путь к `topic_access.yml`, количество пользователей с выданными доступами, server key, display_name, замаскированный host, port, `password_set=true/false` и `hidden=true/false`. Пароли и Telegram token в логи не выводятся.

## 11.1. Docker/deploy

`servers.yml`, `topics.yml`, `topic_access.yml` и `bot_commands.yml` не хранятся в git и игнорируются как локальные файлы. Если Docker-образ собирается только из git-репозитория, реальные YAML-файлы в образ не попадут. Их нужно передать в контейнер отдельно: bind mount, volume или секретом деплоя. Если `bot_commands.yml` не передан, бот использует безопасные дефолты.

Перед первым запуском рядом с `docker-compose.yml` создайте runtime-файл доступов, если его ещё нет:

```bash
printf 'users: {}\n' > topic_access.yml
```

Пример bind mount:

```yaml
services:
  rcon_majure_bot:
    build: .
    container_name: rcon_majure_bot
    restart: unless-stopped
    network_mode: host
    env_file:
      - .env
    volumes:
      - ./servers.yml:/app/servers.yml:ro
      - ./topics.yml:/app/topics.yml:ro
      - ./bot_commands.yml:/app/bot_commands.yml:ro
      - ./topic_access.yml:/app/topic_access.yml
```

Строку с `bot_commands.yml` добавляйте только если создали локальный файл. Без него бот использует дефолтные настройки служебных команд.
`topic_access.yml` монтируется без `:ro`: это state-файл, и бот сохраняет в него `/grant` и `/revoke` сразу после изменения доступа.

Путь справа должен совпадать с `WORKDIR` контейнера. Если `WORKDIR` не `/app`, укажите путь к `servers.yml` рядом с `bot.py`.

Не копируйте `servers.yml.example` поверх реального `servers.yml` при сборке или запуске контейнера. В шаблоне стоят примерные `host`, `port` и `password`.

Если Minecraft-сервер запущен на хост-машине, `127.0.0.1` внутри контейнера указывает на сам контейнер, а не на хост. Используйте подходящий адрес хоста, `host.docker.internal` там, где он доступен, общую Docker-сеть или `network_mode: host`, если это осознанно подходит вашему окружению.

## 12. Примеры использования

```text
list
say Привет
ban Gendalf2475 7d Читы
srestart test test
/test list
/polit list
/polit ban Gendalf2475 7d Читы
/status
/players
/ping
```

Основной формат в топике:

```text
<alias_input> [аргументы]
```

Например, если сообщение отправлено в топике "Тест":

```text
list
```

бот отправит в RCON сервера `test` только:

```text
list
```

Формат через команду сервера:

```text
/<telegram_command> <alias_input> [аргументы]
```

Например, `/polit ban Gendalf2475 7d Читы` отправит в RCON сервера `polit` команду `ban Gendalf2475 7d Читы`, если такой алиас настроен. Если сервер привязан к топику, доступ к режиму всё равно проверяется.

## 13. Частые ошибки

- Неправильный RCON-пароль в локальном `servers.yml`.
- RCON выключен в `server.properties`.
- Порт RCON занят другим процессом.
- Firewall или правила хостинга блокируют порт.
- Алиас команды не добавлен в `command_aliases`.
- Алиас отключён через `enabled: false`.
- Для алиаса указан `access: superadmin`, а пользователя нет в `ADMIN_IDS`.
- В `target_server` указан ключ сервера, которого нет в `servers.yml`.
- Служебная команда отключена в `bot_commands.yml`.
- `ALLOWED_CHAT_ID` не настроен или указан неверно.
- `ADMIN_IDS` не содержит user_id суперадмина.
- Топик не добавлен в `topics.yml` или указан неверный `thread_id`.
- Пользователю не выдан доступ к режиму через `/grant`.
- Команда отправлена не из разрешённой беседы.
- Бот запущен не из той папки.
- У Paper-сервера и `servers.yml` не совпадают `rcon.port` или `rcon.password`.

## 14. Команды для BotFather /setcommands

Чтобы Telegram-меню не показывало служебные команды всем пользователям, в глобальный список лучше добавить только базовые команды:

```text
start - Информация о боте
help - Помощь
access - Показать доступы к режимам
```

Серверные команды и команды суперадмина можно вводить вручную. Сам бот всё равно проверяет права на каждую команду.

## Безопасность

- Не храните реальные секреты в репозитории.
- Не отправляйте RCON-пароли в Telegram.
- Не публикуйте `.env`, `bot_commands.yml`, `servers.yml`, `topics.yml` и `topic_access.yml`.
- Используйте `.env.example`, `bot_commands.yml.example`, `servers.yml.example`, `topics.yml.example` и `topic_access.yml.example` только как шаблоны.
- Бот не пишет Telegram token и RCON-пароли в логи.
- Дополнительные рекомендации находятся в `SECURITY.md`.
