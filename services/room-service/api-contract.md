# Контракт API Plotina

## Общие правила

|Поле / правило|Значение|
|-|-|
|Область|Итоговый контракт взаимодействия сервисов; изменения касаются документа, не реализации сервисов.|
|Токен|Каждая вкладка имеет собственный token. Участник, комната и права определяются сервером по токену. participant\_id в командах клиента не передаётся.|
|REST-авторизация|`Authorization: Bearer alice-token`. createRoom и joinRoom — без токена.|
|WebSocket|`/ws`; token передаётся в каждом пользовательском сообщении.|
|commandId / command\_id|ID изменяющего действия; Gateway переводит commandId в command\_id. При повторе сохраняются ID и параметры. Отдельного ID отправки нет.|
|Чтение|getState и getChatSeq отправляются без commandId; ответ определяется по type и содержимому.|
|duplicate|false — первое выполнение; true — возврат сохранённого результата без повторного действия.|
|state|status, control\_mode, state\_version, current\_video\_id, playback, queue, participants — структура из предоставленного состояния Room Service.|
|Версии|Более новая state\_version заменяет снимок; старая игнорируется; одинаковая допускается для коррекции позиции.|
|playpause|payload пустой. Room Service атомарно переключает is\_playing и сохраняет результат с command\_id. Повтор не переключает состояние второй раз. Без текущего видео — no\_current\_video.|
|changeQueue|payload.video\_ids — все ID текущей очереди в новом порядке, каждый ровно один раз. Проверка, перестановка и сохранение результата выполняются одной транзакцией. Текущее видео не меняется.|
|Изменения Room Service|В /commands используются playpause вместо отдельных play/pause и change\_queue вместо move\_video. Это итоговые команды данного контракта.|
|addVideo|В payload только url. title не используется ни в запросах, ни в ответах.|
|Комната|В путях `{room\_id}` = `637c191e-49bf-453f-a335-5dc47b2ca6f8`. ID и токены в примерах условные. Каждая строка — отдельный пример вызова.|
|Выход|leaveRoom вызывает /leave. Дедупликация /commands не распространяется на /leave.|
|Граница схем|Состояние взято из README; полные ответы /leave, membership, элементы очереди и API Chat Service закреплены здесь как интеграционный контракт.|

# Client → API Gateway

## REST

|Описание|Метод|Путь|Заголовки|Тело запроса|Код|Тело ответа|
|-|-|-|-|-|-|-|
|createRoom|POST|`/rooms`|`Content-Type: application/json`|`{"display\_name":"Alice","control\_mode":"host\_only"}`|201|`{"room\_id":"637c191e-49bf-453f-a335-5dc47b2ca6f8","invite\_code":"AbCdEf\_12345","invite\_link":"http://localhost:3000/rooms/AbCdEf\_12345","token":"alice-token","participant":{"display\_name":"Alice","role":"host","connected":true},"state":{"status":"active","control\_mode":"host\_only","state\_version":1,"current\_video\_id":null,"playback":{"video\_id":null,"position\_seconds":0,"is\_playing":false},"queue":\[],"participants":\[{"display\_name":"Alice","role":"host","connected":true}]}}`|
|joinRoom|POST|`/rooms/join`|`Content-Type: application/json`|`{"invite\_code":"AbCdEf\_12345","display\_name":"Bob"}`|201|`{"room\_id":"637c191e-49bf-453f-a335-5dc47b2ca6f8","invite\_code":"AbCdEf\_12345","invite\_link":"http://localhost:3000/rooms/AbCdEf\_12345","token":"bob-token","participant":{"display\_name":"Bob","role":"member","connected":true},"state":{"status":"active","control\_mode":"host\_only","state\_version":2,"current\_video\_id":null,"playback":{"video\_id":null,"position\_seconds":0,"is\_playing":false},"queue":\[],"participants":\[{"display\_name":"Alice","role":"host","connected":true},{"display\_name":"Bob","role":"member","connected":true}]}}`|

## WebSocket

|Описание|Сообщение клиента|Сообщение ответа|
|-|-|-|
|playpause|`{"type":"playpause","commandId":"cmd-1","token":"alice-token","payload":{}}`|`{"type":"commandConfirm","commandId":"cmd-1","duplicate":false,"state":{"status":"active","control\_mode":"host\_only","state\_version":3,"current\_video\_id":"video-1","playback":{"video\_id":"video-1","position\_seconds":0,"is\_playing":true},"queue":\[{"id":"video-1","url":"https://rutube.ru/video/abc123/","position":0}],"participants":\[{"display\_name":"Alice","role":"host","connected":true}]}}`|
|nextVideo|`{"type":"nextVideo","commandId":"cmd-2","token":"alice-token","payload":{}}`|`{"type":"commandConfirm","commandId":"cmd-2","duplicate":false,"state":{"status":"active","control\_mode":"host\_only","state\_version":4,"current\_video\_id":null,"playback":{"video\_id":null,"position\_seconds":0,"is\_playing":false},"queue":\[{"id":"video-1","url":"https://rutube.ru/video/abc123/","position":0}],"participants":\[{"display\_name":"Alice","role":"host","connected":true}]}}`|
|seek|`{"type":"seek","commandId":"cmd-3","token":"alice-token","payload":{"position\_seconds":30}}`|`{"type":"commandConfirm","commandId":"cmd-3","duplicate":false,"state":{"status":"active","control\_mode":"host\_only","state\_version":4,"current\_video\_id":"video-1","playback":{"video\_id":"video-1","position\_seconds":30,"is\_playing":false},"queue":\[{"id":"video-1","url":"https://rutube.ru/video/abc123/","position":0}],"participants":\[{"display\_name":"Alice","role":"host","connected":true}]}}`|
|addVideo|`{"type":"addVideo","commandId":"cmd-4","token":"alice-token","payload":{"url":"https://rutube.ru/video/abc123/"}}`|`{"type":"commandConfirm","commandId":"cmd-4","duplicate":false,"state":{"status":"active","control\_mode":"host\_only","state\_version":2,"current\_video\_id":"video-1","playback":{"video\_id":"video-1","position\_seconds":0,"is\_playing":false},"queue":\[{"id":"video-1","url":"https://rutube.ru/video/abc123/","position":0}],"participants":\[{"display\_name":"Alice","role":"host","connected":true}]}}`|
|removeVideo|`{"type":"removeVideo","commandId":"cmd-5","token":"alice-token","payload":{"video\_id":"video-1"}}`|`{"type":"commandConfirm","commandId":"cmd-5","duplicate":false,"state":{"status":"active","control\_mode":"host\_only","state\_version":3,"current\_video\_id":null,"playback":{"video\_id":null,"position\_seconds":0,"is\_playing":false},"queue":\[],"participants":\[{"display\_name":"Alice","role":"host","connected":true}]}}`|
|leaveRoom|`{"type":"leaveRoom","commandId":"cmd-6","token":"alice-token","payload":{}}`|`{"type":"commandConfirm","commandId":"cmd-6","left":true}`|
|sendMessage|`{"type":"sendMessage","commandId":"cmd-7","token":"alice-token","payload":{"text":"Привет!"}}`|`{"type":"commandConfirm","commandId":"cmd-7","duplicate":false,"message":{"message\_id":"message-1","messageSeq":43,"participant\_id":"participant-1","text":"Привет!","created\_at":"2026-11-19T12:00:00Z"}}`|
|getState|`{"type":"getState","token":"alice-token","payload":{}}`|`{"type":"sendState","state":{"status":"active","control\_mode":"host\_only","state\_version":1,"current\_video\_id":null,"playback":{"video\_id":null,"position\_seconds":0,"is\_playing":false},"queue":\[],"participants":\[{"display\_name":"Alice","role":"host","connected":true}]}}`|
|changeQueue|`{"type":"changeQueue","commandId":"cmd-9","token":"alice-token","payload":{"video\_ids":\["video-2","video-1"]}}`|`{"type":"commandConfirm","commandId":"cmd-9","duplicate":false,"state":{"status":"active","control\_mode":"host\_only","state\_version":5,"current\_video\_id":"video-1","playback":{"video\_id":"video-1","position\_seconds":0,"is\_playing":false},"queue":\[{"id":"video-2","url":"https://rutube.ru/video/def456/","position":0},{"id":"video-1","url":"https://rutube.ru/video/abc123/","position":1}],"participants":\[{"display\_name":"Alice","role":"host","connected":true}]}}`|
|getChatSeq|`{"type":"getChatSeq","token":"alice-token","payload":{}}`|`{"type":"commandConfirm","messageSeq":43}`|
|setSettings|`{"type":"setSettings","commandId":"cmd-11","token":"alice-token","payload":{"mode":"all"}}`|`{"type":"commandConfirm","commandId":"cmd-11","duplicate":false,"state":{"status":"active","control\_mode":"all","state\_version":2,"current\_video\_id":null,"playback":{"video\_id":null,"position\_seconds":0,"is\_playing":false},"queue":\[],"participants":\[{"display\_name":"Alice","role":"host","connected":true}]}}`|

# API Gateway → Client

## WebSocket

|Описание|Когда|Полное сообщение сервера|
|-|-|-|
|sendState|При подключении; initialMessageSeq задаёт начало чата|`{"type":"sendState","initialMessageSeq":42,"state":{"status":"active","control\_mode":"host\_only","state\_version":1,"current\_video\_id":null,"playback":{"video\_id":null,"position\_seconds":0,"is\_playing":false},"queue":\[],"participants":\[{"display\_name":"Alice","role":"host","connected":true}]}}`|
|sendState|Рассылка изменений; без токена и ID чужой команды|`{"type":"sendState","state":{"status":"active","control\_mode":"all","state\_version":2,"current\_video\_id":null,"playback":{"video\_id":null,"position\_seconds":0,"is\_playing":false},"queue":\[],"participants":\[{"display\_name":"Alice","role":"host","connected":true}]}}`|
|sendMessage|Рассылка чата, включая автора|`{"type":"sendMessage","message":{"message\_id":"message-1","messageSeq":43,"participant\_id":"participant-1","text":"Привет!","created\_at":"2026-11-19T12:00:00Z"}}`|
|pig|Проверка соединения|`{"type":"pig","pigId":"pig-1"}`|
|commandConfirm|Подтверждение команды комнаты|`{"type":"commandConfirm","commandId":"cmd-11","duplicate":false,"state":{"status":"active","control\_mode":"all","state\_version":2,"current\_video\_id":null,"playback":{"video\_id":null,"position\_seconds":0,"is\_playing":false},"queue":\[],"participants":\[{"display\_name":"Alice","role":"host","connected":true}]}}`|
|commandConfirm|Повтор выполненной команды: прежний commandId и сохранённый state|`{"type":"commandConfirm","commandId":"cmd-11","duplicate":true,"state":{"status":"active","control\_mode":"all","state\_version":2,"current\_video\_id":null,"playback":{"video\_id":null,"position\_seconds":0,"is\_playing":false},"queue":\[],"participants":\[{"display\_name":"Alice","role":"host","connected":true}]}}`|
|commandConfirm|Ошибка команды|`{"type":"commandConfirm","commandId":"cmd-1","error":{"code":"no\_current\_video","message":"Не выбрано видео"}}`|

## Client → API Gateway: ответ heartbeat

|Описание|Полное сообщение клиента|
|-|-|
|Ответ на pig|`{"type":"pong","pigId":"pig-1"}`|

# API Gateway → Room Service

## REST

|Описание|Метод|Путь|Заголовки|Тело запроса|Код|Тело ответа|
|-|-|-|-|-|-|-|
|createRoom|POST|`/rooms`|`Content-Type: application/json`|`{"display\_name":"Alice","control\_mode":"host\_only"}`|201|`{"room\_id":"637c191e-49bf-453f-a335-5dc47b2ca6f8","invite\_code":"AbCdEf\_12345","invite\_link":"http://localhost:3000/rooms/AbCdEf\_12345","token":"alice-token","participant":{"display\_name":"Alice","role":"host","connected":true},"state":{"status":"active","control\_mode":"host\_only","state\_version":1,"current\_video\_id":null,"playback":{"video\_id":null,"position\_seconds":0,"is\_playing":false},"queue":\[],"participants":\[{"display\_name":"Alice","role":"host","connected":true}]}}`|
|joinRoom|POST|`/rooms/join`|`Content-Type: application/json`|`{"invite\_code":"AbCdEf\_12345","display\_name":"Bob"}`|201|`{"room\_id":"637c191e-49bf-453f-a335-5dc47b2ca6f8","invite\_code":"AbCdEf\_12345","invite\_link":"http://localhost:3000/rooms/AbCdEf\_12345","token":"bob-token","participant":{"display\_name":"Bob","role":"member","connected":true},"state":{"status":"active","control\_mode":"host\_only","state\_version":2,"current\_video\_id":null,"playback":{"video\_id":null,"position\_seconds":0,"is\_playing":false},"queue":\[],"participants":\[{"display\_name":"Alice","role":"host","connected":true},{"display\_name":"Bob","role":"member","connected":true}]}}`|
|playpause|POST|`/rooms/{room\_id}/commands`|`Authorization: Bearer alice-token`, `Content-Type: application/json`|`{"command\_id":"cmd-1","type":"playpause","payload":{}}`|200|`{"command\_id":"cmd-1","duplicate":false,"state":{"status":"active","control\_mode":"host\_only","state\_version":3,"current\_video\_id":"video-1","playback":{"video\_id":"video-1","position\_seconds":0,"is\_playing":true},"queue":\[{"id":"video-1","url":"https://rutube.ru/video/abc123/","position":0}],"participants":\[{"display\_name":"Alice","role":"host","connected":true}]}}`|
|nextVideo|POST|`/rooms/{room\_id}/commands`|`Authorization: Bearer alice-token`, `Content-Type: application/json`|`{"command\_id":"cmd-2","type":"next","payload":{}}`|200|`{"command\_id":"cmd-2","duplicate":false,"state":{"status":"active","control\_mode":"host\_only","state\_version":4,"current\_video\_id":null,"playback":{"video\_id":null,"position\_seconds":0,"is\_playing":false},"queue":\[{"id":"video-1","url":"https://rutube.ru/video/abc123/","position":0}],"participants":\[{"display\_name":"Alice","role":"host","connected":true}]}}`|
|seek|POST|`/rooms/{room\_id}/commands`|`Authorization: Bearer alice-token`, `Content-Type: application/json`|`{"command\_id":"cmd-3","type":"seek","payload":{"position\_seconds":30}}`|200|`{"command\_id":"cmd-3","duplicate":false,"state":{"status":"active","control\_mode":"host\_only","state\_version":4,"current\_video\_id":"video-1","playback":{"video\_id":"video-1","position\_seconds":30,"is\_playing":false},"queue":\[{"id":"video-1","url":"https://rutube.ru/video/abc123/","position":0}],"participants":\[{"display\_name":"Alice","role":"host","connected":true}]}}`|
|addVideo|POST|`/rooms/{room\_id}/commands`|`Authorization: Bearer alice-token`, `Content-Type: application/json`|`{"command\_id":"cmd-4","type":"add\_video","payload":{"url":"https://rutube.ru/video/abc123/"}}`|200|`{"command\_id":"cmd-4","duplicate":false,"state":{"status":"active","control\_mode":"host\_only","state\_version":2,"current\_video\_id":"video-1","playback":{"video\_id":"video-1","position\_seconds":0,"is\_playing":false},"queue":\[{"id":"video-1","url":"https://rutube.ru/video/abc123/","position":0}],"participants":\[{"display\_name":"Alice","role":"host","connected":true}]}}`|
|removeVideo|POST|`/rooms/{room\_id}/commands`|`Authorization: Bearer alice-token`, `Content-Type: application/json`|`{"command\_id":"cmd-5","type":"remove\_video","payload":{"video\_id":"video-1"}}`|200|`{"command\_id":"cmd-5","duplicate":false,"state":{"status":"active","control\_mode":"host\_only","state\_version":3,"current\_video\_id":null,"playback":{"video\_id":null,"position\_seconds":0,"is\_playing":false},"queue":\[],"participants":\[{"display\_name":"Alice","role":"host","connected":true}]}}`|
|leaveRoom|POST|`/rooms/{room\_id}/leave`|`Authorization: Bearer alice-token`|Нет|200|`{"left":true}`|
|getState|GET|`/rooms/{room\_id}`|`Authorization: Bearer alice-token`|Нет|200|`{"status":"active","control\_mode":"host\_only","state\_version":1,"current\_video\_id":null,"playback":{"video\_id":null,"position\_seconds":0,"is\_playing":false},"queue":\[],"participants":\[{"display\_name":"Alice","role":"host","connected":true}]}`|
|changeQueue|POST|`/rooms/{room\_id}/commands`|`Authorization: Bearer alice-token`, `Content-Type: application/json`|`{"command\_id":"cmd-9","type":"change\_queue","payload":{"video\_ids":\["video-2","video-1"]}}`|200|`{"command\_id":"cmd-9","duplicate":false,"state":{"status":"active","control\_mode":"host\_only","state\_version":5,"current\_video\_id":"video-1","playback":{"video\_id":"video-1","position\_seconds":0,"is\_playing":false},"queue":\[{"id":"video-2","url":"https://rutube.ru/video/def456/","position":0},{"id":"video-1","url":"https://rutube.ru/video/abc123/","position":1}],"participants":\[{"display\_name":"Alice","role":"host","connected":true}]}}`|
|setSettings|POST|`/rooms/{room\_id}/commands`|`Authorization: Bearer alice-token`, `Content-Type: application/json`|`{"command\_id":"cmd-11","type":"set\_control\_mode","payload":{"mode":"all"}}`|200|`{"command\_id":"cmd-11","duplicate":false,"state":{"status":"active","control\_mode":"all","state\_version":2,"current\_video\_id":null,"playback":{"video\_id":null,"position\_seconds":0,"is\_playing":false},"queue":\[],"participants":\[{"display\_name":"Alice","role":"host","connected":true}]}}`|

# API Gateway → Chat Service

## REST

|Описание|Метод|Путь|Заголовки|Тело запроса|Код|Тело ответа|
|-|-|-|-|-|-|-|
|sendMessage|POST|`/rooms/{room\_id}/messages`|`Authorization: Bearer alice-token`, `Content-Type: application/json`|`{"command\_id":"cmd-7","text":"Привет!"}`|200|`{"command\_id":"cmd-7","duplicate":false,"message":{"message\_id":"message-1","messageSeq":43,"participant\_id":"participant-1","text":"Привет!","created\_at":"2026-11-19T12:00:00Z"}}`|
|getChatSeq|GET|`/rooms/{room\_id}/messages/seq`|`Authorization: Bearer alice-token`|Нет|200|`{"messageSeq":43}`|

# Chat Service → Room Service

## REST

|Описание|Метод|Путь|Заголовки|Тело запроса|Код|Тело ответа|
|-|-|-|-|-|-|-|
|getRoom — проверка членства отправителя|GET|`/internal/rooms/{room\_id}/membership`|`Authorization: Bearer alice-token`|Нет|200|`{"room\_id":"637c191e-49bf-453f-a335-5dc47b2ca6f8","participant\_id":"participant-1","display\_name":"Alice","role":"host","connected":true}`|

# Ошибки и права

|HTTP|Код|Причина|
|-|-|-|
|401|unauthorized|Токен отсутствует или недействителен|
|403|wrong\_room|Токен другой комнаты|
|403|host\_only\_mode|Управление запрещено участнику в host\_only|
|403|host\_only\_command|setSettings доступен только ведущему|
|409|no\_current\_video|Управление без выбранного видео|
|409|room\_closed|Комната закрыта|
|409|command\_id\_conflict|Другие параметры с прежним ID|
|422|invalid\_video\_url|Некорректная ссылка Rutube|
|422|invalid\_payload|Неверные параметры; changeQueue содержит пропуски, дубли или чужие ID|

|Формат|Полное тело|
|-|-|
|HTTP-ошибка|`{"error":{"code":"wrong\_room","message":"Токен принадлежит другой комнате"}}`|
|WebSocket-ошибка|`{"type":"commandConfirm","commandId":"cmd-1","error":{"code":"host\_only\_mode","message":"Управление доступно только ведущему"}}`|

|Правило|Действие|
|-|-|
|host\_only|Воспроизведение и очередь меняет только host|
|all|Воспроизведение и очередь меняют host и member|
|setSettings|Всегда только host|
|Удаление текущего видео|Следующее на паузе; если следующего нет — current\_video\_id=null, playback.video\_id=null, position\_seconds=0, is\_playing=false|
|Выход ведущего|Немедленная передача роли самому раннему подключённому участнику|
|Потеря соединения ведущего|Передача роли после 10 секунд; восстановление отменяет ожидание|
|Чат|Автор определяется по токену; messageSeq задаёт порядок, дубли игнорируются|
|Таймаут команды /commands|Повтор с тем же command\_id; таймаут не доказывает, что действие не выполнено|



