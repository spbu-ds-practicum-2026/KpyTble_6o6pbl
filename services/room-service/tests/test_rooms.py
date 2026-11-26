from tests.helpers import auth, create_room, get_state, join_room


async def test_create_room_returns_host_session_and_state(client):
    data = await create_room(client, name="Alice")

    assert data["token"]
    assert data["invite_code"]
    assert data["invite_link"].endswith(data["invite_code"])
    assert data["participant"] == {
        "display_name": "Alice",
        "role": "host",
        "connected": True,
    }

    state = data["state"]
    assert state["status"] == "active"
    assert state["control_mode"] == "host_only"
    assert state["state_version"] == 1
    assert state["current_video_id"] is None
    assert state["queue"] == []
    assert state["participants"] == [
        {"display_name": "Alice", "role": "host", "connected": True}
    ]
    assert state["playback"] == {
        "video_id": None,
        "position_seconds": 0,
        "is_playing": False,
    }


async def test_join_room_by_code(client):
    host = await create_room(client)
    room_id = host["room_id"]

    member = await join_room(client, host["invite_code"], name="Bob")
    assert member["participant"] == {
        "display_name": "Bob",
        "role": "member",
        "connected": True,
    }
    state = await get_state(client, room_id, member["token"])
    assert {p["display_name"] for p in state["participants"]} == {"Host", "Bob"}
    assert state["state_version"] == 2

    third = await join_room(client, host["invite_code"], name="Carol")
    state = await get_state(client, room_id, third["token"])
    assert {p["display_name"] for p in state["participants"]} == {
        "Host",
        "Bob",
        "Carol",
    }
    assert state["state_version"] == 3
    assert third["invite_code"] == host["invite_code"]


async def test_get_state_does_not_bump_version_or_emit_event(client, event_log):
    host = await create_room(client)
    before = len(event_log.events)

    first = await get_state(client, host["room_id"], host["token"])
    second = await get_state(client, host["room_id"], host["token"])

    assert first["state_version"] == second["state_version"]
    assert len(event_log.events) == before


async def test_state_requires_valid_membership(client):
    host = await create_room(client)
    other = await create_room(client, name="Other")

    missing = await client.get(f"/rooms/{host['room_id']}")
    assert missing.status_code == 401
    assert missing.json()["error"]["code"] == "unauthorized"

    invalid = await client.get(
        f"/rooms/{host['room_id']}", headers=auth("not-a-real-token")
    )
    assert invalid.status_code == 401

    wrong_room = await client.get(
        f"/rooms/{host['room_id']}", headers=auth(other["token"])
    )
    assert wrong_room.status_code == 403
    assert wrong_room.json() == {
        "error": {
            "code": "wrong_room",
            "message": "Токен принадлежит другой комнате",
        }
    }

    member = await join_room(client, host["invite_code"], name="Bob")
    left = await client.post(
        f"/rooms/{host['room_id']}/leave", headers=auth(member["token"])
    )
    assert left.status_code == 200
    left_token = await client.get(
        f"/rooms/{host['room_id']}", headers=auth(member["token"])
    )
    assert left_token.status_code == 401
    assert left_token.json()["error"]["code"] == "unauthorized"


async def test_join_validation(client):
    unknown = await client.post(
        "/rooms/join",
        json={"invite_code": "missing-code", "display_name": "Bob"},
    )
    assert unknown.status_code == 422
    assert unknown.json()["error"]["code"] == "invalid_payload"

    bad_link = await client.post(
        "/rooms/join",
        json={"invite_code": "ftp://example.com/rooms/abc", "display_name": "Bob"},
    )
    assert bad_link.status_code == 422
    assert bad_link.json()["error"]["code"] == "invalid_payload"

    blank_name = await client.post(
        "/rooms", json={"display_name": "   ", "control_mode": "all"}
    )
    assert blank_name.status_code == 422
    assert blank_name.json()["error"]["code"] == "invalid_payload"

    extra_field = await client.post(
        "/rooms", json={"display_name": "Alice", "role": "host"}
    )
    assert extra_field.status_code == 422
    assert extra_field.json()["error"]["code"] == "invalid_payload"


async def test_internal_membership_endpoint(client):
    host = await create_room(client)
    member = await join_room(client, host["invite_code"], name="Bob")
    other = await create_room(client, name="Other")

    for token, display_name, role in (
        (host["token"], "Host", "host"),
        (member["token"], "Bob", "member"),
    ):
        response = await client.get(
            f"/internal/rooms/{host['room_id']}/membership",
            headers=auth(token),
        )
        assert response.status_code == 200
        body = response.json()
        assert set(body) == {
            "room_id",
            "participant_id",
            "display_name",
            "role",
            "connected",
        }
        assert body["room_id"] == host["room_id"]
        assert body["display_name"] == display_name
        assert body["role"] == role
        assert body["connected"] is True
        assert "is_member" not in body

    denied_shape = {"is_member": False, "room_id": host["room_id"]}

    response = await client.get(f"/internal/rooms/{host['room_id']}/membership")
    assert response.json() == denied_shape

    response = await client.get(
        f"/internal/rooms/{other['room_id']}/membership",
        headers=auth(member["token"]),
    )
    assert response.json() == {"is_member": False, "room_id": other["room_id"]}

    await client.post(f"/rooms/{host['room_id']}/leave", headers=auth(member["token"]))
    response = await client.get(
        f"/internal/rooms/{host['room_id']}/membership",
        headers=auth(member["token"]),
    )
    assert response.json() == denied_shape


async def test_only_contract_authorization_and_bodies(client):
    host = await create_room(client)

    fallback = await client.get(
        f"/rooms/{host['room_id']}", headers={"X-Session-Token": host["token"]}
    )
    assert fallback.status_code == 401
    assert fallback.json()["error"]["code"] == "unauthorized"

    missing_mode = await client.post("/rooms", json={"display_name": "No mode"})
    assert missing_mode.status_code == 422
    assert missing_mode.json()["error"]["code"] == "invalid_payload"

    link_join = await client.post(
        "/rooms/join",
        json={
            "invite_link": f"http://localhost:3000/rooms/{host['invite_code']}",
            "display_name": "Bob",
        },
    )
    assert link_join.status_code == 422
    assert link_join.json()["error"]["code"] == "invalid_payload"

    missing_payload = await client.post(
        f"/rooms/{host['room_id']}/commands",
        headers=auth(host["token"]),
        json={"command_id": "no-payload", "type": "playpause"},
    )
    assert missing_payload.status_code == 422
    assert missing_payload.json()["error"]["code"] == "invalid_payload"
