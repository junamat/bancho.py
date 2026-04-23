from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .channel import BanchoChannel
    from .user import BanchoUser


@dataclass
class BanchoMessage:
    user: BanchoUser
    message: str


@dataclass
class PrivateMessage(BanchoMessage):
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ChannelMessage(BanchoMessage):
    channel: BanchoChannel
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
