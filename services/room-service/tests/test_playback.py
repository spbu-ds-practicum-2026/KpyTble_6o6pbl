import asyncio

from tests.helpers import add_video, command, create_room, get_state


async def test_add_video_selects_current_and_stays_paused(client):
    host = await create_room(client)
    result = await add_video(client, host["room_id"], host["token"])

    state = result["state"]
    assert state["current_video_id"] is not None
    assert len(state["queue"]) == 1
    assert state["playback"]["is_playing"] is False
    assert state["playback"]["position_seconds"] == 0.0
    assert state["state_version"] == 2


async def test_play_advances_position_and_pause_freezes_it(client):
    host = await create_room(client)
    await add_video(client, host["room_id"], host["token"])

    await command(client, host["room_id"], host["token"], "play")
    await asyncio.sleep(0.2)

    state = await get_state(client, host["room_id"], host["token"])
    assert state["playback"]["is_playing"] is True
    assert 0.1 <= state["playback"]["position_seconds"] < 2.0

    paused = await command(client, host["room_id"], host["token"], "pause")
    paused_position = paused["state"]["playback"]["position_seconds"]
    assert paused["state"]["playback"]["is_playing"] is False

    await asyncio.sleep(0.15)
    state = await get_state(client, host["room_id"], host["token"])
    assert abs(state["playback"]["position_seconds"] - paused_position) < 0.05


async def test_seek_sets_position_and_keeps_play_state(client):
    host = await create_room(client)
    await add_video(client, host["room_id"], host["token"])
    await command(client, host["room_id"], host["token"], "play")

    seek = await command(
        client,
        host["room_id"],
        host["token"],
        "seek",
        {"position_seconds": 42},
    )
    assert seek["state"]["playback"]["is_playing"] is True
    assert 41.9 <= seek["state"]["playback"]["position_seconds"] < 43.0

    paused = await command(client, host["room_id"], host["token"], "pause")
    assert paused["state"]["playback"]["is_playing"] is False

    seek = await command(
        client,
        host["room_id"],
        host["token"],
        "seek",
        {"position_seconds": 10},
    )
    assert seek["state"]["playback"]["position_seconds"] == 10.0
    assert seek["state"]["playback"]["is_playing"] is False


async def test_seek_without_video_is_rejected(client):
    host = await create_room(client)
    response = await client.post(
        f"/rooms/{host['room_id']}/commands",
        headers={"Authorization": f"Bearer {host['token']}"},
        json={
            "command_id": "seek-without-video",
            "type": "seek",
            "payload": {"position_seconds": 5},
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "no_current_video"


async def test_next_switches_video_and_stops_at_end(client):
    host = await create_room(client)
    room_id = host["room_id"]
    token = host["token"]

    await add_video(client, room_id, token, "https://rutube.ru/video/one/")
    await add_video(client, room_id, token, "https://rutube.ru/video/two/")
    await add_video(client, room_id, token, "https://rutube.ru/video/three/")

    initial = await get_state(client, room_id, token)
    assert len(initial["queue"]) == 3
    first_id = initial["current_video_id"]

    await command(client, room_id, token, "play")
    second = await command(client, room_id, token, "next")
    assert second["state"]["current_video_id"] != first_id
    assert second["state"]["playback"]["is_playing"] is True

    third = await command(client, room_id, token, "next")
    assert third["state"]["current_video_id"] != second["state"]["current_video_id"]

    stopped = await command(client, room_id, token, "next")
    assert stopped["state"]["current_video_id"] is None
    assert stopped["state"]["playback"]["is_playing"] is False
    assert stopped["state"]["playback"]["position_seconds"] == 0.0
