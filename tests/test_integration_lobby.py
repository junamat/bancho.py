import asyncio
import os
import pytest

from bancho import BanchoClient, ConnectStates
from bancho.enums import BanchoLobbyTeamModes, BanchoLobbyWinConditions

USERNAME = os.getenv("OSU_IRC_USERNAME", "")
PASSWORD = os.getenv("OSU_IRC_PASSWORD", "")
TIMEOUT = 15

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not USERNAME, reason="OSU_IRC_USERNAME not set"),
]


@pytest.fixture
async def client():
    c = BanchoClient(USERNAME, PASSWORD)
    errors = []
    c.on("error", errors.append)

    connected = asyncio.Event()
    c.on("connected", connected.set)

    await c.connect()
    await asyncio.wait_for(connected.wait(), timeout=TIMEOUT)

    if errors:
        pytest.fail(f"connection error: {errors[0]}")

    yield c

    if c.state != ConnectStates.Disconnected:
        await c.disconnect()


@pytest.fixture
async def lobby(client):
    lb = await client.make_lobby("bancho.py integration test")
    yield lb
    try:
        await lb.close_lobby()
    except Exception:
        pass


async def test_lobby_created(lobby):
    assert lobby.id > 0
    assert lobby.get_history_url() == f"https://osu.ppy.sh/mp/{lobby.id}"


async def test_set_password(lobby):
    q: asyncio.Queue[None] = asyncio.Queue()
    lobby.once("passwordChanged", lambda: q.put_nowait(None))
    await lobby.set_password("testpass123")
    await asyncio.wait_for(q.get(), timeout=TIMEOUT)


async def test_clear_password(lobby):
    set_q: asyncio.Queue[None] = asyncio.Queue()
    lobby.once("passwordChanged", lambda: set_q.put_nowait(None))
    await lobby.set_password("testpass123")
    await asyncio.wait_for(set_q.get(), timeout=TIMEOUT)

    clear_q: asyncio.Queue[None] = asyncio.Queue()
    lobby.once("passwordRemoved", lambda: clear_q.put_nowait(None))
    await lobby.clear_password()
    await asyncio.wait_for(clear_q.get(), timeout=TIMEOUT)


async def test_set_valid_map(lobby):
    q: asyncio.Queue[int] = asyncio.Queue()
    lobby.once("beatmapId", q.put_nowait)
    await lobby.set_map(75)
    beatmap_id = await asyncio.wait_for(q.get(), timeout=TIMEOUT)
    assert beatmap_id == 75
    assert lobby.beatmap_id == 75


async def test_set_invalid_map(lobby):
    q: asyncio.Queue[None] = asyncio.Queue()
    lobby.once("invalidBeatmapId", lambda: q.put_nowait(None))
    await lobby.set_map(0)
    await asyncio.wait_for(q.get(), timeout=TIMEOUT)


async def test_lock(lobby):
    q: asyncio.Queue[None] = asyncio.Queue()
    lobby.once("slotsLocked", lambda: q.put_nowait(None))
    await lobby.lock()
    await asyncio.wait_for(q.get(), timeout=TIMEOUT)


async def test_unlock(lobby):
    locked_q: asyncio.Queue[None] = asyncio.Queue()
    lobby.once("slotsLocked", lambda: locked_q.put_nowait(None))
    await lobby.lock()
    await asyncio.wait_for(locked_q.get(), timeout=TIMEOUT)

    unlocked_q: asyncio.Queue[None] = asyncio.Queue()
    lobby.once("slotsUnlocked", lambda: unlocked_q.put_nowait(None))
    await lobby.unlock()
    await asyncio.wait_for(unlocked_q.get(), timeout=TIMEOUT)


async def test_timer_started(lobby):
    q: asyncio.Queue[int] = asyncio.Queue()
    lobby.once("startTimerStarted", q.put_nowait)
    await lobby.start_timer(30)
    seconds = await asyncio.wait_for(q.get(), timeout=TIMEOUT)
    assert seconds == 30
    await lobby.abort_timer()


async def test_timer_aborted(lobby):
    started_q: asyncio.Queue[int] = asyncio.Queue()
    lobby.once("startTimerStarted", started_q.put_nowait)
    await lobby.start_timer(30)
    await asyncio.wait_for(started_q.get(), timeout=TIMEOUT)

    aborted_q: asyncio.Queue[None] = asyncio.Queue()
    lobby.once("startTimerAborted", lambda: aborted_q.put_nowait(None))
    await lobby.abort_timer()
    await asyncio.wait_for(aborted_q.get(), timeout=TIMEOUT)


async def test_update_settings(lobby):
    q: asyncio.Queue[dict] = asyncio.Queue()
    lobby.once("matchSettings", q.put_nowait)
    await lobby.update_settings()
    ev = await asyncio.wait_for(q.get(), timeout=TIMEOUT)
    assert "team_mode" in ev
    assert "win_condition" in ev


async def test_set_settings(lobby):
    q: asyncio.Queue[dict] = asyncio.Queue()
    lobby.once("matchSettings", q.put_nowait)
    await lobby.set_settings(BanchoLobbyTeamModes.TeamVs, BanchoLobbyWinConditions.ScoreV2)
    await lobby.update_settings()
    await asyncio.wait_for(q.get(), timeout=TIMEOUT)
    assert lobby.team_mode == BanchoLobbyTeamModes.TeamVs
    assert lobby.win_condition == BanchoLobbyWinConditions.ScoreV2
