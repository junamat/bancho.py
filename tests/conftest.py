from pathlib import Path
import asyncio
import os
import pytest

from bancho import BanchoClient, ConnectStates

_env = Path(__file__).parent.parent / ".env"
if _env.exists():
    for _line in _env.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())


@pytest.fixture(scope="session")
async def client():
    username = os.getenv("OSU_IRC_USERNAME", "")
    password = os.getenv("OSU_IRC_PASSWORD", "")

    c = BanchoClient(username, password)
    errors = []
    c.on("error", errors.append)

    connected = asyncio.Event()
    c.on("connected", connected.set)

    await c.connect()
    await asyncio.wait_for(connected.wait(), timeout=15)

    if errors:
        pytest.fail(f"connection error: {errors[0]}")

    yield c

    if c.state != ConnectStates.Disconnected:
        await c.disconnect()
