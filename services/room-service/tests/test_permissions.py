from tests.helpers import add_video, command, create_room, join_room


async def test_host_only_mode_rejects_member_playback_and_queue(client):
    host = await create_room(client)
    room_id = host["room_id"]
    member = await join_room(client, host["invite_code"], name="Bob")

    await add_video(client, room_id, host["token"])

    denied = await command(
        client, room_id, member["token"], "playpause", expected_status=403
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

    allowed = await command(client, room_id, host["token"], "playpause")
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
    assert [video["id"] for video in added["state"]["queue"]] == [
        added["state"]["playback"]["video_id"]
    ]

    played = await command(client, room_id, member["token"], "playpause")
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


async def test_foreign_token_cannot_send_commands(client):
    host = await create_room(client)
    other = await create_room(client, name="Other")

    response = await client.post(
        f"/rooms/{host['room_id']}/commands",
        headers={"Authorization": f"Bearer {other['token']}"},
        json={"command_id": "cross-room", "type": "playpause", "payload": {}},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "wrong_room"


async def test_client_cannot_assign_role_or_participant_id(client):
    host = await create_room(client)
    response = await client.post(
        f"/rooms/{host['room_id']}/commands",
        headers={"Authorization": f"Bearer {host['token']}"},
        json={
            "command_id": "role-spoof",
            "type": "playpause",
            "payload": {},
            "participant_id": str(host["room_id"]),
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_payload"
