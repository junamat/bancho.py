from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import TYPE_CHECKING

from pyee.asyncio import AsyncIOEventEmitter

if TYPE_CHECKING:
    from .client import BanchoClient
    from .user import BanchoUser


class BanchoChannelMemberMode(IntEnum):
    Regular = 0
    Operator = 1


@dataclass
class BanchoChannelMember:
    user: BanchoUser
    mode: BanchoChannelMemberMode = field(default=BanchoChannelMemberMode.Regular)


class BanchoChannel(AsyncIOEventEmitter):
    """Represents a Bancho IRC channel.

    Events:
        message (ChannelMessage): Emitted on a message in the channel.
        JOIN (BanchoUser): Emitted when a user joins.
        PART (BanchoUser): Emitted when a user leaves.
    """

    def __init__(self, client: BanchoClient, name: str) -> None:
        super().__init__()
        self._client = client
        self.name = name
        self.members: dict[str, BanchoChannelMember] = {}

    async def send_message(self, message: str) -> None:
        await self._client.send_message(self.name, message)

    async def join(self) -> None:
        await self._client.join_channel(self.name)

    async def part(self) -> None:
        await self._client.part_channel(self.name)

    def __repr__(self) -> str:
        return f"BanchoChannel({self.name!r})"


class BanchoMultiplayerChannel(BanchoChannel):
    """A #mp_<id> channel. Will be linked to a BanchoLobby."""

    @property
    def lobby_id(self) -> int:
        return int(self.name.removeprefix("#mp_"))

    def __repr__(self) -> str:
        return f"BanchoMultiplayerChannel({self.name!r})"
