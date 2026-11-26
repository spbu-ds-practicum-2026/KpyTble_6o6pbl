from tests.helpers import add_video, command, create_room, get_state


async def test_repeated_next_does_not_switch_video_twice(client):
    host = await create_room(client)
    room_id = host["room_id"]
    token = host["token"]

    await add_video(client, room_id, token, "https://rutube.ru/video/one/")
    await add_video(client, room_id, token, "https://rutube.ru/video/two/")
    await add_video(client, room_id, token, "https://rutube.ru/video/three/")

    command_id = "next-command-1"
    first = await command(client, room_id, token, "next", command_id=command_id)
    assert first["duplicate"] is False
    expected_video = first["state"]["playback"]["video_id"]
    expected_version = first["state"]["state_version"]

    second = await command(client, room_id, token, "next", command_id=command_id)
    assert second["duplicate"] is True
    assert second["state"]["playback"]["video_id"] == expected_video
    assert second["state"]["state_version"] == expected_version

    state = await get_state(client, room_id, token)
    assert state["playback"]["video_id"] == expected_video
    assert state["state_version"] == expected_version


async def test_repeated_add_video_creates_one_queue_item(client):
    host = await create_room(client)
    room_id = host["room_id"]
    token = host["token"]
    payload = {"url": "https://rutube.ru/video/same/"}
    command_id = "add-command-1"

    first = await command(
        client, room_id, token, "add_video", payload, command_id=command_id
    )
    assert first["duplicate"] is False
    assert len(first["state"]["queue"]) == 1
    expected_version = first["state"]["state_version"]

    second = await command(
        client, room_id, token, "add_video", payload, command_id=command_id
    )
    assert second["duplicate"] is True

    state = await get_state(client, room_id, token)
    assert len(state["queue"]) == 1
    assert state["state_version"] == expected_version


async def test_same_command_id_with_different_parameters_is_rejected(client):
    host = await create_room(client)
    room_id = host["room_id"]
    token = host["token"]
    command_id = "shared-command"

    await add_video(client, room_id, token)
    await command(client, room_id, token, "playpause", command_id=command_id)

    conflict = await command(
        client,
        room_id,
        token,
        "seek",
        {"position_seconds": 5},
        command_id=command_id,
        expected_status=409,
    )
    assert conflict["error"]["code"] == "command_id_conflict"


async def test_repeated_playpause_toggles_only_once(client):
    host = await create_room(client)
    room_id = host["room_id"]
    token = host["token"]
    await add_video(client, room_id, token)

    command_id = "playpause-command-1"
    first = await command(client, room_id, token, "playpause", command_id=command_id)
    second = await command(client, room_id, token, "playpause", command_id=command_id)

    assert first["duplicate"] is False
    assert second["duplicate"] is True
    assert second["state"]["state_version"] == first["state"]["state_version"]
    assert second["state"]["playback"]["is_playing"] is True

    state = await get_state(client, room_id, token)
    assert state["state_version"] == first["state"]["state_version"]


async def test_repeated_seek_is_idempotent(client):
    host = await create_room(client)
    room_id = host["room_id"]
    token = host["token"]
    await add_video(client, room_id, token)

    command_id = "seek-command-1"
    payload = {"position_seconds": 42}
    first = await command(
        client, room_id, token, "seek", payload, command_id=command_id
    )
    second = await command(
        client, room_id, token, "seek", payload, command_id=command_id
    )

    assert first["duplicate"] is False
    assert second["duplicate"] is True
    assert second["state"]["state_version"] == first["state"]["state_version"]
    assert second["state"]["playback"]["position_seconds"] == 42.0


async def test_repeated_remove_video_is_idempotent(client):
    host = await create_room(client)
    room_id = host["room_id"]
    token = host["token"]

    await add_video(client, room_id, token, "https://rutube.ru/video/a/")
    second_add = await add_video(client, room_id, token, "https://rutube.ru/video/b/")
    current_id = second_add["state"]["playback"]["video_id"]
    upcoming_id = second_add["state"]["queue"][1]["id"]

    command_id = "remove-command-1"
    payload = {"video_id": current_id}
    first = await command(
        client, room_id, token, "remove_video", payload, command_id=command_id
    )
    second = await command(
        client, room_id, token, "remove_video", payload, command_id=command_id
    )

    assert first["duplicate"] is False
    assert second["duplicate"] is True
    assert second["state"]["state_version"] == first["state"]["state_version"]
    assert second["state"]["playback"]["video_id"] == upcoming_id
    assert [video["id"] for video in second["state"]["queue"]] == [upcoming_id]


async def test_repeated_change_queue_is_idempotent(client):
    host = await create_room(client)
    room_id = host["room_id"]
    token = host["token"]

    await add_video(client, room_id, token, "https://rutube.ru/video/a/")
    await add_video(client, room_id, token, "https://rutube.ru/video/b/")
    await add_video(client, room_id, token, "https://rutube.ru/video/c/")
    last = await add_video(client, room_id, token, "https://rutube.ru/video/d/")
    ids = [video["id"] for video in last["state"]["queue"]]

    command_id = "change-command-1"
    payload = {"video_ids": [ids[2], ids[0], ids[1], ids[3]]}
    first = await command(
        client, room_id, token, "change_queue", payload, command_id=command_id
    )
    second = await command(
        client, room_id, token, "change_queue", payload, command_id=command_id
    )

    assert first["duplicate"] is False
    assert second["duplicate"] is True
    assert second["state"]["state_version"] == first["state"]["state_version"]
    assert [video["id"] for video in second["state"]["queue"]] == [
        ids[2],
        ids[0],
        ids[1],
        ids[3],
    ]


async def test_repeated_set_control_mode_is_idempotent(client):
    host = await create_room(client)
    command_id = "mode-command-1"

    first = await command(
        client,
        host["room_id"],
        host["token"],
        "set_control_mode",
        {"mode": "all"},
        command_id=command_id,
    )
    second = await command(
        client,
        host["room_id"],
        host["token"],
        "set_control_mode",
        {"mode": "all"},
        command_id=command_id,
    )

    assert first["duplicate"] is False
    assert second["duplicate"] is True
    assert second["state"]["state_version"] == first["state"]["state_version"]
    assert second["state"]["control_mode"] == "all"


async def test_repeated_command_after_close_returns_saved_confirmation(
    client, event_log
):
    host = await create_room(client)
    room_id = host["room_id"]
    token = host["token"]
    await add_video(client, room_id, token)

    command_id = "play-before-close"
    first = await command(client, room_id, token, "playpause", command_id=command_id)

    left = await client.post(
        f"/rooms/{room_id}/leave", headers={"Authorization": f"Bearer {token}"}
    )
    assert left.status_code == 200

    repeat = await command(client, room_id, token, "playpause", command_id=command_id)

    assert repeat["duplicate"] is True
    assert repeat["state"]["state_version"] == first["state"]["state_version"]
    assert repeat["state"]["playback"]["is_playing"] is True

    closed = event_log.events[-1]["state"]
    assert closed["status"] == "closed"
    assert closed["state_version"] > first["state"]["state_version"]
