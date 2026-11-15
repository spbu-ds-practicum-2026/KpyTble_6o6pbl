# Plotina — Room Service

Фундамент Room Service из технического решения проекта «Plotina».
Сервис является источником истины для комнат: участники, роли, очередь видео,
состояние воспроизведения, версионирование, идемпотентность команд и передача
роли ведущего.

Реализовано на Python 3.11+ (FastAPI + SQLAlchemy 2.0 + PostgreSQL), тесты
гоняются на SQLite.

---

## Что входит в фундамент

- **Комнаты и сессии**
  - создание комнаты с назначением ведущего;
  - подключение по коду приглашения;
  - выдача уникального токена сессии (в БД хранится только SHA-256 хеш);
  - проверка, что токен принадлежит нужной комнате;
  - явный выход из комнаты.
- **Участники и роли**
  - роли `host` / `member` назначаются только на сервере;
  - клиент не может прислать себе роль;
  - режимы управления `host_only` и `all`;
  - передача роли ведущего при явном выходе и при длительном отключении
    (grace-период, по умолчанию 10 секунд);
  - отмена передачи роли при переподключении.
- **Очередь видео**
  - добавление ссылки Rutube с серверной валидацией;
  - удаление и перемещение видео;
  - удаление текущего видео переключает комнату на следующее видео и ставит
    паузу; если следующего нет — воспроизведение сбрасывается.
- **Воспроизведение**
  - `play`, `pause`, `seek`, `next`;
  - сервер хранит позицию, состояние паузы и время фиксации;
  - позиция рассчитывается на сервере на момент запроса/ответа;
  - корректная поздняя синхронизация (клиент получает текущую позицию).
- **Согласованность и надёжность**
  - `stateVersion` увеличивается только при изменении состояния;
  - последовательная обработка команд внутри комнаты (asyncio-lock на комнату);
  - идемпотентность по `commandId`: результат команды и изменение состояния
    сохраняются одной транзакцией;
  - повтор с тем же `commandId` возвращает сохранённое подтверждение (флаг
    `duplicate: true` и снимок состояния на момент выполнения) без повторного
    действия; правило общее для всех типов команд, а не только для `next` и
    `add_video`;
  - тот же `commandId` с другими параметрами отклоняется (`409`);
  - завершение комнаты (`close_room`), после которого новые команды и
    подключения отклоняются.
- **Интеграционные границы**
  - внутренний endpoint проверки членства для Chat Service;
  - заглушка публикации асинхронных событий для API Gateway.

---

## Структура проекта

```
room-service/
├── app/
│   ├── api/                 # HTTP-роуты (public + internal)
│   ├── integrations/        # ЗАГЛУШКИ интеграций с другими сервисами
│   ├── services/            # доменная логика
│   ├── config.py
│   ├── database.py
│   ├── dependencies.py      # сессия БД, аутентификация по токену
│   ├── enums.py
│   ├── errors.py            # доменные ошибки -> HTTP
│   ├── models.py            # Room, Participant, Video, CommandRecord
│   ├── permissions.py
│   ├── repository.py
│   ├── runtime.py           # locks + зависимости времени выполнения
│   ├── schemas.py
│   ├── security.py
│   ├── snapshot.py          # расчёт позиции и сборка полного состояния
│   ├── timeutils.py
│   └── main.py
├── tests/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── requirements-dev.txt
└── pyproject.toml
```

### Модель данных

- `Room` — комната, режим управления, `state_version`, текущее видео, позиция,
  пауза, время фиксации позиции, статус.
- `Participant` — участник, роль, хеш токена, признак подключения, поколение
  отключения (`connection_generation`), время входа, время выхода.
- `Video` — элемент очереди (ссылка Rutube, порядок, автор).
- `CommandRecord` — результат обработки команды для идемпотентности.

`command_id` имеет уникальное ограничение. Запись `CommandRecord` и изменение
состояния комнаты фиксируются одной транзакцией.

---

**Пошаговое руководство: от запуска до управления комнатой.**

## 1. Что такое Docker и зачем он нужен

Docker — платформа контейнеризации. Она упаковывает приложение и зависимости в
изолированный контейнер, который одинаково работает на разных компьютерах.

- **Образ (image)** — шаблон с окружением и кодом.
- **Контейнер** — запущенный экземпляр образа.
- **Dockerfile** — инструкция сборки образа (`Dockerfile`).
- **Docker Compose** — описание нескольких контейнеров (`docker-compose.yml`).
- **Volume** — постоянное хранилище данных (в проекте — `room_pgdata`).

В проекте Docker нужен, чтобы не устанавливать PostgreSQL вручную и одной
командой поднимать базу и Room Service. Docker не обязателен: сервис может
работать локально на SQLite.

## 2. Установка Docker в Windows

Скачать: https://www.docker.com/products/docker-desktop/

Требования:

- Windows 10/11 64-bit;
- права администратора;
- включённая виртуализация в BIOS/UEFI (Диспетчер задач → Производительность →
  ЦП → «Виртуализация: Включено»);
- WSL2. Если его нет, в PowerShell от администратора:

```powershell
wsl --install
```

Затем перезагрузите компьютер.

Установка:

1. Запустите `Docker Desktop Installer.exe`.
2. Оставьте включённым **Use WSL 2 instead of Hyper-V**.
3. Перезагрузите систему.
4. Запустите Docker Desktop и дождитесь статуса **Engine running**.

Проверка в **новом** терминале:

```powershell
docker --version
docker compose version
docker run hello-world
```

Если команда `docker` не распознаётся:

- убедитесь, что Docker Desktop запущен;
- закройте и снова откройте PowerShell;
- проверьте, что в `PATH` есть `C:\Program Files\Docker\Docker\resources\bin`;
- перезагрузите компьютер.

## 3. Запуск Room Service

Все команды выполняются из папки проекта:

```powershell
cd C:\_IT\code\orv\room-service
```

### Вариант A. Docker Compose: PostgreSQL + сервис

```powershell
docker compose up --build
```

- сервис: http://localhost:8000
- Swagger: http://localhost:8000/docs
- PostgreSQL: `localhost:5432`

Остановка: `Ctrl+C`. Затем при необходимости:

```powershell
docker compose down
```

`docker compose down` останавливает контейнеры, но не удаляет базу: данные
хранятся в volume `room_pgdata`. Команда `docker compose down -v` удалит и
контейнеры, и данные PostgreSQL. После изменения кода в `app/` образ нужно
пересобрать: `docker compose up --build`.

Запуск в фоне и логи:

```powershell
docker compose up --build -d
docker compose logs -f room-service
```

Только база для локальной разработки:

```powershell
docker compose up -d db
```

### Вариант B. Windows без Docker, на SQLite

Существующий `.venv` создан в WSL и для Windows не подходит, поэтому создайте
отдельное окружение `.venv-win`:

```powershell
cd C:\_IT\code\orv\room-service

py -m venv .venv-win
.\.venv-win\Scripts\python.exe -m pip install --upgrade pip
.\.venv-win\Scripts\python.exe -m pip install -r requirements-dev.txt

$env:ROOM_DATABASE_URL="sqlite+aiosqlite:///./room.db"
$env:ROOM_AUTO_CREATE_TABLES="true"
.\.venv-win\Scripts\python.exe -m uvicorn app.main:app --reload
```

Если `asyncpg` не устанавливается, для SQLite он не нужен:

```powershell
.\.venv-win\Scripts\python.exe -m pip install fastapi "uvicorn[standard]" "sqlalchemy[asyncio]" pydantic pydantic-settings aiosqlite
```

### Вариант C. Linux / macOS / WSL

```bash
cd room-service
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Быстрый запуск без PostgreSQL:

```bash
ROOM_DATABASE_URL="sqlite+aiosqlite:///./room.db" \
ROOM_AUTO_CREATE_TABLES=true \
uvicorn app.main:app --reload
```

### Вариант D. Локально с PostgreSQL из Docker

```bash
docker compose up -d db
cp .env.example .env
uvicorn app.main:app --reload
```

### Проверка запуска

```powershell
curl.exe http://localhost:8000/health
# {"status":"ok"}
```

## 4. Открыть Swagger

Откройте **http://localhost:8000/docs**.

Именно `/docs` — интерактивный Swagger с кнопками **Try it out** и
**Authorize**. `/redoc` — только документация без интерактивных запросов.

## 5. Создать комнату

### Через Swagger

1. Найдите `POST /rooms` → **Try it out**.
2. Тело запроса:

```json
{
  "display_name": "Alice",
  "control_mode": "host_only"
}
```

3. Нажмите **Execute**.

### Через PowerShell

```powershell
$base = "http://localhost:8000"

$body = @{
  display_name = "Alice"
  control_mode = "host_only"
} | ConvertTo-Json

$room = Invoke-RestMethod -Method Post -Uri "$base/rooms" `
  -ContentType "application/json" `
  -Body $body

$room | ConvertTo-Json -Depth 10
```

## 6. Как понять, что комната создалась

Успешный ответ — **HTTP 201 Created**. В теле будут поля (пример сокращён):

```json
{
  "room_id": "637c191e-49bf-453f-a335-5dc47b2ca6f8",
  "invite_code": "AbCdEf_12345",
  "invite_link": "http://localhost:3000/rooms/AbCdEf_12345",
  "token": "xQ7vJ2mK9pL4sT8nR1wY6zA3bC5dE0fG",
  "participant": {
    "display_name": "Alice",
    "role": "host",
    "connected": true
  },
  "state": {
    "status": "active",
    "control_mode": "host_only",
    "state_version": 1,
    "current_video_id": null,
    "playback": {
      "video_id": null,
      "position_seconds": 0,
      "is_playing": false
    },
    "queue": [],
    "participants": [
      {
        "display_name": "Alice",
        "role": "host",
        "connected": true
      }
    ]
  }
}
```

Признаки успеха:

- `room_id` и `invite_code` заполнены;
- `participant.role == "host"` — вы ведущий;
- `state.status == "active"`;
- `state.state_version == 1`;
- `state.queue` пустой;
- в `state.participants` один участник.

Также запрос виден в логах:

```powershell
docker compose logs -f room-service
```

Там будет строка вида `POST /rooms HTTP/1.1" 201`.

## 7. Что такое token и где его взять

`token` — секретная строка сессии, которую сервер выдаёт один раз при создании
комнаты или подключении к ней. По ней сервер определяет пользователя, комнату
и роль.

Это **не** `room_id` и **не** `invite_code`:

- `room_id` — UUID комнаты;
- `invite_code` — код для подключения других участников;
- `token` — личный пропуск участника.

Где взять: в ответе `POST /rooms` или `POST /rooms/join`, поле `"token"`.
В БД хранится только SHA-256 хеш, поэтому позже токен посмотреть нельзя.

Если токен потерян:

- создайте новую комнату через `POST /rooms`;
- или подключитесь к той же комнате через `POST /rooms/join` — это будет новый
  участник с новым токеном;
- восстановить старый токен невозможно.

## 8. Авторизация в Swagger

Кнопка **Authorize** находится справа сверху на странице `/docs`, обычно с
иконкой замка.

1. Нажмите **Authorize**.
2. Вставьте `token` — только строку, без слова `Bearer` и без кавычек.
3. Нажмите **Authorize**, затем **Close**.
4. У защищённых методов появятся иконки замка.

Если кнопки нет:

- убедитесь, что образ пересобран после добавления авторизации:
  `docker compose up --build`;
- обновите страницу с очисткой кэша: `Ctrl+F5`;
- проверьте, что в OpenAPI есть схема:

```powershell
(Invoke-RestMethod http://localhost:8000/openapi.json).components.securitySchemes
```

Должен быть `HTTPBearer`.

Без Swagger токен передаётся в заголовке:

```
Authorization: Bearer <token>
```

Также поддерживается `X-Session-Token: <token>`.

## 9. Подключить участника

Передайте `invite_code` другому человеку. Он выполняет:

`POST /rooms/join`

```json
{
  "invite_code": "AbCdEf_12345",
  "display_name": "Bob"
}
```

PowerShell:

```powershell
$body = @{
  invite_code = $room.invite_code
  display_name = "Bob"
} | ConvertTo-Json

$member = Invoke-RestMethod -Method Post -Uri "$base/rooms/join" `
  -ContentType "application/json" `
  -Body $body

$member.token
```

Ответ содержит его собственный `token` и полное состояние комнаты. `invite_link`
пока ведёт на несуществующий веб-клиент, поэтому для теста используйте
`invite_code`.

## 10. Что можно делать в комнате

### 10.1 Добавить видео

`POST /rooms/{room_id}/commands`

```json
{
  "command_id": "add-1",
  "type": "add_video",
  "payload": {
    "url": "https://rutube.ru/video/abc123/",
    "title": "Demo"
  }
}
```

Поддерживаются публичные, private и embed-ссылки Rutube. После добавления видео
становится текущим, но стоит на паузе. `current_video_id` появится в состоянии.

### 10.2 Управление воспроизведением

```json
{ "command_id": "play-1",  "type": "play",  "payload": {} }
{ "command_id": "pause-1", "type": "pause", "payload": {} }
{ "command_id": "seek-1",  "type": "seek",  "payload": { "position_seconds": 30 } }
{ "command_id": "next-1",  "type": "next",  "payload": {} }
```

`command_id` должен быть новым для каждого нового действия. Повтор с тем же ID —
это retry: сервер вернёт сохранённое подтверждение без повторного действия.

### 10.3 Управление очередью

Сначала посмотрите очередь и возьмите `id` видео:

`GET /rooms/{room_id}`

Переместить:

```json
{
  "command_id": "move-1",
  "type": "move_video",
  "payload": { "video_id": "<id из queue>", "position": 0 }
}
```

Удалить:

```json
{
  "command_id": "remove-1",
  "type": "remove_video",
  "payload": { "video_id": "<id из queue>" }
}
```

При удалении текущего видео комната переключается на следующее и ставит паузу.
Если следующего нет — текущее видео сбрасывается, воспроизведение
останавливается.

### 10.4 Режимы управления

```json
{
  "command_id": "mode-1",
  "type": "set_control_mode",
  "payload": { "mode": "all" }
}
```

- `host_only` — управляет только ведущий;
- `all` — управляют все участники.

Сменить режим и закрыть комнату может только ведущий.

### 10.5 Смотреть состояние

`GET /rooms/{room_id}` возвращает:

- участников, роли и `connected`;
- очередь видео;
- текущее видео;
- позицию и `is_playing`;
- `state_version`;
- статус комнаты.

Успешная команда обычно означает: `duplicate: false`, `state_version`
увеличился, нужное поле в `state` изменилось.

### 10.6 Закрыть комнату

Только ведущий, команда `close_room`:

```json
{
  "command_id": "close-1",
  "type": "close_room",
  "payload": {}
}
```

PowerShell:

```powershell
$cmd = @{
  command_id = [guid]::NewGuid().ToString()
  type = "close_room"
  payload = @{}
} | ConvertTo-Json -Depth 5

$closed = Invoke-RestMethod -Method Post `
  -Uri "$base/rooms/$($room.room_id)/commands" `
  -Headers @{ Authorization = "Bearer $($room.token)" } `
  -ContentType "application/json" `
  -Body $cmd

$closed.state.status   # closed
```

После закрытия:

- новые команды отклоняются с `409 room_closed`;
- новые участники через `/rooms/join` не подключаются (`409`);
- `GET /rooms/{room_id}` участникам всё ещё доступен;
- повтор `close_room` с тем же `command_id` вернёт `duplicate: true`.

`close_room` — это завершение комнаты в БД. Это не `docker compose down`:
остановка контейнера не закрывает комнату, состояние сохраняется в PostgreSQL.

### 10.7 Выйти из комнаты

`POST /rooms/{room_id}/leave`

Выход — это не закрытие комнаты. Участник помечается вышедшим. Если выходит
ведущий, роль сразу передаётся самому раннему подключённому участнику. Если
участников не осталось, комната остаётся активной, но без ведущего.

## 11. Полный пример на PowerShell

```powershell
$base = "http://localhost:8000"

# 1. Создать комнату
$body = @{ display_name = "Alice"; control_mode = "host_only" } |
  ConvertTo-Json
$room = Invoke-RestMethod -Method Post -Uri "$base/rooms" `
  -ContentType "application/json" -Body $body

$roomId = $room.room_id
$token = $room.token
$headers = @{ Authorization = "Bearer $token" }

# 2. Подключить Bob
$body = @{ invite_code = $room.invite_code; display_name = "Bob" } |
  ConvertTo-Json
$member = Invoke-RestMethod -Method Post -Uri "$base/rooms/join" `
  -ContentType "application/json" -Body $body

# 3. Добавить видео
$cmd = @{
  command_id = [guid]::NewGuid().ToString()
  type = "add_video"
  payload = @{
    url = "https://rutube.ru/video/abc123/"
    title = "Demo"
  }
} | ConvertTo-Json -Depth 5
Invoke-RestMethod -Method Post -Uri "$base/rooms/$roomId/commands" `
  -Headers $headers -ContentType "application/json" -Body $cmd

# 4. Запустить видео
$cmd = @{
  command_id = [guid]::NewGuid().ToString()
  type = "play"
  payload = @{}
} | ConvertTo-Json -Depth 5
$played = Invoke-RestMethod -Method Post -Uri "$base/rooms/$roomId/commands" `
  -Headers $headers -ContentType "application/json" -Body $cmd

# 5. Посмотреть состояние
Invoke-RestMethod -Uri "$base/rooms/$roomId" -Headers $headers |
  ConvertTo-Json -Depth 10

# 6. Закрыть комнату
$cmd = @{
  command_id = [guid]::NewGuid().ToString()
  type = "close_room"
  payload = @{}
} | ConvertTo-Json -Depth 5
Invoke-RestMethod -Method Post -Uri "$base/rooms/$roomId/commands" `
  -Headers $headers -ContentType "application/json" -Body $cmd
```

В PowerShell используйте `curl.exe`, а не `curl`: `curl` является алиасом
`Invoke-WebRequest` и не понимает флаги `-X`, `-H`, `-d`.

## 12. Типичные ошибки

- `401` — нет токена или он неверный.
- `403 wrong_room` — токен от другой комнаты.
- `403 host_only_mode` — участник пытается управлять в режиме «только ведущий».
- `403 host_only_command` — не ведущий пытается сменить режим или закрыть
  комнату.
- `409 no_current_video` — `play`/`seek` без выбранного видео.
- `409 room_closed` — комната уже закрыта.
- `409 command_id_conflict` — тот же `commandId` использован с другими
  параметрами.
- `422 invalid_video_url` — ссылка не Rutube.
- `422 invalid_payload` — неверные параметры команды.

## 13. Проверка открытых комнат и обслуживание через БД

Публичного API «показать все комнаты» нет — это сделано намеренно, чтобы нельзя
было перебирать чужие комнаты. Через API комнату можно получить только по
`room_id` и с токеном участника.

Посмотреть комнаты можно напрямую в PostgreSQL:

```powershell
docker compose exec db psql -U room -d roomdb -P pager=off `
  -c "SELECT id, invite_code, status, control_mode, state_version, created_at FROM rooms ORDER BY created_at DESC;"
```

Только открытые:

```powershell
docker compose exec db psql -U room -d roomdb -P pager=off `
  -c "SELECT id, invite_code, created_at FROM rooms WHERE status = 'active' ORDER BY created_at DESC;"
```

Количество открытых:

```powershell
docker compose exec db psql -U room -d roomdb -P pager=off `
  -c "SELECT count(*) FROM rooms WHERE status = 'active';"
```

Найти ведущего комнаты:

```powershell
docker compose exec db psql -U room -d roomdb -P pager=off `
  -c "SELECT id, display_name, role, connected FROM participants WHERE room_id = 'ВАШ_ROOM_ID' AND left_at IS NULL ORDER BY joined_at;"
```

Токен ведущего там не виден — в БД хранится только хеш, восстановить его нельзя.

### Закрыть комнату без токена ведущего

Для отладки можно закрыть комнату напрямую SQL-запросом:

```powershell
docker compose exec db psql -U room -d roomdb -P pager=off `
  -c "UPDATE rooms SET status='closed', is_playing=false, closed_at=now(), state_version=state_version+1 WHERE id='ВАШ_ROOM_ID' AND status='active';"
```

Закрыть все открытые комнаты:

```powershell
docker compose exec db psql -U room -d roomdb -P pager=off `
  -c "UPDATE rooms SET status='closed', is_playing=false, closed_at=now(), state_version=state_version+1 WHERE status='active';"
```

Полностью удалить комнату (участники, видео и записи команд удалятся
каскадно):

```powershell
docker compose exec db psql -U room -d roomdb -P pager=off `
  -c "DELETE FROM rooms WHERE id='ВАШ_ROOM_ID';"
```

После SQL-изменения сервис сразу увидит новое состояние: он читает комнату из
БД при каждом запросе.

### Как выйти из psql / просмотра вывода

- Если внизу `(END)` или `:` — это pager, нажмите **`q`**.
- Если приглашение вида `roomdb=#` — введите **`\q`** и Enter.
- Если вы в shell внутри контейнера (`root@...:/#`) — введите **`exit`**.
- Также работает `Ctrl+D`.

Чтобы отключить pager на будущее, используйте `-P pager=off` или внутри psql:

```sql
\pset pager off
```

## 14. Тесты

```bash
pytest -q
```

Windows:

```powershell
.\.venv-win\Scripts\python.exe -m pytest -q
```

Тесты используют SQLite, отдельную БД на каждый тест, и проверяют:
создание/подключение, права, очередь, воспроизведение, идемпотентность,
передачу ведущего, grace-период и членство для чата.

---

## API

Токен передаётся в `Authorization: Bearer <token>` или `X-Session-Token`.

| Метод | Путь | Назначение |
| --- | --- | --- |
| `POST` | `/rooms` | Создать комнату, получить токен ведущего |
| `POST` | `/rooms/join` | Подключиться по `invite_code` |
| `GET` | `/rooms/{room_id}` | Полное состояние комнаты |
| `POST` | `/rooms/{room_id}/commands` | Выполнить команду |
| `POST` | `/rooms/{room_id}/connect` | Отметить WebSocket-соединение открытым |
| `POST` | `/rooms/{room_id}/disconnect` | Отметить соединение потерянным |
| `POST` | `/rooms/{room_id}/leave` | Явный выход из комнаты |
| `GET` | `/internal/rooms/{room_id}/membership` | Проверка членства для Chat Service |
| `GET` | `/health` | Проверка живости |

### Команды

Тело команды:

```json
{
  "command_id": "уникальный-идентификатор",
  "type": "play",
  "payload": {}
}
```

| `type` | `payload` | Кто может |
| --- | --- | --- |
| `play` | `{}` | по режиму комнаты |
| `pause` | `{}` | по режиму комнаты |
| `seek` | `{"position_seconds": 42}` | по режиму комнаты |
| `next` | `{}` | по режиму комнаты |
| `add_video` | `{"url": "https://rutube.ru/video/...", "title": "..."}` | по режиму комнаты |
| `remove_video` | `{"video_id": "uuid"}` | по режиму комнаты |
| `move_video` | `{"video_id": "uuid", "position": 0}` | по режиму комнаты |
| `set_control_mode` | `{"mode": "host_only" \| "all"}` | только ведущий |
| `close_room` | `{}` | только ведущий |

«По режиму комнаты»: в `host_only` — только ведущий, в `all` — все участники.

Ответ команды:

```json
{
  "command_id": "...",
  "duplicate": false,
  "state": { "...полное состояние комнаты..." }
}
```

При повторе `duplicate` будет `true`, а `state` — сохранённый результат.

### Пример через curl

```bash
# создать комнату
curl -X POST http://localhost:8000/rooms \
  -H 'Content-Type: application/json' \
  -d '{"display_name":"Alice","control_mode":"host_only"}'

# добавить видео
curl -X POST http://localhost:8000/rooms/<room_id>/commands \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '{"command_id":"cmd-1","type":"add_video","payload":{"url":"https://rutube.ru/video/abc123/"}}'

# запустить
curl -X POST http://localhost:8000/rooms/<room_id>/commands \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '{"command_id":"cmd-2","type":"play","payload":{}}'
```

---

## Что намеренно является заглушкой

Эти места не относятся к домену Room Service и легко удаляются/заменяются,
когда появятся другие сервисы.

1. **Публикация событий для API Gateway** —
   `app/integrations/events.py`.
   Room Service не рассылает данные клиентам: синхронные ответы содержат полное
   состояние, и Gateway рассылает его. Единственное асинхронное событие —
   `host_changed` после grace-периода. Сейчас оно только логируется
   (`LoggingEventPublisher`) или игнорируется (`NullEventPublisher`).
   Точка замены: реализовать `EventPublisher.publish` через HTTP к Gateway или
   через брокер сообщений. В доменном коде вызов один — в
   `app/services/handover.py`.
2. **Проверка членства для Chat Service** —
   `GET /internal/rooms/{room_id}/membership` (`app/api/internal.py`).
   Это не заглушка по смыслу: Room Service владеет истиной о членстве. Но сам
   Chat Service ещё не существует, поэтому endpoint пока никем не вызывается.
   Когда Chat Service появится, он будет обращаться сюда. Endpoint можно
   закрыть отдельным сервисным токеном/сетевой политикой.
3. **API Gateway** — отсутствует. Контракт сейчас такой: Gateway вызывает REST
   Room Service и рассылает полученное `state` участникам. WebSocket,
   heartbeat и переподключения — зона Gateway, а не Room Service. Для их
   поддержки Room Service предоставляет `/connect`, `/disconnect` и `/leave`.
4. **Rutube** — сервис только валидирует ссылку. Видео воспроизводит браузер
   через embed-плеер; метаданные (название/длительность) не запрашиваются.
5. **Веб-клиент** — отсутствует. В Swagger можно управлять состоянием комнаты,
   но видео там не проигрывается. Реальный плеер, чат и список участников
   появятся в веб-клиенте.

---

## Принятые решения и ограничения прототипа

- **Один экземпляр сервиса.** Порядок команд обеспечивается `asyncio.Lock` на
  комнату, таймеры передач роли живут в памяти. Для нескольких экземпляров
  нужна распределённая блокировка/очередь и внешний планировщик.
- **Таймеры передач роли не переживают перезапуск.** После рестарта уже
  отключённый ведущий не будет автоматически заменён до следующего
  disconnect-события. Для прототипа это допустимо; при необходимости добавляется
  восстановление при старте.
- **`auto_create_tables=true`** создаёт таблицы при запуске. Для production
  нужны миграции (Alembic).
- **Нет сервисной аутентификации между сервисами.** `/internal/*` рассчитан на
  доверенную внутреннюю сеть.
- **Пустая комната после ухода последнего участника** остаётся без ведущего:
  передавать роль некому. Если позже кто-то подключится, он станет обычным
  участником — в ТР это не описано.
- **Длительность видео неизвестна**, поэтому позиция не ограничивается сверху.
  Клиент сам ограничивает её длительностью ролика.
- **История чата и сообщения** — вне Room Service (Chat Service).

---

## Возможные следующие шаги

1. Alembic-миграции вместо `create_all`.
2. Публикация событий в Gateway/брокер через `EventPublisher`.
3. Восстановление grace-таймеров при старте сервиса.
4. Распределённая сериализация команд для нескольких экземпляров.
5. Метрики и структурированные логи.
6. Контрактные тесты с API Gateway и Chat Service.
7. Админский endpoint для просмотра и закрытия комнат без токена ведущего.
