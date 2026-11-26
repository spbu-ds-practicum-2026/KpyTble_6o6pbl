# Plotina — Room Service

Room Service — источник истины для комнат: участники, роли, очередь видео,
состояние воспроизведения, версии состояния, идемпотентность команд и передачи
роли ведущего.

Реализация: Python 3.11+, FastAPI, SQLAlchemy 2.0, PostgreSQL. Тесты используют
SQLite. Полный формат обмена описан в [api-contract.md](api-contract.md).

---

## Запуск

### Вариант A — Docker Compose

Да, команда `docker compose up --build` осталась рабочей. Запускайте её из каталога
`services/room-service`:

```powershell
cd C:\_IT\code\KpyTble_6o6pbl\services\room-service
docker compose up --build
```

Compose поднимает два контейнера:

- `db` — PostgreSQL 16, данные в volume `room_pgdata`;
- `room-service` — сам сервис на порту `8000`.

В `docker-compose.yml` уже выставлены:

```text
ROOM_DATABASE_URL=postgresql+asyncpg://room:room@db:5432/roomdb
ROOM_EVENT_PUBLISHER=logging
ROOM_AUTO_CREATE_TABLES=true
```

Адреса:

- API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- Проверка живости: `http://localhost:8000/health`

Полезные команды:

```powershell
docker compose logs -f room-service   # логи сервиса
docker compose down                   # остановить, данные БД сохранить
docker compose down -v                # остановить и удалить данные PostgreSQL
```

### Вариант B — локально на SQLite (PowerShell)

```powershell
cd C:\_IT\code\KpyTble_6o6pbl\services\room-service
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt

$env:ROOM_DATABASE_URL="sqlite+aiosqlite:///./room.db"
$env:ROOM_AUTO_CREATE_TABLES="true"
$env:ROOM_EVENT_PUBLISHER="logging"

python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Если активация venv блокируется политикой выполнения:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Для Linux/macOS те же переменные задаются иначе:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
ROOM_DATABASE_URL="sqlite+aiosqlite:///./room.db" \
ROOM_AUTO_CREATE_TABLES=true \
ROOM_EVENT_PUBLISHER=logging \
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Остановка сервера — `Ctrl+C` в терминале, где запущен `uvicorn`.

Проверка, что сервис поднялся:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Ожидаемый ответ: `{"status":"ok"}`.

Данные SQLite хранятся в `room.db`. Если нужно начать с пустой базы, остановите
сервер и удалите `room.db`, затем запустите его снова: таблицы создадутся заново
благодаря `ROOM_AUTO_CREATE_TABLES=true`.

---

## Быстрый сценарий: создать комнату, добавить участника, получить состояние

В примерах используется `Invoke-RestMethod` — он не требует экранирования кавычек
в JSON, в отличие от `curl.exe` в Windows PowerShell.

### 1. Создать комнату

```powershell
$base = "http://127.0.0.1:8000"

$createBody = @{
    display_name = "Alice"
    control_mode = "host_only"
} | ConvertTo-Json -Compress

$room = Invoke-RestMethod -Uri "$base/rooms" -Method Post `
    -ContentType "application/json" -Body $createBody

$room.room_id
$room.invite_code
$room.token
```

Ответ `201` содержит:

```json
{
  "room_id": "637c191e-49bf-453f-a335-5dc47b2ca6f8",
  "invite_code": "AbCdEf_12345",
  "invite_link": "http://localhost:3000/rooms/AbCdEf_12345",
  "token": "alice-token",
  "participant": {"display_name": "Alice", "role": "host", "connected": true},
  "state": { "...": "полный снимок состояния" }
}
```

`invite_code` используется для подключения других участников; `invite_link`
возвращается для info, но `POST /rooms/join` принимает только `invite_code`.
`token` — токен ведущего.

### 2. Добавить участника

Отдельного эндпоинта «add participant» нет: участник добавляется запросом
`POST /rooms/join` по коду приглашения.

```powershell
$joinBody = @{
    invite_code = $room.invite_code
    display_name = "Bob"
} | ConvertTo-Json -Compress

$bob = Invoke-RestMethod -Uri "$base/rooms/join" -Method Post `
    -ContentType "application/json" -Body $joinBody

$bob.token
$bob.state.participants
```

Ответ `201` содержит `room_id`, `invite_code`, `invite_link`, новый `token`,
`participant` и полный `state`. Роль назначает сервер.

Важно: каждый успешный `POST /rooms/join` создаёт **новую сессию**. Если вызвать
запрос три раза с `display_name = "Bob"`, в комнате будет три участника с таким
именем и три разных токена. Для тестов используйте уникальные имена
(`Bob-1`, `Bob-2`) или создавайте новую комнату.

### 3. Проверить, что возвращает сервис для состояния комнаты

Запрос:

```powershell
$state = Invoke-RestMethod -Uri "$base/rooms/$($room.room_id)" `
    -Headers @{ Authorization = "Bearer $($room.token)" }

$state | ConvertTo-Json -Depth 8
```

`GET /rooms/{room_id}` возвращает **сам объект состояния**, а не обёртку вида
`{"state": ...}`. Код ответа — `200`.

Пример ответа:

```json
{
  "status": "active",
  "control_mode": "host_only",
  "state_version": 2,
  "current_video_id": null,
  "playback": {
    "video_id": null,
    "position_seconds": 0.0,
    "is_playing": false
  },
  "queue": [],
  "participants": [
    {"display_name": "Alice", "role": "host", "connected": true},
    {"display_name": "Bob", "role": "member", "connected": true}
  ]
}
```

Можно использовать токен ведущего или активного участника этой же комнаты. Для
неверного или вышедшего токена будет `401 unauthorized`, для чужой комнаты —
`403 wrong_room`.

Если нужны заголовки ответа, используйте `curl.exe` (в GET-запросе кавычки не
экранируются):

```powershell
curl.exe -i "$base/rooms/$($room.room_id)" -H "Authorization: Bearer $($room.token)"
```

Тот же запрос можно выполнить через Swagger: откройте
`http://localhost:8000/docs`, нажмите **Authorize**, введите
`Bearer <токен>` и выполните `GET /rooms/{room_id}`.

---

## Состояние комнаты

```json
{
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
    {"display_name": "Alice", "role": "host", "connected": true}
  ]
}
```

- `current_video_id` дублирует `playback.video_id` на верхнем уровне снимка.
- `queue` содержит все видео комнаты в текущем порядке, включая текущее.
- У участника есть `display_name`, `role` и `connected`.
- `title` у видео не используется.

---

## REST API

Токен передаётся в `Authorization: Bearer <token>`. `POST /rooms` и
`POST /rooms/join` выполняются без токена.

| Метод | Путь | Назначение |
| --- | --- | --- |
| `POST` | `/rooms` | Создать комнату, получить токен ведущего |
| `POST` | `/rooms/join` | Подключиться по `invite_code` |
| `GET` | `/rooms/{room_id}` | Полное состояние комнаты |
| `POST` | `/rooms/{room_id}/commands` | Выполнить команду |
| `POST` | `/rooms/{room_id}/connect` | Отметить соединение открытым |
| `POST` | `/rooms/{room_id}/disconnect` | Отметить соединение потерянным |
| `POST` | `/rooms/{room_id}/leave` | Выйти из комнаты |
| `GET` | `/internal/rooms/{room_id}/membership` | Проверка членства для Chat Service |
| `GET` | `/health` | Проверка живости |

`GET /internal/rooms/{room_id}/membership` возвращает при успехе ровно
`room_id`, `participant_id`, `display_name`, `role`, `connected`; при отказе —
ровно `is_member: false` и `room_id`.

---

## Команды

Тело команды:

```json
{
  "command_id": "cmd-1",
  "type": "playpause",
  "payload": {}
}
```

Пример выполнения команды из PowerShell:

```powershell
$cmd = @{
    command_id = "cmd-1"
    type = "add_video"
    payload = @{ url = "https://rutube.ru/video/abc123/" }
} | ConvertTo-Json -Depth 5 -Compress

$result = Invoke-RestMethod -Uri "$base/rooms/$($room.room_id)/commands" `
    -Method Post `
    -Headers @{ Authorization = "Bearer $($room.token)" } `
    -ContentType "application/json" `
    -Body $cmd

$result | ConvertTo-Json -Depth 8
```

| `type` | `payload` | Кто может |
| --- | --- | --- |
| `playpause` | `{}` | по режиму комнаты |
| `seek` | `{"position_seconds": 30}` | по режиму комнаты |
| `next` | `{}` | по режиму комнаты |
| `add_video` | `{"url": "https://rutube.ru/video/..."}` | по режиму комнаты |
| `remove_video` | `{"video_id": "uuid"}` | по режиму комнаты |
| `change_queue` | `{"video_ids": ["uuid-2", "uuid-1"]}` | по режиму комнаты |
| `set_control_mode` | `{"mode": "host_only" \| "all"}` | только ведущий |

Правила:

- `playpause` инвертирует `playback.is_playing`. Если текущего видео нет —
  `409 no_current_video`.
- `next` делает текущим следующий элемент очереди, не удаляя видео; если
  следующего нет — воспроизведение останавливается, а очередь сохраняется.
- `add_video` первое видео становится текущим и остаётся на паузе; видео
  попадает в `queue` и остаётся там в качестве текущего.
- `remove_video` удаляет видео из очереди; если удалён текущий, новым текущим
  становится первый оставшийся элемент на паузе.
- `change_queue` принимает **все** ID текущей очереди в новом порядке, каждый
  ровно один раз, включая текущее видео.
- Успешный ответ: `{"command_id":"cmd-1","duplicate":false,"state":{...}}`.
  Повтор с тем же `command_id` возвращает сохранённый `state` и
  `duplicate: true`, не применяя действие второй раз.

Ответ команды и событие для API Gateway содержат один и тот же снимок `state`.

---

## Выход и закрытие

`POST /rooms/{room_id}/leave` возвращает `{"left": true}`.

- Если вышел ведущий, роль сразу получает самый ранний подключённый участник.
- Когда вышел последний участник, комната получает `status: "closed"` и
  событие `room_closed`; новые команды и `joinRoom` отклоняются с `409
  room_closed`.
- Повторный `/leave` тем же токеном возвращает `401 unauthorized`.
- При потере соединения ведущего роль передаётся через 10 секунд;
  переподключение с тем же токеном отменяет передачу.
- Отдельного API удаления комнаты нет: закрытие наступает только после выхода
  последнего участника. Для полной очистки удалите `room.db` (локально) или
  выполните `docker compose down -v`.

---

## События для API Gateway

После каждой зафиксированной в БД Room Service отправляет событие:

```json
{
  "type": "room_state_changed",
  "room_id": "637c191e-49bf-453f-a335-5dc47b2ca6f8",
  "state_version": 3,
  "reason": "playpause",
  "state": {"status": "active", "control_mode": "host_only", "state_version": 3, "current_video_id": "video-1", "playback": {"video_id": "video-1", "position_seconds": 0, "is_playing": true}, "queue": [{"id": "video-1", "url": "https://rutube.ru/video/abc123/", "position": 0}], "participants": [{"display_name": "Alice", "role": "host", "connected": true}]}
}
```

Настройки:

- `ROOM_EVENT_PUBLISHER=http` (по умолчанию) — HTTP POST на
  `ROOM_API_EVENTS_URL` (по умолчанию
  `http://api-gateway:8080/internal/room-events`);
- `ROOM_EVENT_PUBLISHER=logging` — только лог, для локальной отладки;
  именно это значение используется в `docker-compose.yml`;
- `ROOM_EVENT_PUBLISHER=null` — события не отправляются, используется в тестах.

Для режима `http` принимающая сторона должна реализовать
`POST /internal/room-events` и отвечать `202`. Ошибка доставки события
логируется и не откатывает состояние: Gateway может получить актуальный снимок
через `GET /rooms/{room_id}`. Повтор команды с `duplicate: true` событие не
порождает.

---

## Валидация и ошибки

Сервер проверяет:

- ссылку Rutube (`invalid_video_url`);
- код приглашения (`invalid_payload`);
- `display_name`, `command_id`, `position_seconds` (конечное число ≥ 0);
- обязательные поля `control_mode`, `payload` и `video_ids`;
- UUID видео и точный состав `video_ids` в `change_queue`;
- членство и права по токену (`unauthorized`, `wrong_room`, `host_only_mode`,
  `host_only_command`);
- отсутствие лишних полей в теле запроса и payload.

Формат ошибки:

```json
{"error": {"code": "invalid_payload", "message": "Некорректные параметры запроса"}}
```

---

## Тесты

Запускайте команды из каталога `services/room-service`: там находится
`pyproject.toml` с настройками `pytest-asyncio`.

```powershell
python -m pytest -q
ruff check app tests
ruff format --check app tests
python -m compileall -q app
```

Для Linux/macOS те же команды запускаются с `python3` после активации venv.
Тесты проверяют создание и подключение по коду, форму снимка из контракта,
очередь вместе с текущим видео, `playpause`, идемпотентность, права, передачу
роли, закрытие комнаты при последнем выходе и публикацию событий.

---

## Ограничения прототипа

- Один экземпляр сервиса: блокировки и grace-таймеры живут в памяти.
- Таймеры передач роли не переживают перезапуск; состояние комнат при этом
  сохраняется в БД.
- `auto_create_tables=true` создаёт таблицы при старте; для production нужны
  миграции.
- `/internal/*` рассчитан на доверенную внутреннюю сеть.
- Длительность видео неизвестна: сервер не ограничивает позицию сверху.
