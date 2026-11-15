import asyncio
import uuid
from collections.abc import Callable
from typing import Any

SAMPLE_VIDEO = "https://rutube.ru/video/abc123def456/"


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def create_room(
    client, name: str = "Host", control_mode: str | None = None
) -> dict[str, Any]:
    body: dict[str, Any] = {"display_name": name}
    if control_mode is not None:
        body["control_mode"] = control_mode
    response = await client.post("/rooms", json=body)
    assert response.status_code == 201, response.text
    return response.json()


async def join_room(client, invite_code: str, name: str = "Member") -> dict[str, Any]:
    response = await client.post(
        "/rooms/join",
        json={"invite_code": invite_code, "display_name": name},
    )
    assert response.status_code == 200, response.text
    return response.json()


async def get_state(client, room_id: str, token: str) -> dict[str, Any]:
    response = await client.get(f"/rooms/{room_id}", headers=auth(token))
    assert response.status_code == 200, response.text
    return response.json()


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
    return response.json()


async def add_video(
    client,
    room_id: str,
    token: str,
    url: str = SAMPLE_VIDEO,
    title: str | None = None,
) -> dict[str, Any]:
    return await command(
        client,
        room_id,
        token,
        "add_video",
        {"url": url, "title": title},
    )


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
