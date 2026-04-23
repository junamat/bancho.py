from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from pyee.asyncio import AsyncIOEventEmitter

from .enums import (
    BanchoGamemode,
    BanchoLobbyPlayerStates,
    BanchoLobbyTeamModes,
    BanchoLobbyTeams,
    BanchoLobbyWinConditions,
    Mod,
)

if TYPE_CHECKING:
    from .channel import BanchoMultiplayerChannel
    from .client import BanchoClient
    from .messages import ChannelMessage
    from .user import BanchoUser


# ── BanchoBot message patterns ────────────────────────────────────────────────

_RE_PLAYER_JOINED = re.compile(r"^(.+) joined in slot (\d+)\.$")
_RE_PLAYER_JOINED_TEAM = re.compile(r"^(.+) joined in slot (\d+) for team (Red|Blue)\.$")
_RE_PLAYER_LEFT = re.compile(r"^(.+) left the game\.$")
_RE_PLAYER_FINISHED = re.compile(r"^(.+) finished playing \(Score: (\d+), (PASSED|FAILED)\)\.$")
_RE_PLAYER_MOVED = re.compile(r"^(.+) moved to slot (\d+)\.$")
_RE_PLAYER_TEAM = re.compile(r"^(.+) changed to (Blue|Red)\.$")
_RE_HOST = re.compile(r"^(.+) became the host\.$")
_RE_BEATMAP_CHANGED = re.compile(r"Beatmap changed to: .+https://osu\.ppy\.sh/b/(\d+)")
_RE_REF_BEATMAP_CHANGED = re.compile(r"^Changed beatmap to https://osu\.ppy\.sh/b/(\d+) .+$")
_RE_REF_ADDED = re.compile(r"^Added (.+) to the match referees$")
_RE_REF_REMOVED = re.compile(r"^Removed (.+) from the match referees$")
_RE_USER_NOT_FOUND = re.compile(r"^User not found: (.+)$")
_RE_START_TIMER_TICK = re.compile(r"^Match starts in (\d+) seconds?$")
_RE_START_TIMER_STARTED = re.compile(r"^Queued the match to start in (\d+) seconds?$")
_RE_TIMER_STARTED = re.compile(r"^Countdown ends in (\d+) seconds?$")
_RE_SETTINGS_ROOM = re.compile(r"^Room name: (.+), History: https://osu\.ppy\.sh/mp/\d+$")
_RE_SETTINGS_BEATMAP = re.compile(r"^Beatmap: https://osu\.ppy\.sh/b/(\d+) .+$")
_RE_SETTINGS_MODES = re.compile(r"^Team mode: (.+), Win condition: (.+)$")
_RE_SETTINGS_MODS = re.compile(r"^Active mods: (.+)$")
_RE_SETTINGS_PLAYERS = re.compile(r"^Players: (\d+)$")
_RE_SETTINGS_SLOT = re.compile(
    r"^Slot (\d+)\s+(Not Ready|Ready|No Map|Playing)\s+https://osu\.ppy\.sh/u/\d+\s+(.+?)(?:\s+\[.+\])?$"
)


# ── Mod helpers ───────────────────────────────────────────────────────────────

_MOD_ABBREVS: dict[Mod, str] = {
    Mod.NoFail: "NF",
    Mod.Easy: "EZ",
    Mod.Hidden: "HD",
    Mod.HardRock: "HR",
    Mod.SuddenDeath: "SD",
    Mod.DoubleTime: "DT",
    Mod.Relax: "RX",
    Mod.HalfTime: "HT",
    Mod.Nightcore: "NC",
    Mod.Flashlight: "FL",
    Mod.SpunOut: "SO",
    Mod.Autopilot: "AP",
    Mod.Perfect: "PF",
    Mod.FadeIn: "FI",
    Mod.Mirror: "MR",
    Mod.ScoreV2: "SV2",
    Mod.Key1: "1K",
    Mod.Key2: "2K",
    Mod.Key3: "3K",
    Mod.Key4: "4K",
    Mod.Key5: "5K",
    Mod.Key6: "6K",
    Mod.Key7: "7K",
    Mod.Key8: "8K",
    Mod.Key9: "9K",
}

_ABBREV_TO_MOD: dict[str, Mod] = {v: k for k, v in _MOD_ABBREVS.items()}

_TEAM_MODE_STRINGS: dict[str, BanchoLobbyTeamModes] = {
    "HeadToHead": BanchoLobbyTeamModes.HeadToHead,
    "TagCoop": BanchoLobbyTeamModes.TagCoop,
    "TeamVs": BanchoLobbyTeamModes.TeamVs,
    "TagTeamVs": BanchoLobbyTeamModes.TagTeamVs,
}

_WIN_CONDITION_STRINGS: dict[str, BanchoLobbyWinConditions] = {
    "Score": BanchoLobbyWinConditions.Score,
    "Accuracy": BanchoLobbyWinConditions.Accuracy,
    "Combo": BanchoLobbyWinConditions.Combo,
    "ScoreV2": BanchoLobbyWinConditions.ScoreV2,
}

_PLAYER_STATE_STRINGS: dict[str, BanchoLobbyPlayerStates] = {
    "Not Ready": BanchoLobbyPlayerStates.NotReady,
    "Ready": BanchoLobbyPlayerStates.Ready,
    "No Map": BanchoLobbyPlayerStates.NoMap,
    "Playing": BanchoLobbyPlayerStates.Playing,
}


def _mods_to_str(mods: Mod) -> str:
    if mods == Mod.NoMod:
        return "None"
    return " ".join(abbr for mod, abbr in _MOD_ABBREVS.items() if mod in mods)


def _parse_mods(mod_str: str) -> tuple[Mod, bool]:
    freemod = "Freemod" in mod_str
    combined = Mod.NoMod
    for part in mod_str.replace(",", " ").split():
        if part in ("None", "Freemod"):
            continue
        if mod := _ABBREV_TO_MOD.get(part):
            combined |= mod
    return combined, freemod


# ── Data types ────────────────────────────────────────────────────────────────

@dataclass
class BanchoLobbyPlayer:
    lobby: BanchoLobby
    user: BanchoUser
    slot: int  # 1-indexed, matches Bancho slot numbers
    team: BanchoLobbyTeams = BanchoLobbyTeams.NoTeam
    state: BanchoLobbyPlayerStates = BanchoLobbyPlayerStates.NotReady
    mods: Mod = Mod.NoMod
    is_host: bool = False


@dataclass
class BanchoLobbyPlayerScore:
    player: BanchoLobbyPlayer
    score: int
    passed: bool


# ── BanchoLobby ───────────────────────────────────────────────────────────────

class BanchoLobby(AsyncIOEventEmitter):
    """Represents an osu! multiplayer lobby.

    Events:
        allPlayersReady: All players are ready.
        beatmapId (int): Beatmap ID changed.
        invalidBeatmapId: Selected beatmap ID is invalid.
        beatmapNotFound: Selected beatmap not found.
        freemod (bool): Freemod toggled.
        host (BanchoLobbyPlayer): Host changed.
        hostCleared: Host cleared.
        matchStarted: Match started.
        matchFinished (list[BanchoLobbyPlayerScore]): Match finished with sorted scores.
        matchAborted: Match aborted.
        matchSettings (dict): Room settings updated (from !mp settings).
        mods (Mod): Mods changed.
        name (str): Room name changed.
        passwordChanged: Password set.
        passwordRemoved: Password cleared.
        playerChangedTeam (dict): Keys: player, team.
        playerFinished (BanchoLobbyPlayerScore): Player finished the map.
        playerJoined (dict): Keys: player, slot, team.
        playerLeft (BanchoLobbyPlayer): Player left.
        playerMoved (dict): Keys: player, slot.
        refereeAdded (str): Referee added.
        refereeRemoved (str): Referee removed.
        size (int): Slot count changed.
        slotsLocked: Slots locked.
        slotsUnlocked: Slots unlocked.
        startTimerStarted (int): Match countdown started (seconds).
        startTimerTick (dict): Match countdown tick. Keys: seconds.
        startTimerAborted: Match countdown aborted.
        teamMode (BanchoLobbyTeamModes): Team mode changed.
        timerAborted: General timer aborted.
        timerEnded: General timer ended.
        timerTick (dict): General timer tick. Keys: seconds.
        userNotFound: A !mp command targeted a user that wasn't found.
        userNotFoundUsername (str): Username that wasn't found.
        winCondition (BanchoLobbyWinConditions): Win condition changed.
    """

    def __init__(self, client: BanchoClient, channel: BanchoMultiplayerChannel) -> None:
        super().__init__()
        self._client = client
        self.channel = channel
        self.id: int = channel.lobby_id

        self.name: str = ""
        self.size: int = 16
        self.beatmap_id: int | None = None
        self.team_mode: BanchoLobbyTeamModes = BanchoLobbyTeamModes.HeadToHead
        self.win_condition: BanchoLobbyWinConditions = BanchoLobbyWinConditions.Score
        self.mods: Mod = Mod.NoMod
        self.freemod: bool = False
        self.playing: bool = False
        self.slots: list[BanchoLobbyPlayer | None] = [None] * 16
        self.scores: list[BanchoLobbyPlayerScore] = []

        channel.on("message", self._on_channel_message)

    # ── internals ─────────────────────────────────────────────────────────────

    async def _send_command(self, command: str) -> None:
        await self.channel.send_message(f"!mp {command}")

    async def _on_channel_message(self, msg: ChannelMessage) -> None:
        if msg.user.username != "BanchoBot":
            return
        self._parse(msg.message)

    def _get_player_by_name(self, name: str) -> BanchoLobbyPlayer | None:
        name_cf = name.casefold()
        name_norm = name.replace(" ", "_").casefold()
        for slot in self.slots:
            if slot is None:
                continue
            un = slot.user.username
            if un.casefold() == name_cf or un.replace(" ", "_").casefold() == name_norm:
                return slot
        return None

    def _place(self, player: BanchoLobbyPlayer) -> None:
        idx = player.slot - 1
        if 0 <= idx < 16:
            self.slots[idx] = player

    def _evict(self, player: BanchoLobbyPlayer) -> None:
        idx = player.slot - 1
        if 0 <= idx < 16 and self.slots[idx] is player:
            self.slots[idx] = None

    def _handle_player_joined(self, username: str, slot: int, team: BanchoLobbyTeams) -> None:
        user = self._client.get_user(username)
        player = BanchoLobbyPlayer(lobby=self, user=user, slot=slot, team=team)
        self._place(player)
        self.emit("playerJoined", {"player": player, "slot": slot, "team": team})

    def _parse(self, text: str) -> None:  # noqa: PLR0912
        if m := _RE_PLAYER_JOINED_TEAM.match(text):
            team = BanchoLobbyTeams.Red if m.group(3) == "Red" else BanchoLobbyTeams.Blue
            self._handle_player_joined(m.group(1), int(m.group(2)), team)

        elif m := _RE_PLAYER_JOINED.match(text):
            self._handle_player_joined(m.group(1), int(m.group(2)), BanchoLobbyTeams.NoTeam)

        elif m := _RE_PLAYER_LEFT.match(text):
            if player := self._get_player_by_name(m.group(1)):
                self._evict(player)
                self.emit("playerLeft", player)

        elif m := _RE_PLAYER_FINISHED.match(text):
            if player := self._get_player_by_name(m.group(1)):
                score = BanchoLobbyPlayerScore(
                    player=player,
                    score=int(m.group(2)),
                    passed=m.group(3) == "PASSED",
                )
                self.scores.append(score)
                self.emit("playerFinished", score)

        elif m := _RE_PLAYER_MOVED.match(text):
            if player := self._get_player_by_name(m.group(1)):
                self._evict(player)
                player.slot = int(m.group(2))
                self._place(player)
                self.emit("playerMoved", {"player": player, "slot": player.slot})

        elif m := _RE_PLAYER_TEAM.match(text):
            if player := self._get_player_by_name(m.group(1)):
                player.team = BanchoLobbyTeams.Red if m.group(2) == "Red" else BanchoLobbyTeams.Blue
                self.emit("playerChangedTeam", {"player": player, "team": player.team})

        elif m := _RE_HOST.match(text):
            if player := self._get_player_by_name(m.group(1)):
                for s in self.slots:
                    if s:
                        s.is_host = False
                player.is_host = True
                self.emit("host", player)

        elif text == "Cleared match host":
            for s in self.slots:
                if s:
                    s.is_host = False
            self.emit("hostCleared")

        elif text == "The match has started!":
            self.playing = True
            self.scores = []
            self.emit("matchStarted")

        elif text == "The match has finished!":
            self.playing = False
            self.scores.sort(key=lambda s: s.score if s.passed else -1, reverse=True)
            self.emit("matchFinished", list(self.scores))

        elif text == "Aborted the match":
            self.playing = False
            self.emit("matchAborted")

        elif text == "All players are ready":
            self.emit("allPlayersReady")

        elif m := _RE_BEATMAP_CHANGED.search(text):
            self.beatmap_id = int(m.group(1))
            self.emit("beatmapId", self.beatmap_id)

        elif m := _RE_REF_BEATMAP_CHANGED.match(text):
            self.beatmap_id = int(m.group(1))
            self.emit("beatmapId", self.beatmap_id)

        elif text == "Invalid map ID provided":
            self.emit("invalidBeatmapId")

        elif text == "Changed the match password":
            self.emit("passwordChanged")

        elif text == "Removed the match password":
            self.emit("passwordRemoved")

        elif text == "Locked the match":
            self.emit("slotsLocked")

        elif text == "Unlocked the match":
            self.emit("slotsUnlocked")

        elif m := _RE_REF_ADDED.match(text):
            self.emit("refereeAdded", m.group(1))

        elif m := _RE_REF_REMOVED.match(text):
            self.emit("refereeRemoved", m.group(1))

        elif m := _RE_USER_NOT_FOUND.match(text):
            self.emit("userNotFoundUsername", m.group(1))
            self.emit("userNotFound")

        elif m := _RE_START_TIMER_STARTED.match(text):
            self.emit("startTimerStarted", int(m.group(1)))

        elif m := _RE_START_TIMER_TICK.match(text):
            self.emit("startTimerTick", {"seconds": int(m.group(1))})

        elif m := _RE_TIMER_STARTED.match(text):
            self.emit("startTimerStarted", int(m.group(1)))
            self.emit("timerTick", {"seconds": int(m.group(1))})

        elif text in ("Aborted the match start timer", "Countdown aborted"):
            self.emit("startTimerAborted")
            self.emit("timerAborted")

        elif text == "Countdown finished":
            self.emit("timerEnded")

        # !mp settings response lines
        elif m := _RE_SETTINGS_ROOM.match(text):
            self.name = m.group(1)
            self.emit("name", self.name)

        elif m := _RE_SETTINGS_BEATMAP.match(text):
            self.beatmap_id = int(m.group(1))

        elif m := _RE_SETTINGS_MODES.match(text):
            if tm := _TEAM_MODE_STRINGS.get(m.group(1)):
                self.team_mode = tm
                self.emit("teamMode", self.team_mode)
            if wc := _WIN_CONDITION_STRINGS.get(m.group(2)):
                self.win_condition = wc
                self.emit("winCondition", self.win_condition)

        elif m := _RE_SETTINGS_MODS.match(text):
            self.mods, self.freemod = _parse_mods(m.group(1))
            self.emit("mods", self.mods)
            self.emit("freemod", self.freemod)

        elif m := _RE_SETTINGS_PLAYERS.match(text):
            self.emit("matchSettings", {
                "size": self.size,
                "team_mode": self.team_mode,
                "win_condition": self.win_condition,
            })

        elif m := _RE_SETTINGS_SLOT.match(text):
            slot_num = int(m.group(1))
            state = _PLAYER_STATE_STRINGS.get(m.group(2), BanchoLobbyPlayerStates.NotReady)
            username = m.group(3).strip()
            user = self._client.get_user(username)
            existing = self.slots[slot_num - 1]
            if existing and existing.user.username.casefold() == username.casefold():
                existing.state = state
            else:
                player = BanchoLobbyPlayer(lobby=self, user=user, slot=slot_num, state=state)
                self._place(player)

    # ── properties ────────────────────────────────────────────────────────────

    @property
    def host(self) -> BanchoLobbyPlayer | None:
        return next((p for p in self.slots if p and p.is_host), None)

    def get_history_url(self) -> str:
        return f"https://osu.ppy.sh/mp/{self.id}"

    # ── !mp commands ──────────────────────────────────────────────────────────

    async def set_name(self, name: str) -> None:
        await self._send_command(f"name {name}")

    async def set_password(self, password: str) -> None:
        await self._send_command(f"password {password}")

    async def clear_password(self) -> None:
        await self._send_command("password")

    async def set_size(self, size: int) -> None:
        await self._send_command(f"size {size}")

    async def set_map(self, beatmap_id: int, gamemode: BanchoGamemode = BanchoGamemode.Osu) -> None:
        await self._send_command(f"map {beatmap_id} {gamemode.value}")

    async def set_mods(self, mods: Mod, freemod: bool = False) -> None:
        mod_str = _mods_to_str(mods)
        if freemod:
            mod_str += " Freemod"
        await self._send_command(f"mods {mod_str}")

    async def set_settings(
        self,
        team_mode: BanchoLobbyTeamModes,
        win_condition: BanchoLobbyWinConditions,
        size: int | None = None,
    ) -> None:
        cmd = f"set {team_mode.value} {win_condition.value}"
        if size is not None:
            cmd += f" {size}"
        await self._send_command(cmd)

    async def set_host(self, username: str) -> None:
        await self._send_command(f"host {username}")

    async def clear_host(self) -> None:
        await self._send_command("clearhost")

    async def lock(self) -> None:
        await self._send_command("lock")

    async def unlock(self) -> None:
        await self._send_command("unlock")

    async def start_match(self, timeout: int | None = None) -> None:
        cmd = f"start {timeout}" if timeout is not None else "start"
        await self._send_command(cmd)

    async def abort_match(self) -> None:
        await self._send_command("abort")

    async def start_timer(self, seconds: int) -> None:
        await self._send_command(f"timer {seconds}")

    async def abort_timer(self) -> None:
        await self._send_command("aborttimer")

    async def kick_player(self, username: str) -> None:
        await self._send_command(f"kick {username}")

    async def ban_player(self, username: str) -> None:
        await self._send_command(f"ban {username}")

    async def move_player(self, username: str, slot: int) -> None:
        await self._send_command(f"move {username} {slot}")

    async def change_team(self, username: str, team: BanchoLobbyTeams) -> None:
        await self._send_command(f"team {username} {'red' if team == BanchoLobbyTeams.Red else 'blue'}")

    async def add_ref(self, ref: str | list[str]) -> None:
        await self._send_command(f"addref {' '.join(ref) if isinstance(ref, list) else ref}")

    async def remove_ref(self, ref: str | list[str]) -> None:
        await self._send_command(f"removeref {' '.join(ref) if isinstance(ref, list) else ref}")

    async def invite_player(self, username: str) -> None:
        await self._send_command(f"invite {username}")

    async def update_settings(self) -> None:
        await self._send_command("settings")

    async def close_lobby(self) -> None:
        await self._send_command("close")

    def __repr__(self) -> str:
        return f"BanchoLobby(id={self.id}, name={self.name!r})"
