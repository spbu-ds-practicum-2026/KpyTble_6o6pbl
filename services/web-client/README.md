# Plotina Web Client

Веб-клиент системы совместного просмотра видео Plotina.

## Возможности текущего каркаса

- создание комнаты через REST;
- подключение к комнате через REST;
- хранение сессии отдельно для каждой вкладки;
- WebSocket-подключение к API Gateway;
- авторизация через `session.authenticate`;
- heartbeat и автоматическое переподключение;
- обработка `room.state`, `chat.message`, `command.ack`, `error`;
- команды управления воспроизведением и очередью;
- генерация отдельных `requestId` и `commandId`;
- игнорирование устаревших версий состояния комнаты;
- REST-сверка состояния после reconnect и по таймеру;
- базовый интерфейс комнаты, очереди, участников и чата.

## Требования

- Node.js 20 или новее;
- npm;
- запущенный API Gateway на `http://localhost:8080`.

## Запуск Gateway

Из `services/api-gateway/`:

```bash
./gradlew bootRun
```

## Запуск Web Client

Из `services/web-client/`:

```bash
npm install
cp .env.example .env
npm run dev
```

Приложение будет доступно по адресу:

```text
http://localhost:5173
```

## Проверка сборки

```bash
npm run typecheck
npm run build
```

## Переменные окружения

- `VITE_API_BASE_URL` — базовый REST URL, по умолчанию `/api`;
- `VITE_WS_URL` — полный WebSocket URL; если не задан, используется `/ws` текущего origin;
- `VITE_RETRY_PENDING_COMMANDS` — повторять неподтверждённые команды после reconnect;
- `VITE_HEARTBEAT_INTERVAL_MS` — интервал heartbeat;
- `VITE_HEARTBEAT_TIMEOUT_MS` — время ожидания `pong`;
- `VITE_STATE_SYNC_INTERVAL_MS` — период REST-сверки состояния.

В development Vite проксирует:

- `/api/*` → `http://localhost:8080/*`;
- `/ws` → `ws://localhost:8080/ws`.

## Важные ограничения

1. Текущий API Gateway использует backend-заглушки и не хранит реальное состояние.
2. Повтор команд реализован, но выключен по умолчанию до появления серверной дедупликации по `commandId`.
3. Gateway пока не возвращает участников комнаты.
4. Gateway пока не возвращает `messageSeq`, поэтому чат отображается в порядке доставки.
5. В состоянии пока отсутствует временная опора позиции плеера. Точная синхронизация позиции будет добавлена после появления `positionUpdatedAt`/`serverTime`.
6. Embed Rutube отображается, но команды pause/play/seek пока не применяются к iframe. Для этого требуется зафиксированный API управления Rutube-плеером.
7. Полное восстановление страницы с прежним токеном требует REST endpoint восстановления сессии. Автоматическое восстановление уже открытого WebSocket работает с прежним токеном.