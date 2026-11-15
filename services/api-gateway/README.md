# API Gateway

Предварительный контракт текущего каркаса. **Backend-вызовы пока работают через заглушки, не через HTTP.** Адреса внутренних сервисов и их сетевые JSON-контракты ещё согласуются. ТР не заменяется этим документом.

## Запуск

Из `services/api-gateway/`, с JDK 21:

```bash
./gradlew bootRun
./gradlew test
```

HTTP: `http://localhost:8080`. WebSocket: `ws://localhost:8080/ws`.
Для ручной проверки: `http://localhost:8080/ws-test.html`, затем консоль браузера.

## Форматы данных

В таблицах используются сокращения:

| Объект | Поля |
|---|---|
| `Session` | `sessionToken: string`, `userId: string`, `roomId: string` |
| `State` | `roomId: string`, `version: integer`, `paused: boolean`, `positionSeconds: number`, `currentVideo: Item \| null`, `queue: Item[]` |
| `Item` | `itemId: string`, `url: string` |
| `ChatMessage` | `messageId: string`, `roomId: string`, `userId: string`, `text: string`, `sentAt: string` |

Позиция — в секундах. `sentAt` — время в ISO 8601. Токен сессии — секрет, не передаётся другим участникам. Модели предварительные, в частности пока нет списка участников и временной опоры позиции плеера.

## Client ↔ Gateway

### REST

Тела ответов — JSON. Создание и вход сейчас не требуют тела запроса.

| Отправитель → получатель | Метод / путь | Запрос | Успешный ответ |
|---|---|---|---|
| Client → Gateway | `GET /health` | Без тела | `200`, `{ "status": "ok" }` — отвечает только сам Gateway |
| Client → Gateway | `POST /rooms` | Без тела | `201`, `{ roomId, version, paused, positionSeconds, session: Session }`; заголовок `Location: /rooms/{roomId}/state` |
| Client → Gateway | `POST /rooms/{roomId}/join` | `roomId` в пути, без тела | `200`, `{ state: State, session: Session }` |
| Client → Gateway | `GET /rooms/{roomId}/state` | `roomId` в пути, без тела | `200`, `State` |

Обработанная ошибка отсутствующей комнаты: `404`, `{ "code": "ROOM_NOT_FOUND", "message": "..." }`. Фейк сейчас её не генерирует; тесты проверяют передачу ошибки от подменённого backend. Единый формат прочих REST-ошибок и проверка токена REST-чтения пока не реализованы.

### WebSocket: запросы клиента

Общий конверт:

```json
{
  "type": "playback.seek",
  "requestId": "request-1",
  "payload": {
    "sessionToken": "demo-host-token",
    "commandId": "command-1",
    "positionSeconds": 120.5
  }
}
```

`type` и `requestId` — непустые строки. Для прикладных команд `payload` — объект; у `ping` его содержимое не проверяется. В таблице перечислены поля `payload`, а не отдельные HTTP-endpoints.

Для команд ниже **`C` = `sessionToken: string` + `commandId: string`**, обе строки непустые. `requestId` связывает запрос с ответом; `commandId` предназначен для дедупликации операции ответственным сервисом. Это разные назначения.

| Отправитель → получатель | `type`                 | Поля `payload`                                    | Успешный результат                                                |
| ------------------------ | ---------------------- | ------------------------------------------------- | ----------------------------------------------------------------- |
| Client → Gateway         | `ping`                 | Не используются                                   | Только отправителю: `pong`, `{ status: "ok" }`                    |
| Client → Gateway         | `session.authenticate` | `sessionToken: string`, непустой                  | Только отправителю: `session.authenticated`, `{ userId, roomId }` |
| Client → Gateway         | `playback.play`        | `C`                                               | Комнате: `room.state`; отправителю: `command.ack`                 |
| Client → Gateway         | `playback.pause`       | `C`                                               | Комнате: `room.state`; отправителю: `command.ack`                 |
| Client → Gateway         | `playback.seek`        | `C`, `positionSeconds: number`                    | Комнате: `room.state`; отправителю: `command.ack`                 |
| Client → Gateway         | `playback.next`        | `C`                                               | Комнате: `room.state`; отправителю: `command.ack`                 |
| Client → Gateway         | `queue.add`            | `C`, `url: string`                                | Комнате: `room.state`; отправителю: `command.ack`                 |
| Client → Gateway         | `queue.remove`         | `C`, `itemId: string`                             | Комнате: `room.state`; отправителю: `command.ack`                 |
| Client → Gateway         | `queue.move`           | `C`, `itemId: string`, `toIndex: integer` (int32) | Комнате: `room.state`; отправителю: `command.ack`                 |
| Client → Gateway         | `chat.send`            | `C`, `text: string`                               | Комнате: `chat.message`; отправителю: `command.ack`               |

До авторизации разрешены только `ping` и `session.authenticate`. Повторная авторизация уже привязанного соединения отклоняется.

Gateway проверяет форму данных, но не существование комнаты, права, допустимость ссылки, диапазоны позиции/индекса или содержание текста. Числовая позиция должна представляться конечным `double`. Решения о принятии команды делегируются backend. Ограничения диапазонов и правила очереди необходимо согласовать с Room Service.

### WebSocket: ответы и события сервера

Все сообщения имеют конверт `{ type, requestId, payload }`.

| Отправитель → получатель | `type` | `requestId` | `payload` |
|---|---|---|---|
| Gateway → отправитель | `pong` | Из запроса | `{ status: "ok" }` |
| Gateway → отправитель | `session.authenticated` | Из запроса | `{ userId, roomId }` |
| Gateway → отправитель команды комнаты | `command.ack` | Из запроса | `{ commandId, stateVersion }` |
| Gateway → отправитель сообщения чата | `command.ack` | Из запроса | `{ commandId, messageId }` |
| Gateway → все подключённые клиенты комнаты, включая отправителя | `room.state` | `null` | `State`, полученный от backend |
| Gateway → все подключённые клиенты комнаты, включая отправителя | `chat.message` | `null` | `ChatMessage`, полученный от backend |
| Gateway → отправитель | `error` | Из запроса, либо `null`, если ID не удалось извлечь | `{ code: string, message: string }` |

Сейчас рассылка события вызывается перед отправкой подтверждения. При отклонении команды её событие не рассылается. Подтверждение не означает доставку события всем клиентам.

Возможные обработанные коды: `INVALID_MESSAGE`, `UNKNOWN_MESSAGE_TYPE`, `UNAUTHORIZED`, `ALREADY_AUTHENTICATED`, а также отказы backend: например, `FORBIDDEN`, `ROOM_NOT_FOUND`, `QUEUE_ITEM_NOT_FOUND`, `INVALID_QUEUE_POSITION`. Это не полная спецификация ошибок будущих сервисов.

## Gateway ↔ внутренние сервисы

**Ниже текущие Java-вызовы интерфейсов, а не утверждённые HTTP-адреса или JSON-тела.** При интеграции их реализации будут отправлять HTTP-запросы. Несколько методов могут соответствовать одному внутреннему endpoint команд.

**Разработчикам Room Service и Chat Service:** для необходимых операций укажите HTTP-методы и пути endpoints, формат запросов, способ передачи сессии, успешные ответы и ошибки. Эти контракты согласуются с разработчиком Gateway, после чего Gateway сможет отправлять соответствующие HTTP-запросы вместо вызовов заглушек. Имена Java-методов ниже не требуют отдельных одноимённых endpoints: несколько операций могут обслуживаться одним endpoint. Таблица — предварительный список потребностей Gateway, а не полная спецификация сервисов по ТР.

| Отправитель → получатель | Текущая операция интерфейса | Передаваемые данные | Ожидаемый результат |
|---|---|---|---|
| Gateway → Room Service | `RoomBackend.createRoom()` | Пока без параметров | `{ state: State, session: Session }` |
| Gateway → Room Service | `RoomBackend.joinRoom(roomId)` | `roomId` | `{ state: State, session: Session }` |
| Gateway → Room Service | `RoomBackend.getSnapshot(roomId)` | `roomId`; передача токена для этого вызова ещё требуется | `State` |
| Gateway → Room Service / проверка сессии | `SessionBackend.findByToken(sessionToken)` | `sessionToken` | `Session` или отсутствие действительной сессии |
| Gateway → Room Service | `RoomBackend.play(...)` | `roomId`, `sessionToken`, `commandId` | `State` или отказ |
| Gateway → Room Service | `RoomBackend.pause(...)` | `roomId`, `sessionToken`, `commandId` | `State` или отказ |
| Gateway → Room Service | `RoomBackend.seek(...)` | `roomId`, `sessionToken`, `commandId`, `positionSeconds` | `State` или отказ |
| Gateway → Room Service | `RoomBackend.next(...)` | `roomId`, `sessionToken`, `commandId` | `State` или отказ |
| Gateway → Room Service | `RoomBackend.addVideo(...)` | `roomId`, `sessionToken`, `commandId`, `url` | `State` или отказ |
| Gateway → Room Service | `RoomBackend.removeVideo(...)` | `roomId`, `sessionToken`, `commandId`, `itemId` | `State` или отказ |
| Gateway → Room Service | `RoomBackend.moveVideo(...)` | `roomId`, `sessionToken`, `commandId`, `itemId`, `toIndex` | `State` или отказ |
| Gateway → Chat Service | `ChatBackend.sendMessage(...)` | `roomId`, `userId` из привязки соединения, `sessionToken`, `commandId`, `text` | `ChatMessage` или отказ |

Room Service отвечает за комнаты, сессии, права, состояние, версии, порядок команд и дедупликацию. Chat Service отвечает за принятие и сохранение сообщения и проверяет членство через Room Service согласно ТР. Gateway хранит только локальные подключения и подтверждённую backend привязку пользователя/комнаты, направляет запросы и доставляет ответы/события.

При интеграции результаты команд нужно расширить до согласованного подтверждения с полным состоянием/сообщением: текущие интерфейсы возвращают только данные, а Gateway формирует `ack` сам. Сетевые ошибки и HTTP-статусы также ещё согласуются.

## Заглушки и ограничения

- `FakeRoomBackend` не хранит состояние и не применяет команды: возвращает пример `State` с версией `1`, паузой и пустой очередью.
- Создание/вход возвращают фиксированную комнату `demo-room`. Токены: `demo-host-token` и `demo-guest-token`; это **не настоящая аутентификация**, не использовать для реальных пользователей.
- `FakeSessionBackend` возвращает подготовленные привязки для этих двух токенов. Остальные не принимает.
- `FakeChatBackend` возвращает сообщение с фиксированными ID/временем и переданным текстом. Историю не хранит и не загружает.
- Фейки не подтверждают корректность бизнес-операций. Тесты проверяют транспорт, делегирование и передачу ошибок, а не реальную интеграцию.
- Пока отсутствуют настоящие HTTP-клиенты, полноценная защита REST, роли/настройки, список участников, connect/disconnect/leave в Room Service, начальный снимок при WebSocket-подключении, восстановление/периодическая сверка, дедупликация, `messageSeq`, таймауты и ограничения нагрузки.
- При закрытии сокета очищается только локальный реестр; уведомления внутренних сервисов пока нет.
- Автоматические повторы изменяющих команд не включать до интеграции дедупликации. Проект пока не является полной реализацией ТР.
