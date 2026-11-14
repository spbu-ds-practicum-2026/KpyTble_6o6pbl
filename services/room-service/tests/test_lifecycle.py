from tests.helpers import add_video, command, create_room, get_state, join_room


async def test_closed_room_rejects_new_commands_and_joins(client):
    host = await create_room(client)
    room_id = host["room_id"]
    token = host["token"]
    member = await join_room(client, host["invite_code"], name="Bob")

    await add_video(client, room_id, token)
    await command(client, room_id, token, "play")
    before_close = await get_state(client, room_id, token)

    command_id = "close-room-1"
    closed = await command(client, room_id, token, "close_room", command_id=command_id)
    assert closed["state"]["status"] == "closed"
    assert closed["state"]["playback"]["is_playing"] is False
    assert closed["state"]["state_version"] == before_close["state_version"] + 1

    denied = await command(
        client,
        room_id,
        token,
        "play",
        expected_status=409,
    )
    assert denied["error"]["code"] == "room_closed"

    denied = await command(
        client,
        room_id,
        member["token"],
        "pause",
        expected_status=409,
    )
    assert denied["error"]["code"] == "room_closed"

    duplicate = await command(
        client, room_id, token, "close_room", command_id=command_id
    )
    assert duplicate["duplicate"] is True

    response = await client.post(
        "/rooms/join",
        json={"invite_code": host["invite_code"], "display_name": "Late"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "room_closed"

    state = await get_state(client, room_id, member["token"])
    assert state["status"] == "closed"
