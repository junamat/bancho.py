import pytest
from unittest.mock import AsyncMock

from bancho import BanchoClient, ConnectStates
from bancho.client import _parse_irc_line


class TestParseIrcLine:
    def test_simple_command(self):
        prefix, cmd, params = _parse_irc_line("PING cho.ppy.sh")
        assert prefix is None
        assert cmd == "PING"
        assert params == ["cho.ppy.sh"]

    def test_ping_with_colon(self):
        prefix, cmd, params = _parse_irc_line("PING :cho.ppy.sh")
        assert prefix is None
        assert cmd == "PING"
        assert params == ["cho.ppy.sh"]

    def test_server_welcome(self):
        prefix, cmd, params = _parse_irc_line(
            ":cho.ppy.sh 001 testbot :Welcome to the osu! IRC server testbot"
        )
        assert prefix == "cho.ppy.sh"
        assert cmd == "001"
        assert params == ["testbot", "Welcome to the osu! IRC server testbot"]

    def test_privmsg_to_user(self):
        prefix, cmd, params = _parse_irc_line(":player!cho@ppy.sh PRIVMSG bot :hello world")
        assert prefix == "player!cho@ppy.sh"
        assert cmd == "PRIVMSG"
        assert params == ["bot", "hello world"]

    def test_privmsg_preserves_colons_in_message(self):
        prefix, cmd, params = _parse_irc_line(":player!cho@ppy.sh PRIVMSG #mp_1 :hello: colon message")
        assert params[-1] == "hello: colon message"

    def test_join_with_trailing(self):
        prefix, cmd, params = _parse_irc_line(":user!cho@ppy.sh JOIN :#mp_12345")
        assert cmd == "JOIN"
        assert params == ["#mp_12345"]

    def test_part_with_message(self):
        prefix, cmd, params = _parse_irc_line(":user!cho@ppy.sh PART #osu :leaving")
        assert cmd == "PART"
        assert params == ["#osu", "leaving"]

    def test_quit_with_message(self):
        prefix, cmd, params = _parse_irc_line(":user!cho@ppy.sh QUIT :disconnected")
        assert cmd == "QUIT"
        assert params == ["disconnected"]

    def test_error_reply_params(self):
        prefix, cmd, params = _parse_irc_line(":cho.ppy.sh 401 bot unknownuser :No such nick")
        assert cmd == "401"
        assert params == ["bot", "unknownuser", "No such nick"]


class TestBanchoClientState:
    def test_initial_state_is_disconnected(self):
        client = BanchoClient("bot", "pass")
        assert client.state == ConnectStates.Disconnected

    def test_set_state_emits_state_event(self):
        client = BanchoClient("bot", "pass")
        received = []
        client.on("state", received.append)

        client._set_state(ConnectStates.Connecting)

        assert received == [ConnectStates.Connecting]

    def test_set_state_connected_emits_connected(self):
        client = BanchoClient("bot", "pass")
        fired = []
        client.on("connected", lambda: fired.append(True))

        client._set_state(ConnectStates.Connected)

        assert fired == [True]

    def test_set_state_disconnected_emits_disconnected(self):
        client = BanchoClient("bot", "pass")
        fired = []
        client.on("disconnected", lambda: fired.append(True))

        client._set_state(ConnectStates.Disconnected)

        assert fired == [True]

    async def test_connect_raises_if_already_connected(self):
        client = BanchoClient("bot", "pass")
        client._state = ConnectStates.Connected

        with pytest.raises(RuntimeError, match="Cannot connect"):
            await client.connect()

    async def test_connect_raises_if_connecting(self):
        client = BanchoClient("bot", "pass")
        client._state = ConnectStates.Connecting

        with pytest.raises(RuntimeError, match="Cannot connect"):
            await client.connect()


class TestBanchoClientDispatch:
    def make_client(self) -> BanchoClient:
        return BanchoClient("testbot", "secret")

    async def test_welcome_sets_connected_state(self):
        client = self.make_client()

        await client._dispatch_line(":cho.ppy.sh 001 testbot :Welcome")

        assert client.state == ConnectStates.Connected

    async def test_welcome_emits_connected_event(self):
        client = self.make_client()
        fired = []
        client.on("connected", lambda: fired.append(True))

        await client._dispatch_line(":cho.ppy.sh 001 testbot :Welcome")

        assert fired == [True]

    async def test_ping_sends_pong(self):
        client = self.make_client()
        client._send_raw = AsyncMock()

        await client._dispatch_line("PING :cho.ppy.sh")

        client._send_raw.assert_called_once_with("PONG :cho.ppy.sh")

    async def test_pm_event(self):
        client = self.make_client()
        received = []
        client.on("PM", received.append)

        await client._dispatch_line(":player1!cho@ppy.sh PRIVMSG testbot :hey bot")

        assert received == [{"user": "player1", "message": "hey bot"}]

    async def test_pm_username_match_is_case_insensitive(self):
        client = self.make_client()
        received = []
        client.on("PM", received.append)

        await client._dispatch_line(":player1!cho@ppy.sh PRIVMSG TESTBOT :hey")

        assert len(received) == 1

    async def test_pm_with_spaces_in_message(self):
        client = self.make_client()
        received = []
        client.on("PM", received.append)

        await client._dispatch_line(":player1!cho@ppy.sh PRIVMSG testbot :hello world how are you")

        assert received[0]["message"] == "hello world how are you"

    async def test_cm_event(self):
        client = self.make_client()
        received = []
        client.on("CM", received.append)

        await client._dispatch_line(":player1!cho@ppy.sh PRIVMSG #osu :hello channel")

        assert received == [{"channel": "#osu", "user": "player1", "message": "hello channel"}]

    async def test_cm_not_emitted_for_pm(self):
        client = self.make_client()
        cm_received = []
        client.on("CM", cm_received.append)

        await client._dispatch_line(":player1!cho@ppy.sh PRIVMSG testbot :private")

        assert cm_received == []

    async def test_pm_not_emitted_for_cm(self):
        client = self.make_client()
        pm_received = []
        client.on("PM", pm_received.append)

        await client._dispatch_line(":player1!cho@ppy.sh PRIVMSG #osu :channel message")

        assert pm_received == []

    async def test_join_event(self):
        client = self.make_client()
        received = []
        client.on("JOIN", received.append)

        await client._dispatch_line(":player1!cho@ppy.sh JOIN :#mp_12345")

        assert received == [{"channel": "#mp_12345", "user": "player1"}]

    async def test_part_event(self):
        client = self.make_client()
        received = []
        client.on("PART", received.append)

        await client._dispatch_line(":player1!cho@ppy.sh PART #osu :leaving")

        assert received == [{"channel": "#osu", "user": "player1"}]

    async def test_quit_event(self):
        client = self.make_client()
        received = []
        client.on("QUIT", received.append)

        await client._dispatch_line(":player1!cho@ppy.sh QUIT :disconnected")

        assert received == [{"user": "player1", "message": "disconnected"}]

    async def test_quit_without_message(self):
        client = self.make_client()
        received = []
        client.on("QUIT", received.append)

        await client._dispatch_line(":player1!cho@ppy.sh QUIT")

        assert received == [{"user": "player1", "message": None}]

    async def test_nouser_event(self):
        client = self.make_client()
        received = []
        client.on("nouser", received.append)

        await client._dispatch_line(":cho.ppy.sh 401 testbot unknownuser :No such nick")

        assert received == ["unknownuser"]

    async def test_nochannel_event(self):
        client = self.make_client()
        received = []
        client.on("nochannel", received.append)

        await client._dispatch_line(":cho.ppy.sh 403 testbot #nonexistent :No such channel")

        assert received == ["#nonexistent"]

    async def test_bad_password_emits_error(self):
        client = self.make_client()
        client._cleanup = AsyncMock()
        errors = []
        client.on("error", errors.append)

        await client._dispatch_line(":cho.ppy.sh 464 * :Bad authentication token")

        assert len(errors) == 1
        assert "Bad password" in str(errors[0])

    async def test_bad_password_calls_cleanup(self):
        client = self.make_client()
        client._cleanup = AsyncMock()
        client.on("error", lambda _: None)  # prevent pyee from re-raising

        await client._dispatch_line(":cho.ppy.sh 464 * :Bad authentication token")

        client._cleanup.assert_called_once()

    async def test_rejected_message_event(self):
        client = self.make_client()
        received = []
        client.on("rejectedMessage", received.append)

        await client._dispatch_line(":cho.ppy.sh 404 testbot #channel :Cannot send to channel")

        assert len(received) == 1

    async def test_unknown_command_is_silently_ignored(self):
        client = self.make_client()
        # Should not raise
        await client._dispatch_line(":cho.ppy.sh 372 testbot :- Message of the day")


class TestSendMessage:
    async def test_queues_privmsg(self):
        client = BanchoClient("bot", "pass")

        await client.send_message("#osu", "hello there")

        assert not client._send_queue.empty()
        assert client._send_queue.get_nowait() == "PRIVMSG #osu :hello there"

    async def test_queues_multiple_in_order(self):
        client = BanchoClient("bot", "pass")

        await client.send_message("user1", "first")
        await client.send_message("user2", "second")

        assert client._send_queue.get_nowait() == "PRIVMSG user1 :first"
        assert client._send_queue.get_nowait() == "PRIVMSG user2 :second"

    async def test_message_with_spaces(self):
        client = BanchoClient("bot", "pass")

        await client.send_message("#mp_1", "Match starting in 10 seconds!")

        assert client._send_queue.get_nowait() == "PRIVMSG #mp_1 :Match starting in 10 seconds!"
