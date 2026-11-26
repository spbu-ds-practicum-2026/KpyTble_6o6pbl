import asyncio

from tests.helpers import auth, create_room, get_state, join_room, wait_until


async def test_explicit_leave_transfers_host_to_earliest_member(client):
    host = await create_room(client)
    room_id = host["room_id"]
    await asyncio.sleep(0.01)
    bob = await join_room(client, host["invite_code"], name="Bob")
    await asyncio.sleep(0.01)
    await join_room(client, host["invite_code"], name="Carol")

    response = await client.post(f"/rooms/{room_id}/leave", headers=auth(host["token"]))
    assert response.status_code == 200
    assert response.json() == {"left": True}

    state = await get_state(client, room_id, bob["token"])
    roles = {p["display_name"]: p["role"] for p in state["participants"]}
    assert roles == {"Bob": "host", "Carol": "member"}


async def test_reconnect_within_grace_keeps_host_role(client):
    host = await create_room(client)
    room_id = host["room_id"]
    member = await join_room(client, host["invite_code"], name="Bob")

    disconnected = await client.post(
        f"/rooms/{room_id}/disconnect", headers=auth(host["token"])
    )
    assert disconnected.status_code == 200
    assert disconnected.json()["state_version"] == 3

    reconnected = await client.post(
        f"/rooms/{room_id}/connect", headers=auth(host["token"])
    )
    assert reconnected.status_code == 200
    assert reconnected.json()["state_version"] == 4

    await asyncio.sleep(0.6)
    state = await get_state(client, room_id, member["token"])
    roles = {p["display_name"]: p["role"] for p in state["participants"]}
    assert roles == {"Host": "host", "Bob": "member"}


async def test_long_disconnect_transfers_host_to_earliest_connected(client, event_log):
    host = await create_room(client)
    room_id = host["room_id"]
    await asyncio.sleep(0.01)
    second = await join_room(client, host["invite_code"], name="Bob")

    response = await client.post(
        f"/rooms/{room_id}/disconnect", headers=auth(host["token"])
    )
    assert response.status_code == 200

    async def second_is_host():
        state = await get_state(client, room_id, second["token"])
        entry = next(
            participant
            for participant in state["participants"]
            if participant["display_name"] == "Bob"
        )
        return entry["role"] == "host"

    await wait_until(second_is_host, timeout=3.0)

    state = await get_state(client, room_id, second["token"])
    roles = {p["display_name"]: p["role"] for p in state["participants"]}
    assert roles == {"Host": "member", "Bob": "host"}
    assert any(event["reason"] == "host_changed" for event in event_log.events)


async def test_member_leave_does_not_change_host(client):
    host = await create_room(client)
    room_id = host["room_id"]
    member = await join_room(client, host["invite_code"], name="Bob")

    response = await client.post(
        f"/rooms/{room_id}/leave", headers=auth(member["token"])
    )
    assert response.status_code == 200
    assert response.json() == {"left": True}

    state = await get_state(client, room_id, host["token"])
    assert [p["display_name"] for p in state["participants"]] == ["Host"]
    assert state["participants"][0]["role"] == "host"
