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
    expected_video = first["state"]["current_video_id"]
    expected_version = first["state"]["state_version"]

    second = await command(client, room_id, token, "next", command_id=command_id)
    assert second["duplicate"] is True
    assert second["state"]["current_video_id"] == expected_video
    assert second["state"]["state_version"] == expected_version

    state = await get_state(client, room_id, token)
    assert state["current_video_id"] == expected_video
    assert state["state_version"] == expected_version


async def test_repeated_add_video_creates_one_queue_item(client):
    host = await create_room(client)
    room_id = host["room_id"]
    token = host["token"]
    payload = {"url": "https://rutube.ru/video/same/", "title": "Same"}
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
    assert len(second["state"]["queue"]) == 1

    state = await get_state(client, room_id, token)
    assert len(state["queue"]) == 1
    assert state["state_version"] == expected_version


async def test_same_command_id_with_different_parameters_is_rejected(client):
    host = await create_room(client)
    room_id = host["room_id"]
    token = host["token"]
    command_id = "shared-command"

    await command(client, room_id, token, "pause", command_id=command_id)

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


async def test_duplicate_command_allows_different_command_id(client):
    host = await create_room(client)
    room_id = host["room_id"]
    token = host["token"]

    await add_video(client, room_id, token)
    first = await command(client, room_id, token, "pause")
    second = await command(client, room_id, token, "pause")

    assert first["duplicate"] is False
    assert second["duplicate"] is False
    assert second["state"]["state_version"] == first["state"]["state_version"] + 1


async def test_repeated_play_is_idempotent(client):
    host = await create_room(client)
    room_id = host["room_id"]
    token = host["token"]
    await add_video(client, room_id, token)

    command_id = "play-command-1"
    first = await command(client, room_id, token, "play", command_id=command_id)
    second = await command(client, room_id, token, "play", command_id=command_id)

    assert first["duplicate"] is False
    assert second["duplicate"] is True
    assert second["state"]["state_version"] == first["state"]["state_version"]
    assert second["state"]["playback"]["is_playing"] is True

    state = await get_state(client, room_id, token)
    assert state["state_version"] == first["state"]["state_version"]


async def test_repeated_pause_is_idempotent(client):
    host = await create_room(client)
    room_id = host["room_id"]
    token = host["token"]
    await add_video(client, room_id, token)
    await command(client, room_id, token, "play")

    command_id = "pause-command-1"
    first = await command(client, room_id, token, "pause", command_id=command_id)
    second = await command(client, room_id, token, "pause", command_id=command_id)

    assert first["duplicate"] is False
    assert second["duplicate"] is True
    assert second["state"]["state_version"] == first["state"]["state_version"]
    assert second["state"]["playback"]["is_playing"] is False


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

    state = await get_state(client, room_id, token)
    assert state["state_version"] == first["state"]["state_version"]
    assert state["playback"]["position_seconds"] == 42.0


async def test_repeated_remove_video_is_idempotent(client):
    host = await create_room(client)
    room_id = host["room_id"]
    token = host["token"]

    first_add = await add_video(client, room_id, token, "https://rutube.ru/video/a/")
    first_id = first_add["state"]["current_video_id"]
    second_add = await add_video(client, room_id, token, "https://rutube.ru/video/b/")
    second_id = second_add["state"]["queue"][1]["id"]

    command_id = "remove-command-1"
    payload = {"video_id": first_id}
    first = await command(
        client, room_id, token, "remove_video", payload, command_id=command_id
    )
    second = await command(
        client, room_id, token, "remove_video", payload, command_id=command_id
    )

    assert first["duplicate"] is False
    assert second["duplicate"] is True
    assert second["state"]["state_version"] == first["state"]["state_version"]
    assert len(second["state"]["queue"]) == 1
    assert second["state"]["current_video_id"] == second_id

    state = await get_state(client, room_id, token)
    assert len(state["queue"]) == 1
    assert state["current_video_id"] == second_id


async def test_repeated_move_video_is_idempotent(client):
    host = await create_room(client)
    room_id = host["room_id"]
    token = host["token"]

    await add_video(client, room_id, token, "https://rutube.ru/video/a/", "A")
    await add_video(client, room_id, token, "https://rutube.ru/video/b/", "B")
    result = await add_video(client, room_id, token, "https://rutube.ru/video/c/", "C")
    third_id = result["state"]["queue"][2]["id"]

    command_id = "move-command-1"
    payload = {"video_id": third_id, "position": 0}
    first = await command(
        client, room_id, token, "move_video", payload, command_id=command_id
    )
    second = await command(
        client, room_id, token, "move_video", payload, command_id=command_id
    )

    assert first["duplicate"] is False
    assert second["duplicate"] is True
    assert second["state"]["state_version"] == first["state"]["state_version"]
    assert [video["title"] for video in second["state"]["queue"]] == ["C", "A", "B"]


async def test_repeated_set_control_mode_is_idempotent(client):
    host = await create_room(client)
    room_id = host["room_id"]
    token = host["token"]

    command_id = "mode-command-1"
    payload = {"mode": "all"}
    first = await command(
        client, room_id, token, "set_control_mode", payload, command_id=command_id
    )
    second = await command(
        client, room_id, token, "set_control_mode", payload, command_id=command_id
    )

    assert first["duplicate"] is False
    assert second["duplicate"] is True
    assert second["state"]["state_version"] == first["state"]["state_version"]
    assert second["state"]["control_mode"] == "all"


async def test_repeated_command_after_close_returns_saved_confirmation(client):
    host = await create_room(client)
    room_id = host["room_id"]
    token = host["token"]
    await add_video(client, room_id, token)

    command_id = "play-before-close"
    first = await command(client, room_id, token, "play", command_id=command_id)
    await command(client, room_id, token, "close_room")

    repeat = await command(client, room_id, token, "play", command_id=command_id)

    assert repeat["duplicate"] is True
    assert repeat["state"]["state_version"] == first["state"]["state_version"]
    assert repeat["state"]["playback"]["is_playing"] is True

    state = await get_state(client, room_id, token)
    assert state["status"] == "closed"
    assert state["state_version"] > first["state"]["state_version"]
