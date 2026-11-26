# Недокументированное в room-service

Этот файл описывает функциональность, которая намеренно оставлена в коде, но отсутствует в `api-contract.md`. Сам `api-contract.md` не изменялся. Всё, что в нём описано, приведено к контракту; ниже — дополнительные возможности сервиса.

---

## 1. `POST /rooms/{room_id}/connect`

**Код:** `app/api/rooms.py:68`, `app/services/rooms.py:173-209`.

### Зачем

Room-service не владеет WebSocket-соединением клиента, но должен знать, открыта сессия участника или потеряна. Этот REST-выполняет роль внутреннего сигнала «participant подключился».

Он нужен для:

- флага `connected` в `state`;
- отмены отложенной передачи роли, если ведущий переподключился в течение 10 секунд;
- публикации события изменения, если внутренний флаг действительно изменился.

### Запрос

```http
POST /rooms/{room_id}/connect
Authorization: Bearer <token>
```

Тело отсутствует.

### Ответ `200`

Полный `state` из контракта:

```json
{
  "status": "active",
  "control_mode": "host_only",
  "state_version": 3,
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

### Поведение

- Если участник уже был `connected=true`, `state_version` не увеличивается и событие не отправляется.
- Если был `false`: ставится `true`, `state_version++`, отправляется событие `reason: "participant_connected"`.
- Всегда отменяется ожидающая передача роли для этого участника.
- Возможные ошибки только из контракта: `401 unauthorized`, `403 wrong_room`.

---

## 2. `POST /rooms/{room_id}/disconnect`

**Код:** `app/api/rooms.py:78`, `app/services/rooms.py:212-253`.

### Зачем

Отмечает потерю соединения. Нужно для правила `api-contract.md:130`: если ведущий потерял соединение, роль передаётся через 10 секунд, если он не восстановился.

### Запрос

```http
POST /rooms/{room_id}/disconnect
Authorization: Bearer <token>
```

Тело отсутствует.

### Ответ `200`

Тот же полный `state`, но у участника:

```json
{"display_name": "Alice", "role": "host", "connected": false}
```

### Поведение

- При первом `disconnect`: `connected=false`, `disconnected_at=<now>`, `connection_generation++`, `state_version++`.
- Если участник — ведущий, планируется таймер передачи роли.
- Отправляется событие `reason: "participant_disconnected"`.
- Повторный `disconnect` без изменений не увеличивает `state_version` и не отправляет событие.
- `connect` с тем же токеном отменяет запланированную передачу роли.
- Возможные ошибки только из контракта: `401 unauthorized`, `403 wrong_room`.

---

## 3. `GET /health`

**Код:** `app/main.py:88`.

### Зачем

Проверка живости для Docker/compose, оркестратора и локальной отладки. Бизнес-логики не несёт.

### Запрос

```http
GET /health
```

Без токена и без тела.

### Ответ `200`

```json
{"status": "ok"}
```

В `api-contract.md` строки для health нет, поэтому эндпоинт оставлен как есть.

---

## 4. Отказ `GET /internal/rooms/{room_id}/membership`

**Код:** `app/services/rooms.py:307-321`, `app/api/internal.py:22`.

### Зачем

Chat Service должен получать простой ответ «можно ли принять сообщение», не разбирая коды авторизации room-service. Endpoint возвращает `200` и явный признак `is_member:false`.

### Успех

Форма из `api-contract.md:102`:

```json
{
  "room_id": "637c191e-49bf-453f-a335-5dc47b2ca6f8",
  "participant_id": "participant-1",
  "display_name": "Alice",
  "role": "host",
  "connected": true
}
```

### Отказ, которого нет в контракте

```json
{
  "is_member": false,
  "room_id": "637c191e-49bf-453f-a335-5dc47b2ca6f8"
}
```

Возвращается, если:

- токен отсутствует;
- токен не найден;
- токен принадлежит другой комнате;
- участник уже вышел (`is_active=false`).

Это внутренний member-check, а не защищённый публичный REST, поэтому не используются `401/403`. Chat Service сам решает, что отвечать клиенту. Поле `is_member` и denied-форма в `api-contract.md` не описаны.

---

## 5. События `room_state_changed`

**Код:** `app/integrations/events.py:43-85`, вызовы в `app/services/rooms.py`, `app/services/commands.py`, `app/services/handover.py`.

### Зачем

По требованию «как только что-то изменилось — кидать это в апи сервис». Gateway затем может рассылать `sendState` по WebSocket без polling-а room-service.

В контракте есть только Gateway→Client `sendState` (`api-contract.md:55-56`), но нет Room Service→Gateway события, поэтому вся publisher-часть оставлена в коде.

### Формат события

```json
{
  "type": "room_state_changed",
  "room_id": "637c191e-49bf-453f-a335-5dc47b2ca6f8",
  "state_version": 3,
  "reason": "playpause",
  "state": {
    "status": "active",
    "control_mode": "host_only",
    "state_version": 3,
    "current_video_id": "video-1",
    "playback": {
      "video_id": "video-1",
      "position_seconds": 0,
      "is_playing": true
    },
    "queue": [
      {"id": "video-1", "url": "https://rutube.ru/video/abc123/", "position": 0}
    ],
    "participants": [
      {"display_name": "Alice", "role": "host", "connected": true}
    ]
  }
}
```

`state` — тот же объект, что возвращают `GET /rooms/{room_id}` и ответ команды.

### `reason`

- `created` — комната создана;
- `participant_joined` — участник вошёл;
- `participant_connected` — соединение восстановлено;
- `participant_disconnected` — соединение потеряно;
- `participant_left` — участник вышел;
- `room_closed` — комната закрылась автоматически;
- `host_changed` — роль ведущего передана по таймеру;
- `playpause`, `seek`, `next`, `add_video`, `remove_video`, `change_queue`, `set_control_mode` — тип выполненной команды.

Повтор команды с `duplicate: true` событие **не** отправляет.

### Куда отправляется

`HttpEventPublisher` делает:

```http
POST http://api-gateway:8080/internal/room-events
Content-Type: application/json

<event JSON>
```

### Настройки

- `ROOM_EVENT_PUBLISHER=http` — default в `app/config.py:19`;
- `ROOM_API_EVENTS_URL` — default `http://api-gateway:8080/internal/room-events`;
- `ROOM_API_EVENTS_TIMEOUT_SECONDS` — default `2.0`;
- `ROOM_EVENT_PUBLISHER=logging` — только лог, используется в `docker-compose.yml` и тестах;
- `ROOM_EVENT_PUBLISHER=null` — ничего не отправляется.

Любой `httpx.HTTPError` или не-2xx логируется warning-ом и **не откатывает** состояние. Если Gateway не получил событие, он может запросить актуальный снимок через `GET /rooms/{room_id}`.

Принимающий `/internal/room-events` в API Gateway не реализован.
