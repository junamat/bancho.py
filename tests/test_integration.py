import asyncio
import os
import pytest

from bancho import ConnectStates, PrivateMessage

USERNAME = os.getenv("OSU_IRC_USERNAME", "")
PASSWORD = os.getenv("OSU_IRC_PASSWORD", "")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not USERNAME, reason="OSU_IRC_USERNAME not set"),
]

async def test_connect(client):
    assert client.state == ConnectStates.Connected


async def test_banchobot_replies_to_pm(client):
    reply = asyncio.get_event_loop().create_future()

    def on_pm(msg: PrivateMessage):
        if msg.user.username == "BanchoBot" and not reply.done():
            reply.set_result(msg)

    client.on("PM", on_pm)
    await client.send_message("BanchoBot", f"!stats {USERNAME}")

    msg = await asyncio.wait_for(reply, timeout=15)
    assert isinstance(msg, PrivateMessage)
    assert msg.user.username == "BanchoBot"
    assert USERNAME.lower() in msg.message.lower()


async def test_user_object_is_cached(client):
    user_a = client.get_user("BanchoBot")
    user_b = client.get_user("banchobot")
    assert user_a is user_b


async def test_user_can_send_pm(client):
    reply = asyncio.get_event_loop().create_future()

    def on_pm(msg: PrivateMessage):
        if msg.user.username == "BanchoBot" and not reply.done():
            reply.set_result(msg)

    client.on("PM", on_pm)
    user = client.get_user("BanchoBot")
    await user.send_message(f"!stats {USERNAME}")

    msg = await asyncio.wait_for(reply, timeout=15)
    assert msg.user.username == "BanchoBot"
