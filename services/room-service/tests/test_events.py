from tests.helpers import add_video, command, create_room, event_shape, join_room


async def test_events_are_published_for_every_change(client, event_log):
    host = await create_room(client)
    room_id = host["room_id"]

    await join_room(client, host["invite_code"], name="Bob")
    await add_video(client, room_id, host["token"])
    result = await command(client, room_id, host["token"], "playpause")

    reasons = [event["reason"] for event in event_log.events]
    assert reasons == [
        "created",
        "participant_joined",
        "add_video",
        "playpause",
    ]
    for event in event_log.events:
        event_shape(event)
        assert event["room_id"] == room_id

    last = event_log.events[-1]
    assert last["type"] == "room_state_changed"
    assert last["state_version"] == result["state"]["state_version"]
    assert last["state"] == result["state"]


async def test_duplicate_command_does_not_emit_event(client, event_log):
    host = await create_room(client)
    room_id = host["room_id"]
    await add_video(client, room_id, host["token"])

    before = len(event_log.events)
    first = await command(
        client, room_id, host["token"], "playpause", command_id="cmd-events"
    )
    repeat = await command(
        client, room_id, host["token"], "playpause", command_id="cmd-events"
    )

    assert first["duplicate"] is False
    assert repeat["duplicate"] is True
    assert len(event_log.events) == before + 1
