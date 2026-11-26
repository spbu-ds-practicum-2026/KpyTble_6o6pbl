import asyncio
import uuid
from collections.abc import Callable
from typing import Any

SAMPLE_VIDEO = "https://rutube.ru/video/abc123def456/"

STATE_KEYS = {
    "status",
    "control_mode",
    "state_version",
    "current_video_id",
    "playback",
    "queue",
    "participants",
}
PLAYBACK_KEYS = {"video_id", "position_seconds", "is_playing"}
VIDEO_KEYS = {"id", "url", "position"}
PARTICIPANT_KEYS = {"display_name", "role", "connected"}


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def assert_state_shape(state: dict[str, Any]) -> None:
    assert set(state) == STATE_KEYS
    assert set(state["playback"]) == PLAYBACK_KEYS
    assert state["current_video_id"] == state["playback"]["video_id"]
    for video in state["queue"]:
        assert set(video) == VIDEO_KEYS
    for participant in state["participants"]:
        assert set(participant) == PARTICIPANT_KEYS


def event_shape(event: dict[str, Any]) -> None:
    assert set(event) == {"type", "room_id", "state_version", "reason", "state"}
    assert event["type"] == "room_state_changed"
    assert_state_shape(event["state"])


async def create_room(
    client, name: str = "Host", control_mode: str = "host_only"
) -> dict[str, Any]:
    body = {"display_name": name, "control_mode": control_mode}
    response = await client.post("/rooms", json=body)
    assert response.status_code == 201, response.text
    data = response.json()
    assert set(data) == {
        "room_id",
        "invite_code",
        "invite_link",
        "token",
        "participant",
        "state",
    }
    assert set(data["participant"]) == PARTICIPANT_KEYS
    assert_state_shape(data["state"])
    return data


async def join_room(client, invite_code: str, name: str = "Member") -> dict[str, Any]:
    response = await client.post(
        "/rooms/join", json={"invite_code": invite_code, "display_name": name}
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert set(data) == {
        "room_id",
        "invite_code",
        "invite_link",
        "token",
        "participant",
        "state",
    }
    assert set(data["participant"]) == PARTICIPANT_KEYS
    assert_state_shape(data["state"])
    return data


async def get_state(client, room_id: str, token: str) -> dict[str, Any]:
    response = await client.get(f"/rooms/{room_id}", headers=auth(token))
    assert response.status_code == 200, response.text
    state = response.json()
    assert_state_shape(state)
    return state


async def command(
    client,
    room_id: str,
    token: str,
    command_type: str,
    payload: dict[str, Any] | None = None,
    command_id: str | None = None,
    expected_status: int = 200,
) -> dict[str, Any]:
    response = await client.post(
        f"/rooms/{room_id}/commands",
        headers=auth(token),
        json={
            "command_id": command_id or str(uuid.uuid4()),
            "type": command_type,
            "payload": payload or {},
        },
    )
    assert response.status_code == expected_status, response.text
    data = response.json()
    if expected_status == 200:
        assert set(data) == {"command_id", "duplicate", "state"}
        assert_state_shape(data["state"])
    return data


async def add_video(
    client, room_id: str, token: str, url: str = SAMPLE_VIDEO
) -> dict[str, Any]:
    return await command(client, room_id, token, "add_video", {"url": url})


async def wait_until(
    predicate: Callable[[], Any],
    *,
    timeout: float = 2.0,
    interval: float = 0.02,
) -> Any:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while True:
        result = await predicate()
        if result:
            return result
        if loop.time() >= deadline:
            raise AssertionError("condition was not met within timeout")
        await asyncio.sleep(interval)
