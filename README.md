# bancho.py

[![Tests](https://github.com/{owner}/bancho.py/actions/workflows/tests.yml/badge.svg)](https://github.com/junamat/bancho.py/actions/workflows/tests.yml)
[![PyPI](https://img.shields.io/pypi/v/bancho.py)](https://pypi.org/project/bancho.py/)
[![Python](https://img.shields.io/pypi/pyversions/bancho.py)](https://pypi.org/project/bancho.py/)
[![License](https://img.shields.io/github/license/junamat/bancho.py)](LICENSE)

A Python library for interacting with Bancho, osu!'s chat server, in real-time.

Connects over Bancho's IRC interface and lets you listen to messages, join channels, and manage multiplayer lobbies from Python. Heavily inspired by [bancho.js](https://bancho.js.org/) — if you're working in JavaScript, go use that instead.

## Installation

```
pip install bancho.py
```

## Quick start

```python
import asyncio
from bancho import BanchoClient

client = BanchoClient("your_username", "your_irc_password")

@client.on("PM")
async def on_pm(message):
    print(f"{message.user.username}: {message.message}")

asyncio.run(client.connect())
```

You can get your IRC password at [osu.ppy.sh/p/irc](https://osu.ppy.sh/p/irc).

> **Note:** Please use a dedicated bot account and make sure it's authorized per the [osu! Bot Account wiki page](https://osu.ppy.sh/wiki/en/Bot_account). Don't run this on your main account.

## Features

- Real-time chat — PMs and channel messages
- Multiplayer lobby management
- Mod flag parsing
- asyncio-native, event-driven API
- Rate limiting built in

## Credits

bancho.py is heavily inspired by [bancho.js](https://bancho.js.org/) by [ThePooN](https://github.com/ThePooN). The overall design, class structure, and event model are all drawn from that project. If you're building something in JS, use bancho.js — it's well-maintained and battle-tested.

## License

GPL-3.0
