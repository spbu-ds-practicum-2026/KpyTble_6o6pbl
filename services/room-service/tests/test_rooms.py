import uuid

from tests.helpers import auth, create_room, get_state, join_room


async def test_create_room_returns_host_session_and_state(client):
    data = await create_room(client, name="Alice")

    assert data["token"]
    assert data["invite_code"]
    assert data["invite_link"].endswith(data["invite_code"])
    assert data["participant"]["role"] == "host"
    assert data["participant"]["connected"] is True

    state = data["state"]
    assert state["room_id"] == data["room_id"]
    assert state["status"] == "active"
    assert state["control_mode"] == "host_only"
    assert state["state_version"] == 1
    assert state["current_video_id"] is None
    assert state["queue"] == []
    assert len(state["participants"]) == 1
    assert state["participants"][0]["role"] == "host"
    assert state["playback"]["is_playing"] is False
    assert state["playback"]["position_seconds"] == 0.0


async def test_join_room_adds_member_and_updates_version(client):
    host = await create_room(client)
    room_id = host["room_id"]

    member = await join_room(client, host["invite_code"], name="Bob")

    assert member["participant"]["role"] == "member"
    state = await get_state(client, room_id, member["token"])
    assert {p["display_name"] for p in state["participants"]} == {"Host", "Bob"}
    assert state["state_version"] == 2

    third = await join_room(client, host["invite_code"], name="Carol")
    state = await get_state(client, room_id, third["token"])
    assert len(state["participants"]) == 3
    assert state["state_version"] == 3


async def test_get_state_does_not_bump_version(client):
    host = await create_room(client)
    first = await get_state(client, host["room_id"], host["token"])
    second = await get_state(client, host["room_id"], host["token"])

    assert first["state_version"] == second["state_version"]


async def test_state_requires_valid_membership(client):
    host = await create_room(client)
    other = await create_room(client, name="Other")

    missing = await client.get(f"/rooms/{host['room_id']}")
    assert missing.status_code == 401

    invalid = await client.get(
        f"/rooms/{host['room_id']}", headers=auth("not-a-real-token")
    )
    assert invalid.status_code == 401

    wrong_room = await client.get(
        f"/rooms/{host['room_id']}", headers=auth(other["token"])
    )
    assert wrong_room.status_code == 403


async def test_join_unknown_room_returns_404(client):
    response = await client.post(
        "/rooms/join",
        json={"invite_code": "missing-code", "display_name": "Bob"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "room_not_found"


async def test_internal_membership_endpoint(client):
    host = await create_room(client)
    member = await join_room(client, host["invite_code"], name="Bob")
    other = await create_room(client, name="Other")

    response = await client.get(
        f"/internal/rooms/{host['room_id']}/membership",
        headers=auth(host["token"]),
    )
    assert response.status_code == 200
    assert response.json()["is_member"] is True
    assert response.json()["role"] == "host"

    response = await client.get(
        f"/internal/rooms/{host['room_id']}/membership",
        headers=auth(member["token"]),
    )
    assert response.json()["is_member"] is True
    assert response.json()["role"] == "member"

    response = await client.get(f"/internal/rooms/{host['room_id']}/membership")
    assert response.json()["is_member"] is False

    response = await client.get(
        f"/internal/rooms/{other['room_id']}/membership",
        headers=auth(member["token"]),
    )
    assert response.json()["is_member"] is False

    response = await client.get(
        f"/internal/rooms/{uuid.UUID(int=0)}/membership",
        headers=auth(member["token"]),
    )
    assert response.json()["is_member"] is False
