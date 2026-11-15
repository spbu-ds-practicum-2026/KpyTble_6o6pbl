from tests.helpers import add_video, command, create_room, get_state


async def test_add_move_and_remove_queue_items(client):
    host = await create_room(client)
    room_id = host["room_id"]
    token = host["token"]

    result = await add_video(client, room_id, token, "https://rutube.ru/video/a/", "A")
    first_id = result["state"]["current_video_id"]
    result = await add_video(client, room_id, token, "https://rutube.ru/video/b/", "B")
    second_id = result["state"]["queue"][1]["id"]
    result = await add_video(client, room_id, token, "https://rutube.ru/video/c/", "C")
    third_id = result["state"]["queue"][2]["id"]

    assert [video["title"] for video in result["state"]["queue"]] == ["A", "B", "C"]
    assert [video["order_index"] for video in result["state"]["queue"]] == [0, 1, 2]

    moved = await command(
        client,
        room_id,
        token,
        "move_video",
        {"video_id": third_id, "position": 0},
    )
    assert [video["title"] for video in moved["state"]["queue"]] == ["C", "A", "B"]
    assert [video["order_index"] for video in moved["state"]["queue"]] == [0, 1, 2]
    assert moved["state"]["current_video_id"] == first_id

    removed = await command(
        client, room_id, token, "remove_video", {"video_id": first_id}
    )
    assert [video["title"] for video in removed["state"]["queue"]] == ["C", "B"]
    # The next video after the removed current one becomes current and is paused.
    assert removed["state"]["current_video_id"] == second_id
    assert removed["state"]["playback"]["is_playing"] is False
    assert removed["state"]["playback"]["position_seconds"] == 0.0

    # B was current and has no following video, so playback stops.
    removed = await command(
        client, room_id, token, "remove_video", {"video_id": second_id}
    )
    assert removed["state"]["current_video_id"] is None
    assert [video["title"] for video in removed["state"]["queue"]] == ["C"]
    assert removed["state"]["playback"]["is_playing"] is False

    removed = await command(
        client, room_id, token, "remove_video", {"video_id": third_id}
    )
    assert removed["state"]["queue"] == []
    assert removed["state"]["current_video_id"] is None
    assert removed["state"]["playback"]["is_playing"] is False


async def test_remove_last_current_video_when_it_is_the_only_one(client):
    host = await create_room(client)
    room_id = host["room_id"]
    token = host["token"]

    result = await add_video(client, room_id, token)
    video_id = result["state"]["current_video_id"]

    removed = await command(
        client, room_id, token, "remove_video", {"video_id": video_id}
    )
    assert removed["state"]["current_video_id"] is None
    assert removed["state"]["queue"] == []


async def test_invalid_rutube_url_and_missing_video(client):
    host = await create_room(client)
    room_id = host["room_id"]
    token = host["token"]

    response = await client.post(
        f"/rooms/{room_id}/commands",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "command_id": "bad-url",
            "type": "add_video",
            "payload": {"url": "https://youtube.com/watch?v=x"},
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_video_url"

    state = await get_state(client, room_id, token)
    assert state["queue"] == []
    assert state["state_version"] == 1

    result = await command(
        client,
        room_id,
        token,
        "remove_video",
        {"video_id": "00000000-0000-0000-0000-000000000000"},
        expected_status=404,
    )
    assert result["error"]["code"] == "video_not_found"

    position = await command(
        client,
        room_id,
        token,
        "move_video",
        {"video_id": "00000000-0000-0000-0000-000000000000", "position": 0},
        expected_status=404,
    )
    assert position["error"]["code"] == "video_not_found"
