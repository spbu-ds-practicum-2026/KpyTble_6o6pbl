from tests.helpers import add_video, command, create_room, join_room


async def test_host_only_mode_rejects_member_playback_and_queue(client):
    host = await create_room(client)
    room_id = host["room_id"]
    member = await join_room(client, host["invite_code"], name="Bob")

    await add_video(client, room_id, host["token"])

    denied = await command(
        client,
        room_id,
        member["token"],
        "play",
        expected_status=403,
    )
    assert denied["error"]["code"] == "host_only_mode"

    denied = await command(
        client,
        room_id,
        member["token"],
        "add_video",
        {"url": "https://rutube.ru/video/member/"},
        expected_status=403,
    )
    assert denied["error"]["code"] == "host_only_mode"

    allowed = await command(client, room_id, host["token"], "play")
    assert allowed["duplicate"] is False


async def test_all_mode_allows_member_control_but_not_room_settings(client):
    host = await create_room(client, control_mode="host_only")
    room_id = host["room_id"]
    member = await join_room(client, host["invite_code"], name="Bob")

    switched = await command(
        client,
        room_id,
        host["token"],
        "set_control_mode",
        {"mode": "all"},
    )
    assert switched["state"]["control_mode"] == "all"

    added = await add_video(
        client,
        room_id,
        member["token"],
        "https://rutube.ru/video/member/",
    )
    assert len(added["state"]["queue"]) == 1

    played = await command(client, room_id, member["token"], "play")
    assert played["state"]["playback"]["is_playing"] is True

    denied = await command(
        client,
        room_id,
        member["token"],
        "set_control_mode",
        {"mode": "host_only"},
        expected_status=403,
    )
    assert denied["error"]["code"] == "host_only_command"


async def test_only_host_can_close_room(client):
    host = await create_room(client, control_mode="all")
    room_id = host["room_id"]
    member = await join_room(client, host["invite_code"], name="Bob")

    denied = await command(
        client,
        room_id,
        member["token"],
        "close_room",
        expected_status=403,
    )
    assert denied["error"]["code"] == "host_only_command"

    closed = await command(client, room_id, host["token"], "close_room")
    assert closed["state"]["status"] == "closed"


async def test_foreign_token_cannot_send_commands(client):
    host = await create_room(client)
    other = await create_room(client, name="Other")

    response = await client.post(
        f"/rooms/{host['room_id']}/commands",
        headers={"Authorization": f"Bearer {other['token']}"},
        json={"command_id": "cross-room", "type": "play", "payload": {}},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "wrong_room"
