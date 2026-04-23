from bancho.enums import (
    BanchoGamemode,
    BanchoLobbyPlayerStates,
    BanchoLobbyTeamModes,
    BanchoLobbyTeams,
    BanchoLobbyWinConditions,
    ConnectStates,
    Mod,
)


class TestConnectStates:
    def test_values(self):
        assert ConnectStates.Disconnected.value == "Disconnected"
        assert ConnectStates.Connecting.value == "Connecting"
        assert ConnectStates.Connected.value == "Connected"
        assert ConnectStates.Disconnecting.value == "Disconnecting"


class TestBanchoLobbyTeamModes:
    def test_values(self):
        assert BanchoLobbyTeamModes.HeadToHead == 0
        assert BanchoLobbyTeamModes.TagCoop == 1
        assert BanchoLobbyTeamModes.TeamVs == 2
        assert BanchoLobbyTeamModes.TagTeamVs == 3


class TestBanchoLobbyWinConditions:
    def test_values(self):
        assert BanchoLobbyWinConditions.Score == 0
        assert BanchoLobbyWinConditions.Accuracy == 1
        assert BanchoLobbyWinConditions.Combo == 2
        assert BanchoLobbyWinConditions.ScoreV2 == 3


class TestBanchoLobbyTeams:
    def test_values(self):
        assert BanchoLobbyTeams.NoTeam == 0
        assert BanchoLobbyTeams.Blue == 1
        assert BanchoLobbyTeams.Red == 2


class TestBanchoLobbyPlayerStates:
    def test_values(self):
        assert BanchoLobbyPlayerStates.NotReady == 0
        assert BanchoLobbyPlayerStates.Ready == 1
        assert BanchoLobbyPlayerStates.NoMap == 2
        assert BanchoLobbyPlayerStates.Playing == 3


class TestBanchoGamemode:
    def test_values(self):
        assert BanchoGamemode.Osu == 0
        assert BanchoGamemode.Taiko == 1
        assert BanchoGamemode.CatchTheBeat == 2
        assert BanchoGamemode.OsuMania == 3


class TestMod:
    def test_nomod_is_zero(self):
        assert Mod.NoMod == 0

    def test_individual_values(self):
        assert Mod.Hidden == 8
        assert Mod.HardRock == 16
        assert Mod.DoubleTime == 64
        assert Mod.HalfTime == 256
        assert Mod.Flashlight == 1024

    def test_combination(self):
        hdhr = Mod.Hidden | Mod.HardRock
        assert hdhr == 24
        assert Mod.Hidden in hdhr
        assert Mod.HardRock in hdhr
        assert Mod.NoFail not in hdhr

    def test_from_int(self):
        assert Mod(24) == Mod.Hidden | Mod.HardRock

    def test_hddt(self):
        hddt = Mod.Hidden | Mod.DoubleTime
        assert Mod.Hidden in hddt
        assert Mod.DoubleTime in hddt
        assert Mod.HardRock not in hddt
