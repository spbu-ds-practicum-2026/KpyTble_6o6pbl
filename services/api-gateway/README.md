# API Gateway Plotina

Gateway реализует клиентские REST/WebSocket сообщения и внутренние HTTP-вызовы
по итоговому `api-contract.md`. Room и Chat вызываются по HTTP, production-заглушек нет.
Изменения состояния, права, валидация Rutube, транзакции и дедупликация — ответственность сервисов.

## Запуск и тесты

Нужен JDK 21:

```bash
./gradlew test
ROOM_SERVICE_URL=http://localhost:8000 CHAT_SERVICE_URL=http://localhost:8001 ./gradlew bootRun
```

Gateway: `http://localhost:8080`, WebSocket: `/ws`, проверка процесса: `/health`.
Порт меняется через `SERVER_PORT`. Таймаут внутренних запросов:
`SERVICE_REQUEST_TIMEOUT_MS` (по умолчанию 3000).
Ручная проверка: `http://localhost:8080/ws-test.html`.

## REST

| Метод | Путь | JSON | Успех |
|---|---|---|---|
| POST | `/rooms` | `{"display_name":"Alice","control_mode":"host_only"}` | 201, ответ Room Service без изменений |
| POST | `/rooms/join` | `{"invite_code":"AbCdEf_12345","display_name":"Bob"}` | 201, ответ Room Service без изменений |

Эти два запроса не требуют токена. Тела и ошибки соответствуют контракту;
ошибка имеет форму `{"error":{"code":"...","message":"..."}}`.

## WebSocket `/ws`

Первым сообщением рекомендуется отправить:

```json
{"type":"getState","token":"alice-token","payload":{}}
```

Токен обязателен **в каждом пользовательском сообщении**, не в query string и не внутри payload.
До первого сообщения Gateway не знает сессию: начальный `sendState` отправляется после
первого валидного сообщения с токеном и успешного чтения состояния из Room Service.
Он содержит `initialMessageSeq`, полученный из Chat Service.
Повторные `getState` возвращают `sendState` без начального номера.
Во время инициализации рассылки буферизуются; сообщения чата с номером не больше
начального не отправляются. Буфер ограничен 256 событиями.

| type | payload | HTTP-вызов |
|---|---|---|
| `playpause` | `{}` | POST `/rooms/{room_id}/commands`, type=`playpause` |
| `nextVideo` | `{}` | commands, type=`next` |
| `seek` | `{"position_seconds":30}` | commands, type=`seek` |
| `addVideo` | `{"url":"https://rutube.ru/video/abc123/"}` | commands, type=`add_video` |
| `removeVideo` | `{"video_id":"video-1"}` | commands, type=`remove_video` |
| `changeQueue` | `{"video_ids":["video-2","video-1"]}` | commands, type=`change_queue` |
| `setSettings` | `{"mode":"all"}` | commands, type=`set_control_mode` |
| `leaveRoom` | `{}` | POST `/rooms/{room_id}/leave`, без тела |
| `sendMessage` | `{"text":"Привет!"}` | POST `/rooms/{room_id}/messages` |
| `getState` | `{}` | GET `/rooms/{room_id}` |
| `getChatSeq` | `{}` | GET `/rooms/{room_id}/messages/seq` |

Для изменяющих действий обязателен верхнеуровневый `commandId`, который передаётся
как `command_id`. Чтения отправляются без ID. Внутренние запросы передают
`Authorization: Bearer <token>`; клиентские participant_id/роли не принимаются.

Команды подтверждаются `commandConfirm` с исходным `commandId`, флагом `duplicate`
и полным `state` либо `message`. Выход подтверждается `left`, без `duplicate`.
После выхода сокет закрывается. `getChatSeq` возвращает `commandConfirm` с `messageSeq`, без ID.
Бизнес-ошибки сервисов сохраняют `code` и `message`.

Рассылка состояния: `{"type":"sendState","state":{...}}`.
Рассылка чата, включая автора: `{"type":"sendMessage","message":{...}}`.
Токены и ID чужих команд в рассылки не попадают. Старое состояние из duplicate-ответа
не рассылается; duplicate-сообщение чата рассылается с прежним messageSeq.
Подтверждение отправляется до рассылки.

Heartbeat: Gateway отправляет `{"type":"pig","pigId":"..."}`;
клиент отвечает `{"type":"pong","pigId":"..."}`. Интервал — 5 секунд,
ожидание ответа — 10 секунд. Неверный pigId не подтверждает heartbeat.
Неавторизованные соединения также имеют 10 секунд на инициализацию.
Каждую секунду Gateway перечитывает состояние активных комнат для сверки клиентов.
Интервалы настраиваются свойствами `gateway.heartbeat-interval-ms`,
`gateway.heartbeat-timeout-ms`, `gateway.state-refresh-ms`.

Сетевые ошибки: `service_unavailable` (502), `gateway_timeout` (504).
Gateway не повторяет изменяющие запросы автоматически. После таймаута клиент должен
повторить команду с **тем же ID и параметрами**.

## Границы действующего контракта

Не добавляются выдуманные endpoint-ы или обязательные параметры. Поэтому есть
интеграционные ограничения, которые невозможно снять только в Gateway:

* Контракт не содержит поиска комнаты по непрозрачному токену. Gateway запоминает
  `token → room_id` из create/join в памяти и проверяет токен через защищённое чтение
  Room Service. Переподключение работает, пока жив этот экземпляр Gateway.
  После перезапуска привязки теряются; для восстановления старых сессий нужен
  согласованный механизм разрешения токена или постоянное хранилище привязок.
* Контракт не содержит вызовов уведомления Room Service о connect/disconnect.
  Gateway обнаруживает обрыв и чистит свои соединения, но не может сообщить сервису
  о потере связи и запустить предусмотренную ТР передачу ведущего через 10 секунд.
  Явный leave отправляется строго по контракту.
* Нет endpoint-а чтения пропущенных сообщений чата. `getChatSeq` реализован,
  но восстановление диапазона сообщений из ТР требует дополнения контракта.
* Для начального `initialMessageSeq` необходим доступный Chat Service.
  После инициализации сбой Chat Service не блокирует команды комнаты.
* Реализация рассчитана на один экземпляр Gateway. Команды одной WebSocket-сессии
  поступают последовательно; глобальный порядок команд комнаты и дедупликацию
  обеспечивает Room Service согласно контракту.

Тесты в `src/test` поднимают настоящий Gateway на случайном порту и контрактные
HTTP-серверы Room/Chat. Это проверка Gateway независимо от готовности других сервисов,
не утверждение о завершённой интеграции всего проекта.
