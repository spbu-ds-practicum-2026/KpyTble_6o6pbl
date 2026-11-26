from tests.helpers import add_video, command, create_room, get_state, join_room


async def test_closed_room_rejects_new_commands_and_joins(client, event_log):
    host = await create_room(client)
    room_id = host["room_id"]
    token = host["token"]
    member = await join_room(client, host["invite_code"], name="Bob")

    await add_video(client, room_id, token)
    await command(client, room_id, token, "playpause")
    before_close = await get_state(client, room_id, token)

    command_id = "seek-before-close"
    payload = {"position_seconds": 5}
    saved = await command(
        client, room_id, token, "seek", payload, command_id=command_id
    )

    member_left = await client.post(
        f"/rooms/{room_id}/leave",
        headers={"Authorization": f"Bearer {member['token']}"},
    )
    assert member_left.status_code == 200
    host_left = await client.post(
        f"/rooms/{room_id}/leave", headers={"Authorization": f"Bearer {token}"}
    )
    assert host_left.status_code == 200

    closed_state = event_log.events[-1]["state"]
    assert event_log.events[-1]["reason"] == "room_closed"
    assert closed_state["status"] == "closed"
    assert closed_state["playback"]["is_playing"] is False
    assert closed_state["state_version"] > before_close["state_version"]

    denied = await command(client, room_id, token, "playpause", expected_status=409)
    assert denied["error"]["code"] == "room_closed"

    denied = await command(
        client, room_id, member["token"], "playpause", expected_status=409
    )
    assert denied["error"]["code"] == "room_closed"

    duplicate = await command(
        client, room_id, token, "seek", payload, command_id=command_id
    )
    assert duplicate["duplicate"] is True
    assert duplicate["state"] == saved["state"]

    response = await client.post(
        "/rooms/join",
        json={"invite_code": host["invite_code"], "display_name": "Late"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "room_closed"


async def test_room_closes_when_last_participant_leaves(client, event_log):
    host = await create_room(client)
    room_id = host["room_id"]
    member = await join_room(client, host["invite_code"], name="Bob")

    first_leave = await client.post(
        f"/rooms/{room_id}/leave",
        headers={"Authorization": f"Bearer {member['token']}"},
    )
    assert first_leave.status_code == 200
    assert first_leave.json() == {"left": True}

    again = await client.post(
        f"/rooms/{room_id}/leave",
        headers={"Authorization": f"Bearer {member['token']}"},
    )
    assert again.status_code == 401
    assert again.json()["error"]["code"] == "unauthorized"

    active = await get_state(client, room_id, host["token"])
    assert active["status"] == "active"
    assert [p["display_name"] for p in active["participants"]] == ["Host"]

    last_leave = await client.post(
        f"/rooms/{room_id}/leave",
        headers={"Authorization": f"Bearer {host['token']}"},
    )
    assert last_leave.status_code == 200
    assert last_leave.json() == {"left": True}

    reasons = [event["reason"] for event in event_log.events]
    assert reasons[-1] == "room_closed"

    closed = event_log.events[-1]["state"]
    assert closed["status"] == "closed"
    assert closed["status"] != "active"
    assert closed["participants"] == []
    assert closed["state_version"] == active["state_version"] + 1

    denied = await command(
        client, room_id, host["token"], "playpause", expected_status=409
    )
    assert denied["error"]["code"] == "room_closed"

    response = await client.post(
        "/rooms/join",
        json={"invite_code": host["invite_code"], "display_name": "Late"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "room_closed"
