import uuid

from tests.helpers import command, create_room, get_state


async def test_add_change_and_remove_queue_items(client):
    host = await create_room(client)
    room_id = host["room_id"]
    token = host["token"]

    first = await command(
        client, room_id, token, "add_video", {"url": "https://rutube.ru/video/a/"}
    )
    first_id = first["state"]["playback"]["video_id"]
    assert [video["id"] for video in first["state"]["queue"]] == [first_id]

    second = await command(
        client, room_id, token, "add_video", {"url": "https://rutube.ru/video/b/"}
    )
    second_id = second["state"]["queue"][1]["id"]

    third = await command(
        client, room_id, token, "add_video", {"url": "https://rutube.ru/video/c/"}
    )
    third_id = third["state"]["queue"][2]["id"]
    assert [video["id"] for video in third["state"]["queue"]] == [
        first_id,
        second_id,
        third_id,
    ]
    assert [video["position"] for video in third["state"]["queue"]] == [0, 1, 2]
    assert third["state"]["state_version"] == 4

    moved = await command(
        client,
        room_id,
        token,
        "change_queue",
        {"video_ids": [third_id, first_id, second_id]},
    )
    assert [video["id"] for video in moved["state"]["queue"]] == [
        third_id,
        first_id,
        second_id,
    ]
    assert moved["state"]["playback"]["video_id"] == first_id

    removed = await command(
        client, room_id, token, "remove_video", {"video_id": first_id}
    )
    assert removed["state"]["playback"]["video_id"] == third_id
    assert [video["id"] for video in removed["state"]["queue"]] == [third_id, second_id]
    assert removed["state"]["playback"]["is_playing"] is False
    assert removed["state"]["playback"]["position_seconds"] == 0.0

    removed = await command(
        client, room_id, token, "remove_video", {"video_id": third_id}
    )
    assert removed["state"]["playback"]["video_id"] == second_id
    assert [video["id"] for video in removed["state"]["queue"]] == [second_id]

    removed = await command(
        client, room_id, token, "remove_video", {"video_id": second_id}
    )
    assert removed["state"]["playback"]["video_id"] is None
    assert removed["state"]["queue"] == []
    assert removed["state"]["playback"]["is_playing"] is False


async def test_change_queue_rejects_invalid_ids(client):
    host = await create_room(client)
    room_id = host["room_id"]
    token = host["token"]

    current = (
        await command(
            client, room_id, token, "add_video", {"url": "https://rutube.ru/video/a/"}
        )
    )["state"]["playback"]["video_id"]
    upcoming = (
        await command(
            client, room_id, token, "add_video", {"url": "https://rutube.ru/video/b/"}
        )
    )["state"]["queue"][1]["id"]

    payloads = [
        {"video_ids": [upcoming, upcoming]},
        {"video_ids": []},
        {"video_ids": [current]},
        {"video_ids": [str(uuid.uuid4())]},
    ]
    for payload in payloads:
        bad = await command(
            client, room_id, token, "change_queue", payload, expected_status=422
        )
        assert bad["error"]["code"] == "invalid_payload"

    state = await get_state(client, room_id, token)
    assert state["state_version"] == 3
    assert state["playback"]["video_id"] == current
    assert [video["id"] for video in state["queue"]] == [current, upcoming]


async def test_invalid_rutube_url_and_missing_video(client):
    host = await create_room(client)
    room_id = host["room_id"]
    token = host["token"]

    bad_url = await command(
        client,
        room_id,
        token,
        "add_video",
        {"url": "https://youtube.com/watch?v=x"},
        expected_status=422,
    )
    assert bad_url["error"]["code"] == "invalid_video_url"

    state = await get_state(client, room_id, token)
    assert state["queue"] == []
    assert state["state_version"] == 1

    missing = await command(
        client,
        room_id,
        token,
        "remove_video",
        {"video_id": str(uuid.uuid4())},
        expected_status=422,
    )
    assert missing["error"]["code"] == "invalid_payload"
