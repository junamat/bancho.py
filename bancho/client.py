import asyncio
import contextlib
from pyee.asyncio import AsyncIOEventEmitter

from .channel import BanchoChannel, BanchoChannelMember, BanchoMultiplayerChannel
from .enums import ConnectStates
from .messages import ChannelMessage, PrivateMessage
from .user import BanchoUser

BANCHO_HOST = "irc.ppy.sh"
BANCHO_PORT = 6667


def _parse_irc_line(line: str) -> tuple[str | None, str, list[str]]:
    """Parse an IRC message into (prefix, command, params).

    The trailing param (prefixed with ':') is included as the last element of params.
    """
    prefix = None
    if line.startswith(":"):
        idx = line.index(" ")
        prefix = line[1:idx]
        line = line[idx + 1:]

    trailing = None
    if " :" in line:
        line, trailing = line.split(" :", 1)

    parts = line.split()
    command = parts[0]
    params = parts[1:]
    if trailing is not None:
        params.append(trailing)

    return prefix, command, params


class BanchoClient(AsyncIOEventEmitter):
    """Client for Bancho, osu!'s IRC-based chat server.

    Events:
        connected: Emitted when successfully authenticated.
        disconnected: Emitted when the connection closes.
        state (ConnectStates): Emitted on every state change.
        error (Exception): Emitted on unrecoverable errors.
        PM (PrivateMessage): Emitted on private message.
        CM (ChannelMessage): Emitted on channel message.
        JOIN (dict): Emitted when a user joins a channel. Keys: channel (BanchoChannel), user (BanchoUser).
        PART (dict): Emitted when a user leaves a channel. Keys: channel (BanchoChannel), user (BanchoUser).
        QUIT (dict): Emitted when a user disconnects. Keys: user (BanchoUser), message (str | None).
        nochannel (str): Emitted when a channel doesn't exist.
        nouser (str): Emitted when a user doesn't exist.
        rejectedMessage (str): Emitted when a message is rejected by the server.
    """

    def __init__(
        self,
        username: str,
        password: str,
        host: str = BANCHO_HOST,
        port: int = BANCHO_PORT,
        rate_limit: float = 0.3,
    ) -> None:
        super().__init__()
        self.username = username
        self._password = password
        self._host = host
        self._port = port
        self._rate_limit = rate_limit

        self._state = ConnectStates.Disconnected
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._send_queue: asyncio.Queue[str] = asyncio.Queue()
        self._read_task: asyncio.Task | None = None
        self._send_task: asyncio.Task | None = None
        self._users: dict[str, BanchoUser] = {}
        self._channels: dict[str, BanchoChannel] = {}

    @property
    def state(self) -> ConnectStates:
        return self._state

    def _set_state(self, state: ConnectStates) -> None:
        self._state = state
        self.emit("state", state)
        if state == ConnectStates.Connected:
            self.emit("connected")
        elif state == ConnectStates.Disconnected:
            self.emit("disconnected")

    async def connect(self) -> None:
        if self._state != ConnectStates.Disconnected:
            raise RuntimeError(f"Cannot connect: current state is {self._state.value}")

        self._set_state(ConnectStates.Connecting)
        self._reader, self._writer = await asyncio.open_connection(self._host, self._port)

        await self._send_raw(f"PASS {self._password}")
        await self._send_raw(f"NICK {self.username}")
        await self._send_raw(f"USER {self.username} 0 * :{self.username}")

        self._read_task = asyncio.create_task(self._read_loop())
        self._send_task = asyncio.create_task(self._send_loop())

    async def disconnect(self) -> None:
        if self._state == ConnectStates.Disconnected:
            return
        self._set_state(ConnectStates.Disconnecting)
        await self._send_raw("QUIT")
        await self._cleanup()

    async def _cleanup(self) -> None:
        if self._read_task and not self._read_task.done():
            self._read_task.cancel()
        if self._send_task and not self._send_task.done():
            self._send_task.cancel()

        writer, self._writer = self._writer, None
        self._reader = None
        self._set_state(ConnectStates.Disconnected)

        if writer:
            writer.close()
            with contextlib.suppress(Exception, asyncio.CancelledError):
                await writer.wait_closed()

    async def _send_raw(self, line: str) -> None:
        if self._writer is None:
            raise RuntimeError("Not connected")
        self._writer.write(f"{line}\r\n".encode())
        await self._writer.drain()

    async def _read_loop(self) -> None:
        try:
            while True:
                assert self._reader is not None
                data = await self._reader.readline()
                if not data:
                    break
                line = data.decode("utf-8", errors="replace").rstrip("\r\n")
                if line:
                    await self._dispatch_line(line)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.emit("error", e)
        finally:
            if self._state not in (ConnectStates.Disconnected, ConnectStates.Disconnecting):
                await self._cleanup()

    async def _send_loop(self) -> None:
        try:
            while True:
                line = await self._send_queue.get()
                await self._send_raw(line)
                await asyncio.sleep(self._rate_limit)
        except asyncio.CancelledError:
            pass

    async def _dispatch_line(self, line: str) -> None:
        try:
            prefix, command, params = _parse_irc_line(line)
        except (ValueError, IndexError):
            return

        match command:
            case "001":  # RPL_WELCOME
                self._set_state(ConnectStates.Connected)

            case "464":  # ERR_PASSWDMISMATCH
                self.emit("error", Exception("Bad password"))
                await self._cleanup()

            case "PING":
                server = params[0] if params else ""
                await self._send_raw(f"PONG :{server}")

            case "PRIVMSG":
                await self._handle_privmsg(prefix, params)

            case "JOIN":
                await self._handle_join(prefix, params)

            case "PART":
                await self._handle_part(prefix, params)

            case "QUIT":
                await self._handle_quit(prefix, params)

            case "403":  # ERR_NOSUCHCHANNEL
                channel = params[1] if len(params) > 1 else None
                self.emit("nochannel", channel)

            case "401":  # ERR_NOSUCHNICK
                nick = params[1] if len(params) > 1 else None
                self.emit("nouser", nick)

            case "404":  # ERR_CANNOTSENDTOCHAN (Bancho uses this for rejected messages)
                msg = params[-1] if params else None
                self.emit("rejectedMessage", msg)

    async def _handle_privmsg(self, prefix: str | None, params: list[str]) -> None:
        if not prefix or len(params) < 2:
            return
        sender_nick = prefix.split("!")[0]
        target = params[0]
        text = params[1]
        user = self.get_user(sender_nick)

        if target.casefold() == self.username.casefold():
            msg = PrivateMessage(user=user, message=text)
            user.emit("message", msg)
            self.emit("PM", msg)
        elif target.startswith("#"):
            channel = self.get_channel(target)
            msg = ChannelMessage(user=user, message=text, channel=channel)
            channel.emit("message", msg)
            self.emit("CM", msg)

    async def _handle_join(self, prefix: str | None, params: list[str]) -> None:
        if not prefix or not params:
            return
        user = self.get_user(prefix.split("!")[0])
        channel = self.get_channel(params[0])
        channel.members[user.username.casefold()] = BanchoChannelMember(user=user)
        channel.emit("JOIN", user)
        self.emit("JOIN", {"channel": channel, "user": user})

    async def _handle_part(self, prefix: str | None, params: list[str]) -> None:
        if not prefix or not params:
            return
        user = self.get_user(prefix.split("!")[0])
        channel = self.get_channel(params[0])
        channel.members.pop(user.username.casefold(), None)
        channel.emit("PART", user)
        self.emit("PART", {"channel": channel, "user": user})

    async def _handle_quit(self, prefix: str | None, params: list[str]) -> None:
        if not prefix:
            return
        user = self.get_user(prefix.split("!")[0])
        message = params[0] if params else None
        for channel in self._channels.values():
            if user.username.casefold() in channel.members:
                del channel.members[user.username.casefold()]
                channel.emit("PART", user)
        self.emit("QUIT", {"user": user, "message": message})

    def get_user(self, username: str) -> BanchoUser:
        key = username.casefold()
        if key not in self._users:
            self._users[key] = BanchoUser(self, username)
        return self._users[key]

    def get_channel(self, name: str) -> BanchoChannel:
        if name not in self._channels:
            if name.startswith("#mp_"):
                self._channels[name] = BanchoMultiplayerChannel(self, name)
            else:
                self._channels[name] = BanchoChannel(self, name)
        return self._channels[name]

    async def send_message(self, target: str, message: str) -> None:
        """Queue a PRIVMSG to a user or channel (rate-limited)."""
        await self._send_queue.put(f"PRIVMSG {target} :{message}")

    async def join_channel(self, name: str) -> None:
        await self._send_raw(f"JOIN {name}")

    async def part_channel(self, name: str) -> None:
        await self._send_raw(f"PART {name}")

    async def make_lobby(self, name: str, timeout: float = 10) -> BanchoLobby:
        from .lobby import BanchoLobby

        future: asyncio.Future[tuple[int, str]] = asyncio.get_event_loop().create_future()

        def on_pm(msg: PrivateMessage) -> None:
            if msg.user.username != "BanchoBot" or future.done():
                return
            import re
            m = re.match(
                r"Created the tournament match https://osu\.ppy\.sh/mp/(\d+) (.+)",
                msg.message,
            )
            if m:
                future.set_result((int(m.group(1)), m.group(2)))

        self.on("PM", on_pm)
        await self.send_message("BanchoBot", f"!mp make {name}")

        try:
            lobby_id, lobby_name = await asyncio.wait_for(future, timeout=timeout)
        finally:
            self.remove_listener("PM", on_pm)

        from .channel import BanchoMultiplayerChannel
        channel = self.get_channel(f"#mp_{lobby_id}")
        assert isinstance(channel, BanchoMultiplayerChannel)
        lobby = BanchoLobby(self, channel)
        lobby.name = lobby_name
        return lobby

    async def join_lobby(self, lobby_id: int) -> BanchoLobby:
        from .channel import BanchoMultiplayerChannel
        from .lobby import BanchoLobby

        channel_name = f"#mp_{lobby_id}"
        await self.join_channel(channel_name)
        channel = self.get_channel(channel_name)
        assert isinstance(channel, BanchoMultiplayerChannel)
        return BanchoLobby(self, channel)
