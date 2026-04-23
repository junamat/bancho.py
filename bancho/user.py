from __future__ import annotations

from typing import TYPE_CHECKING

from pyee.asyncio import AsyncIOEventEmitter

if TYPE_CHECKING:
    from .client import BanchoClient


class BanchoUser(AsyncIOEventEmitter):
    """Represents an osu! user on Bancho.

    Events:
        message (PrivateMessage): Emitted when this user sends a PM to the bot.
    """

    def __init__(self, client: BanchoClient, username: str) -> None:
        super().__init__()
        self._client = client
        self.username = username

    async def send_message(self, message: str) -> None:
        await self._client.send_message(self.username, message)

    def __repr__(self) -> str:
        return f"BanchoUser({self.username!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, BanchoUser):
            return self.username.casefold() == other.username.casefold()
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.username.casefold())
