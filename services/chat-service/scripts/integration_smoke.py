#!/usr/bin/env python3
"""Check Chat -> Room -> Chat DB through HTTP, using only Python's stdlib.

Default mode uses CHAT_SMOKE_ROOM_ID and CHAT_SMOKE_TOKEN. --create-room creates
temporary integration rooms and closes only those rooms in finally.
No tokens, connection strings or message bodies are printed.
"""

import argparse
import http.client
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid


class CheckFailed(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def require(condition, message):
    if not condition:
        raise CheckFailed(message)


def base_url(value):
    parsed = urllib.parse.urlsplit(value)
    require(parsed.scheme in ("http", "https") and parsed.hostname and
            not parsed.username and not parsed.password and not parsed.query and
            not parsed.fragment, "Нужен HTTP(S)-адрес без токенов и паролей")
    return value.rstrip("/")


class API:
    def __init__(self, base, timeout):
        self.base = base_url(base)
        self.timeout = timeout
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, method, path, token=None, body=None, expected=200):
        data = None if body is None else json.dumps(body, ensure_ascii=False).encode()
        request = urllib.request.Request(self.base + path, data=data, method=method)
        request.add_header("X-Request-ID", "smoke-" + uuid.uuid4().hex)
        if token:
            request.add_header("Authorization", "Bearer " + token)
        if data is not None:
            request.add_header("Content-Type", "application/json")
        try:
            response = self.opener.open(request, timeout=self.timeout)
        except urllib.error.HTTPError as error:
            response = error
        except (OSError, urllib.error.URLError):
            raise CheckFailed(f"{method} {path}: ошибка соединения или таймаут") from None
        try:
            with response:
                raw = response.read(1024 * 1024 + 1)
                require(len(raw) <= 1024 * 1024, "Слишком большой ответ")
                try:
                    result = json.loads(raw)
                except (ValueError, UnicodeError):
                    result = None
                status = response.status
        except (OSError, http.client.HTTPException):
            raise CheckFailed(f"{method} {path}: ошибка чтения ответа") from None
        if status != expected:
            code = "unknown"
            if isinstance(result, dict) and isinstance(result.get("error"), dict):
                code = result["error"].get("code", "unknown")
            # Never print arbitrary upstream strings, which might contain secrets.
            known = {"unauthorized", "wrong_room", "room_closed", "command_id_conflict",
                     "invalid_payload", "room_service_unavailable", "room_service_timeout",
                     "storage_unavailable", "request_timeout", "not_found"}
            code = code if code in known else "unknown"
            raise CheckFailed(f"{method} {path}: ожидался HTTP {expected}, получен {status}, code={code}")
        return result, raw


def error_code(result, wanted):
    require(isinstance(result, dict) and isinstance(result.get("error"), dict) and
            result["error"].get("code") == wanted, f"Ожидалась JSON-ошибка {wanted}")


def check_message(result, command_id, text, participant_id):
    require(isinstance(result, dict) and set(result) == {"command_id", "duplicate", "message"},
            "Ответ отправки не соответствует контракту")
    require(result["command_id"] == command_id and type(result["duplicate"]) is bool,
            "Некорректные command_id или duplicate")
    message = result["message"]
    require(isinstance(message, dict) and set(message) == {
        "message_id", "messageSeq", "participant_id", "text", "created_at"},
        "Неверные поля message (в частности, token и room_id не должны рассылаться)")
    require(message["participant_id"] == participant_id and message["text"] == text,
            "Автор или текст сообщения не совпали")
    require(isinstance(message["message_id"], str) and message["message_id"] and
            type(message["messageSeq"]) is int and message["messageSeq"] > 0,
            "Некорректные ID или messageSeq")
    require(isinstance(message["created_at"], str) and message["created_at"].endswith("Z"),
            "created_at должен содержать время UTC")
    return message


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chat-url", default=os.getenv("CHAT_URL", "http://127.0.0.1:6767"))
    parser.add_argument("--room-url", default=os.getenv("ROOM_SERVICE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--timeout", type=float, default=10)
    parser.add_argument("--create-room", action="store_true", help="создать и затем закрыть временные комнаты")
    args = parser.parse_args()
    require(args.timeout > 0, "Таймаут должен быть положительным")
    chat = API(args.chat_url, args.timeout)
    room = API(args.room_url, args.timeout)
    created = []
    try:
        _, health = chat.request("GET", "/health")
        require(health == b"i'm still standing\n", "Неожиданный ответ Chat /health")
        ready, _ = chat.request("GET", "/ready")
        require(isinstance(ready, dict) and ready.get("status") == "ok", "Chat Service не готов")
        print("PASS: живость сервиса, готовность Chat DB и доступность Room Service")

        def create_room(name):
            response, _ = room.request("POST", "/rooms", body={"display_name": name, "control_mode": "host_only"}, expected=201)
            require(isinstance(response, dict) and response.get("room_id") and response.get("token"),
                    "Создание комнаты: отсутствуют room_id или token")
            created.append((response["room_id"], response["token"]))
            return response

        if args.create_room:
            first = create_room("Chat integration host")
            room_id, token = first["room_id"], first["token"]
        else:
            room_id, token = os.getenv("CHAT_SMOKE_ROOM_ID"), os.getenv("CHAT_SMOKE_TOKEN")
            require(room_id and token, "Задай CHAT_SMOKE_ROOM_ID и CHAT_SMOKE_TOKEN или используй --create-room")
        path = "/rooms/" + urllib.parse.quote(room_id, safe="") + "/messages"
        membership, _ = room.request("GET", "/internal/rooms/" + urllib.parse.quote(room_id, safe="") + "/membership", token)
        require(isinstance(membership, dict) and membership.get("room_id") == room_id and
                membership.get("participant_id"), "Membership не соответствует контракту")
        seq, _ = chat.request("GET", path + "/seq", token)
        require(isinstance(seq, dict) and type(seq.get("messageSeq")) is int, "Нет целого messageSeq")
        initial = seq["messageSeq"]
        text = "Интеграция чата: кириллица, emoji 🎬 и <b>обычный текст</b>"
        command_id = "smoke-" + uuid.uuid4().hex
        body = {"command_id": command_id, "text": text}
        response, _ = chat.request("POST", path, token, body)
        message = check_message(response, command_id, text, membership["participant_id"])
        require(response["duplicate"] is False and message["messageSeq"] > initial, "Новое сообщение не создано")
        print("PASS: отправка текста, автор из Room Service, формат и рост messageSeq")
        retry, _ = chat.request("POST", path, token, body)
        require(retry.get("duplicate") is True and retry.get("message") == message,
                "Повтор создал другое сообщение")
        conflict, _ = chat.request("POST", path, token, {"command_id": command_id, "text": text + "!"}, expected=409)
        error_code(conflict, "command_id_conflict")
        current, _ = chat.request("GET", path + "/seq", token)
        require(current["messageSeq"] >= message["messageSeq"], "Счётчик меньше сохранённого номера")
        if args.create_room:
            require(current["messageSeq"] == message["messageSeq"], "Повтор или конфликт увеличил счётчик")
        print("PASS: повтор возвращает прежнее сообщение, конфликт параметров отклоняется")

        for method, endpoint, payload in [("GET", path + "/seq", None), ("POST", path, body)]:
            for bad_token in (None, "invalid-" + uuid.uuid4().hex):
                response, _ = chat.request(method, endpoint, bad_token, payload, expected=401)
                error_code(response, "unauthorized")
        invalid, _ = chat.request("POST", path, token, {"command_id": "smoke-" + uuid.uuid4().hex, "text": "   "}, expected=422)
        error_code(invalid, "invalid_payload")
        print("PASS: нет доступа без сессии; пустое сообщение отклоняется")

        if args.create_room:
            joined, _ = room.request("POST", "/rooms/join", body={"invite_code": first["invite_code"], "display_name": "Chat integration member"}, expected=201)
            member_token = joined["token"]
            member, _ = room.request("GET", "/internal/rooms/" + urllib.parse.quote(room_id, safe="") + "/membership", member_token)
            next_id = "smoke-" + uuid.uuid4().hex
            other, _ = chat.request("POST", path, member_token, {"command_id": next_id, "text": "Сообщение участника"})
            member_message = check_message(other, next_id, "Сообщение участника", member["participant_id"])
            require(member_message["messageSeq"] == message["messageSeq"] + 1, "У участников нет общего счётчика")
            second = create_room("Other integration room")
            for method, endpoint, payload in [("GET", path + "/seq", None), ("POST", path, body)]:
                response, _ = chat.request(method, endpoint, second["token"], payload, expected=403)
                error_code(response, "wrong_room")
            room.request("POST", "/rooms/" + urllib.parse.quote(room_id, safe="") + "/commands", token,
                         {"command_id": "close-" + uuid.uuid4().hex, "type": "close_room", "payload": {}})
            for method, endpoint, payload in [("GET", path + "/seq", None), ("POST", path, body)]:
                response, _ = chat.request(method, endpoint, token, payload, expected=409)
                error_code(response, "room_closed")
            created.remove((room_id, token))
            print("PASS: второй участник, чужая комната, закрытие комнаты")
        print("OK: HTTP-интеграция Chat Service проверена. WebSocket Gateway проверяется отдельно.")
        return 0
    finally:
        for room_id, token in created:
            try:
                room.request("POST", "/rooms/" + urllib.parse.quote(room_id, safe="") + "/commands", token,
                             {"command_id": "cleanup-" + uuid.uuid4().hex, "type": "close_room", "payload": {}})
            except CheckFailed:
                print("WARN: не удалось закрыть одну из созданных тестовых комнат", file=sys.stderr)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (CheckFailed, KeyError, TypeError, ValueError, AttributeError) as error:
        message = str(error) if isinstance(error, CheckFailed) else "Ответ не соответствует согласованной схеме"
        print("FAIL:", message, file=sys.stderr)
        sys.exit(1)
