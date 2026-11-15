import asyncio

from tests.helpers import auth, create_room, get_state, join_room, wait_until


async def test_explicit_leave_transfers_host_to_earliest_member(client):
    host = await create_room(client)
    room_id = host["room_id"]
    await asyncio.sleep(0.01)
    second = await join_room(client, host["invite_code"], name="Bob")
    await asyncio.sleep(0.01)
    third = await join_room(client, host["invite_code"], name="Carol")

    response = await client.post(f"/rooms/{room_id}/leave", headers=auth(host["token"]))
    assert response.status_code == 200
    data = response.json()
    assert data["left"] is True
    assert data["new_host_id"] == second["participant"]["id"]
    assert data["new_host_id"] != third["participant"]["id"]

    state = await get_state(client, room_id, third["token"])
    roles = {p["display_name"]: p["role"] for p in state["participants"]}
    assert roles == {"Bob": "host", "Carol": "member"}
    assert len(state["participants"]) == 2


async def test_reconnect_within_grace_keeps_host_role(client):
    host = await create_room(client)
    room_id = host["room_id"]
    member = await join_room(client, host["invite_code"], name="Bob")

    disconnected = await client.post(
        f"/rooms/{room_id}/disconnect", headers=auth(host["token"])
    )
    assert disconnected.status_code == 200
    host_entry = next(
        p
        for p in disconnected.json()["participants"]
        if p["id"] == host["participant"]["id"]
    )
    assert host_entry["connected"] is False

    reconnected = await client.post(
        f"/rooms/{room_id}/connect", headers=auth(host["token"])
    )
    assert reconnected.status_code == 200

    await asyncio.sleep(0.6)
    state = await get_state(client, room_id, member["token"])
    roles = {p["id"]: p["role"] for p in state["participants"]}
    assert roles[host["participant"]["id"]] == "host"
    assert roles[member["participant"]["id"]] == "member"


async def test_long_disconnect_transfers_host_to_earliest_connected(client):
    host = await create_room(client)
    room_id = host["room_id"]
    await asyncio.sleep(0.01)
    second = await join_room(client, host["invite_code"], name="Bob")
    member_id = second["participant"]["id"]

    response = await client.post(
        f"/rooms/{room_id}/disconnect", headers=auth(host["token"])
    )
    assert response.status_code == 200

    async def second_is_host():
        state = await get_state(client, room_id, second["token"])
        current = next(p for p in state["participants"] if p["id"] == member_id)
        return current["role"] == "host"

    await wait_until(second_is_host, timeout=3.0)

    state = await get_state(client, room_id, second["token"])
    host_entry = next(
        p for p in state["participants"] if p["id"] == host["participant"]["id"]
    )
    assert host_entry["role"] == "member"
    assert host_entry["connected"] is False


async def test_member_leave_does_not_change_host(client):
    host = await create_room(client)
    room_id = host["room_id"]
    member = await join_room(client, host["invite_code"], name="Bob")

    response = await client.post(
        f"/rooms/{room_id}/leave", headers=auth(member["token"])
    )
    assert response.status_code == 200
    assert response.json()["new_host_id"] is None

    state = await get_state(client, room_id, host["token"])
    assert len(state["participants"]) == 1
    assert state["participants"][0]["role"] == "host"
