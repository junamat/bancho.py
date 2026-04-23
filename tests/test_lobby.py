from unittest.mock import AsyncMock, MagicMock

import pytest

from bancho import (
    BanchoClient,
    BanchoLobby,
    BanchoLobbyPlayer,
    BanchoLobbyPlayerScore,
)
from bancho.channel import BanchoMultiplayerChannel
from bancho.enums import (
    BanchoLobbyPlayerStates,
    BanchoLobbyTeamModes,
    BanchoLobbyTeams,
    BanchoLobbyWinConditions,
    Mod,
)
from bancho.lobby import _mods_to_str, _parse_mods


def make_lobby() -> tuple[BanchoClient, BanchoLobby]:
    client = BanchoClient("testbot", "secret")
    channel = BanchoMultiplayerChannel(client, "#mp_99999")
    lobby = BanchoLobby(client, channel)
    return client, lobby


def parse(lobby: BanchoLobby, text: str) -> None:
    lobby._parse(text)


class TestModHelpers:
    def test_mods_to_str_nomod(self):
        assert _mods_to_str(Mod.NoMod) == "None"

    def test_mods_to_str_single(self):
        assert _mods_to_str(Mod.Hidden) == "HD"

    def test_mods_to_str_combo(self):
        result = _mods_to_str(Mod.Hidden | Mod.HardRock)
        assert "HD" in result
        assert "HR" in result

    def test_parse_mods_nomod(self):
        mods, freemod = _parse_mods("None")
        assert mods == Mod.NoMod
        assert not freemod

    def test_parse_mods_single(self):
        mods, freemod = _parse_mods("HD")
        assert mods == Mod.Hidden
        assert not freemod

    def test_parse_mods_combo(self):
        mods, freemod = _parse_mods("HD HR")
        assert Mod.Hidden in mods
        assert Mod.HardRock in mods

    def test_parse_mods_freemod(self):
        mods, freemod = _parse_mods("HD Freemod")
        assert freemod
        assert Mod.Hidden in mods

    def test_parse_mods_freemod_only(self):
        mods, freemod = _parse_mods("Freemod")
        assert mods == Mod.NoMod
        assert freemod


class TestLobbySetup:
    def test_initial_state(self):
        _, lobby = make_lobby()
        assert lobby.id == 99999
        assert lobby.slots == [None] * 16
        assert not lobby.playing
        assert lobby.host is None
        assert lobby.scores == []

    def test_get_history_url(self):
        _, lobby = make_lobby()
        assert lobby.get_history_url() == "https://osu.ppy.sh/mp/99999"

    def test_lobby_id_from_channel(self):
        _, lobby = make_lobby()
        assert lobby.id == 99999


class TestPlayerJoined:
    def test_basic_join(self):
        _, lobby = make_lobby()
        events = []
        lobby.on("playerJoined", events.append)

        parse(lobby, "player1 joined in slot 3.")

        assert len(events) == 1
        ev = events[0]
        assert ev["player"].user.username == "player1"
        assert ev["slot"] == 3
        assert ev["team"] == BanchoLobbyTeams.NoTeam

    def test_join_fills_slot(self):
        _, lobby = make_lobby()

        parse(lobby, "player1 joined in slot 2.")

        assert lobby.slots[1] is not None
        assert lobby.slots[1].user.username == "player1"

    def test_join_with_team(self):
        _, lobby = make_lobby()
        events = []
        lobby.on("playerJoined", events.append)

        parse(lobby, "player1 joined in slot 1 for team Red.")

        assert events[0]["team"] == BanchoLobbyTeams.Red

    def test_join_blue_team(self):
        _, lobby = make_lobby()
        events = []
        lobby.on("playerJoined", events.append)

        parse(lobby, "player1 joined in slot 1 for team Blue.")

        assert events[0]["team"] == BanchoLobbyTeams.Blue

    def test_username_with_spaces(self):
        _, lobby = make_lobby()

        parse(lobby, "Cool Player joined in slot 5.")

        assert lobby.slots[4].user.username == "Cool Player"


class TestPlayerLeft:
    def test_player_left_emits_event(self):
        _, lobby = make_lobby()
        events = []
        lobby.on("playerLeft", events.append)

        parse(lobby, "player1 joined in slot 1.")
        parse(lobby, "player1 left the game.")

        assert len(events) == 1
        assert isinstance(events[0], BanchoLobbyPlayer)
        assert events[0].user.username == "player1"

    def test_player_left_clears_slot(self):
        _, lobby = make_lobby()

        parse(lobby, "player1 joined in slot 1.")
        parse(lobby, "player1 left the game.")

        assert lobby.slots[0] is None

    def test_unknown_player_left_no_event(self):
        _, lobby = make_lobby()
        events = []
        lobby.on("playerLeft", events.append)

        parse(lobby, "ghost left the game.")

        assert events == []


class TestPlayerMoved:
    def test_player_moved(self):
        _, lobby = make_lobby()
        events = []
        lobby.on("playerMoved", events.append)

        parse(lobby, "player1 joined in slot 1.")
        parse(lobby, "player1 moved to slot 5.")

        assert len(events) == 1
        assert events[0]["slot"] == 5
        assert lobby.slots[0] is None
        assert lobby.slots[4] is not None


class TestTeamChange:
    def test_player_changed_team(self):
        _, lobby = make_lobby()
        events = []
        lobby.on("playerChangedTeam", events.append)

        parse(lobby, "player1 joined in slot 1.")
        parse(lobby, "player1 changed to Red.")

        assert len(events) == 1
        assert events[0]["team"] == BanchoLobbyTeams.Red
        assert lobby.slots[0].team == BanchoLobbyTeams.Red


class TestHost:
    def test_host_changed(self):
        _, lobby = make_lobby()
        events = []
        lobby.on("host", events.append)

        parse(lobby, "player1 joined in slot 1.")
        parse(lobby, "player1 became the host.")

        assert len(events) == 1
        assert events[0].user.username == "player1"
        assert lobby.slots[0].is_host is True
        assert lobby.host is lobby.slots[0]

    def test_host_cleared(self):
        _, lobby = make_lobby()
        events = []
        lobby.on("hostCleared", lambda: events.append(True))

        parse(lobby, "player1 joined in slot 1.")
        parse(lobby, "player1 became the host.")
        parse(lobby, "Cleared match host")

        assert events == [True]
        assert lobby.host is None

    def test_only_one_host_at_a_time(self):
        _, lobby = make_lobby()

        parse(lobby, "player1 joined in slot 1.")
        parse(lobby, "player2 joined in slot 2.")
        parse(lobby, "player1 became the host.")
        parse(lobby, "player2 became the host.")

        assert lobby.slots[0].is_host is False
        assert lobby.slots[1].is_host is True


class TestMatchEvents:
    def test_match_started(self):
        _, lobby = make_lobby()
        events = []
        lobby.on("matchStarted", lambda: events.append(True))

        parse(lobby, "The match has started!")

        assert events == [True]
        assert lobby.playing is True

    def test_match_finished(self):
        _, lobby = make_lobby()
        events = []
        lobby.on("matchFinished", events.append)

        parse(lobby, "The match has started!")
        parse(lobby, "The match has finished!")

        assert len(events) == 1
        assert lobby.playing is False

    def test_match_aborted(self):
        _, lobby = make_lobby()
        events = []
        lobby.on("matchAborted", lambda: events.append(True))

        parse(lobby, "The match has started!")
        parse(lobby, "Aborted the match")

        assert events == [True]
        assert lobby.playing is False

    def test_all_players_ready(self):
        _, lobby = make_lobby()
        events = []
        lobby.on("allPlayersReady", lambda: events.append(True))

        parse(lobby, "All players are ready")

        assert events == [True]

    def test_scores_cleared_on_match_start(self):
        _, lobby = make_lobby()

        parse(lobby, "player1 joined in slot 1.")
        parse(lobby, "The match has started!")
        parse(lobby, "player1 finished playing (Score: 100000, PASSED).")
        parse(lobby, "The match has finished!")
        parse(lobby, "The match has started!")

        assert lobby.scores == []


class TestPlayerFinished:
    def test_player_finished_passed(self):
        _, lobby = make_lobby()
        events = []
        lobby.on("playerFinished", events.append)

        parse(lobby, "player1 joined in slot 1.")
        parse(lobby, "player1 finished playing (Score: 1234567, PASSED).")

        assert len(events) == 1
        score = events[0]
        assert isinstance(score, BanchoLobbyPlayerScore)
        assert score.score == 1234567
        assert score.passed is True

    def test_player_finished_failed(self):
        _, lobby = make_lobby()
        events = []
        lobby.on("playerFinished", events.append)

        parse(lobby, "player1 joined in slot 1.")
        parse(lobby, "player1 finished playing (Score: 500, FAILED).")

        assert events[0].passed is False

    def test_match_finished_scores_sorted(self):
        _, lobby = make_lobby()
        results = []
        lobby.on("matchFinished", results.append)

        parse(lobby, "player1 joined in slot 1.")
        parse(lobby, "player2 joined in slot 2.")
        parse(lobby, "The match has started!")
        parse(lobby, "player1 finished playing (Score: 500000, PASSED).")
        parse(lobby, "player2 finished playing (Score: 800000, PASSED).")
        parse(lobby, "The match has finished!")

        scores = results[0]
        assert scores[0].score == 800000
        assert scores[1].score == 500000


class TestBeatmap:
    def test_beatmap_changed(self):
        _, lobby = make_lobby()
        events = []
        lobby.on("beatmapId", events.append)

        parse(lobby, "Beatmap changed to: Artist - Title [Diff] https://osu.ppy.sh/b/12345")

        assert events == [12345]
        assert lobby.beatmap_id == 12345

    def test_invalid_beatmap(self):
        _, lobby = make_lobby()
        events = []
        lobby.on("invalidBeatmapId", lambda: events.append(True))

        parse(lobby, "Invalid map id")

        assert events == [True]


class TestPasswordEvents:
    def test_password_changed(self):
        _, lobby = make_lobby()
        events = []
        lobby.on("passwordChanged", lambda: events.append(True))

        parse(lobby, "Changed the match password")

        assert events == [True]

    def test_password_removed(self):
        _, lobby = make_lobby()
        events = []
        lobby.on("passwordRemoved", lambda: events.append(True))

        parse(lobby, "Removed the match password")

        assert events == [True]


class TestSlotEvents:
    def test_slots_locked(self):
        _, lobby = make_lobby()
        events = []
        lobby.on("slotsLocked", lambda: events.append(True))

        parse(lobby, "The match is locked.")

        assert events == [True]

    def test_slots_unlocked(self):
        _, lobby = make_lobby()
        events = []
        lobby.on("slotsUnlocked", lambda: events.append(True))

        parse(lobby, "The match is unlocked.")

        assert events == [True]


class TestRefereeEvents:
    def test_ref_added(self):
        _, lobby = make_lobby()
        events = []
        lobby.on("refereeAdded", events.append)

        parse(lobby, "Added player1 to the match referees")

        assert events == ["player1"]

    def test_ref_removed(self):
        _, lobby = make_lobby()
        events = []
        lobby.on("refereeRemoved", events.append)

        parse(lobby, "Removed player1 from the match referees")

        assert events == ["player1"]


class TestUserNotFound:
    def test_user_not_found(self):
        _, lobby = make_lobby()
        username_events = []
        lobby.on("userNotFoundUsername", username_events.append)
        notfound_events = []
        lobby.on("userNotFound", lambda: notfound_events.append(True))

        parse(lobby, "User not found: ghost_user")

        assert username_events == ["ghost_user"]
        assert notfound_events == [True]


class TestTimerEvents:
    def test_start_timer_tick(self):
        _, lobby = make_lobby()
        events = []
        lobby.on("startTimerTick", events.append)

        parse(lobby, "Match starts in 30 seconds")

        assert events == [{"seconds": 30}]

    def test_start_timer_aborted(self):
        _, lobby = make_lobby()
        events = []
        lobby.on("startTimerAborted", lambda: events.append(True))

        parse(lobby, "Aborted the countdown")

        assert events == [True]

    def test_timer_ended(self):
        _, lobby = make_lobby()
        events = []
        lobby.on("timerEnded", lambda: events.append(True))

        parse(lobby, "Countdown finished")

        assert events == [True]


class TestSettingsParsing:
    def test_room_name(self):
        _, lobby = make_lobby()
        events = []
        lobby.on("name", events.append)

        parse(lobby, "Room name: My Lobby, History: https://osu.ppy.sh/mp/99999")

        assert lobby.name == "My Lobby"
        assert events == ["My Lobby"]

    def test_team_mode_and_win_condition(self):
        _, lobby = make_lobby()

        parse(lobby, "Team mode: TeamVs, Win condition: ScoreV2")

        assert lobby.team_mode == BanchoLobbyTeamModes.TeamVs
        assert lobby.win_condition == BanchoLobbyWinConditions.ScoreV2

    def test_active_mods(self):
        _, lobby = make_lobby()

        parse(lobby, "Active mods: HD HR")

        assert Mod.Hidden in lobby.mods
        assert Mod.HardRock in lobby.mods

    def test_match_settings_event(self):
        _, lobby = make_lobby()
        events = []
        lobby.on("matchSettings", events.append)

        parse(lobby, "Team mode: HeadToHead, Win condition: Score")
        parse(lobby, "Players: 4")

        assert len(events) == 1
        ev = events[0]
        assert "team_mode" in ev
        assert "win_condition" in ev

    def test_slot_parsing(self):
        _, lobby = make_lobby()

        parse(lobby, "Slot 1  Not Ready https://osu.ppy.sh/u/123456 PlayerOne  ")

        assert lobby.slots[0] is not None
        assert lobby.slots[0].state == BanchoLobbyPlayerStates.NotReady
