import asyncio

from tests.helpers import command, create_room, get_state


async def test_add_video_selects_current_and_stays_paused(client):
    host = await create_room(client)
    result = await command(
        client,
        host["room_id"],
        host["token"],
        "add_video",
        {"url": "https://rutube.ru/video/a/"},
    )

    state = result["state"]
    assert state["playback"]["video_id"] is not None
    assert state["current_video_id"] == state["playback"]["video_id"]
    assert [video["id"] for video in state["queue"]] == [state["playback"]["video_id"]]
    assert state["playback"]["is_playing"] is False
    assert state["playback"]["position_seconds"] == 0.0
    assert state["state_version"] == 2


async def test_playpause_toggles_is_playing_and_freezes_position(client):
    host = await create_room(client)
    await command(
        client,
        host["room_id"],
        host["token"],
        "add_video",
        {"url": "https://rutube.ru/video/a/"},
    )

    playing = await command(client, host["room_id"], host["token"], "playpause")
    assert playing["state"]["playback"]["is_playing"] is True

    await asyncio.sleep(0.2)
    state = await get_state(client, host["room_id"], host["token"])
    assert 0.1 <= state["playback"]["position_seconds"] < 2.0

    paused = await command(client, host["room_id"], host["token"], "playpause")
    paused_position = paused["state"]["playback"]["position_seconds"]
    assert paused["state"]["playback"]["is_playing"] is False

    await asyncio.sleep(0.15)
    state = await get_state(client, host["room_id"], host["token"])
    assert abs(state["playback"]["position_seconds"] - paused_position) < 0.05

    resumed = await command(client, host["room_id"], host["token"], "playpause")
    assert resumed["state"]["playback"]["is_playing"] is True


async def test_seek_sets_position_and_keeps_play_state(client):
    host = await create_room(client)
    await command(
        client,
        host["room_id"],
        host["token"],
        "add_video",
        {"url": "https://rutube.ru/video/a/"},
    )
    await command(client, host["room_id"], host["token"], "playpause")

    seek = await command(
        client, host["room_id"], host["token"], "seek", {"position_seconds": 42}
    )
    assert seek["state"]["playback"]["is_playing"] is True
    assert 41.9 <= seek["state"]["playback"]["position_seconds"] < 43.0

    await command(client, host["room_id"], host["token"], "playpause")
    seek = await command(
        client, host["room_id"], host["token"], "seek", {"position_seconds": 10}
    )
    assert seek["state"]["playback"]["position_seconds"] == 10.0
    assert seek["state"]["playback"]["is_playing"] is False


async def test_playback_commands_require_current_video(client):
    host = await create_room(client)
    for command_type, payload in (
        ("playpause", {}),
        ("seek", {"position_seconds": 5}),
        ("next", {}),
    ):
        denied = await command(
            client,
            host["room_id"],
            host["token"],
            command_type,
            payload,
            expected_status=409,
        )
        assert denied["error"]["code"] == "no_current_video"


async def test_next_switches_video_and_stops_at_end(client):
    host = await create_room(client)
    room_id = host["room_id"]
    token = host["token"]

    await command(
        client, room_id, token, "add_video", {"url": "https://rutube.ru/video/one/"}
    )
    await command(
        client, room_id, token, "add_video", {"url": "https://rutube.ru/video/two/"}
    )
    await command(
        client, room_id, token, "add_video", {"url": "https://rutube.ru/video/three/"}
    )

    initial = await get_state(client, room_id, token)
    first_id = initial["playback"]["video_id"]
    queue_urls = [
        "https://rutube.ru/video/one/",
        "https://rutube.ru/video/two/",
        "https://rutube.ru/video/three/",
    ]
    assert [video["url"] for video in initial["queue"]] == queue_urls

    await command(client, room_id, token, "playpause")
    second = await command(client, room_id, token, "next")
    second_video_id = second["state"]["playback"]["video_id"]
    assert second_video_id != first_id
    assert second["state"]["current_video_id"] == second_video_id
    assert second["state"]["playback"]["is_playing"] is True
    assert [video["url"] for video in second["state"]["queue"]] == queue_urls

    third = await command(client, room_id, token, "next")
    third_video_id = third["state"]["playback"]["video_id"]
    assert third_video_id != second_video_id
    assert third["state"]["current_video_id"] == third_video_id
    assert [video["url"] for video in third["state"]["queue"]] == queue_urls

    stopped = await command(client, room_id, token, "next")
    assert stopped["state"]["playback"]["video_id"] is None
    assert stopped["state"]["current_video_id"] is None
    assert stopped["state"]["playback"]["is_playing"] is False
    assert stopped["state"]["playback"]["position_seconds"] == 0.0
    assert [video["url"] for video in stopped["state"]["queue"]] == queue_urls


async def test_seek_rejects_non_finite_position(client):
    host = await create_room(client)
    await command(
        client,
        host["room_id"],
        host["token"],
        "add_video",
        {"url": "https://rutube.ru/video/a/"},
    )
    denied = await command(
        client,
        host["room_id"],
        host["token"],
        "seek",
        {"position_seconds": "nan"},
        expected_status=422,
    )
    assert denied["error"]["code"] == "invalid_payload"
