from enum import Enum, IntEnum, IntFlag


class ConnectStates(Enum):
    Disconnected = "Disconnected"
    Connecting = "Connecting"
    Connected = "Connected"
    Disconnecting = "Disconnecting"


class BanchoLobbyPlayerStates(IntEnum):
    NotReady = 0
    Ready = 1
    NoMap = 2
    Playing = 3


class BanchoLobbyTeamModes(IntEnum):
    HeadToHead = 0
    TagCoop = 1
    TeamVs = 2
    TagTeamVs = 3


class BanchoLobbyTeams(IntEnum):
    NoTeam = 0
    Blue = 1
    Red = 2


class BanchoLobbyWinConditions(IntEnum):
    Score = 0
    Accuracy = 1
    Combo = 2
    ScoreV2 = 3


class BanchoGamemode(IntEnum):
    Osu = 0
    Taiko = 1
    CatchTheBeat = 2
    OsuMania = 3


class Mod(IntFlag):
    NoMod = 0
    NoFail = 1 << 0
    Easy = 1 << 1
    TouchDevice = 1 << 2
    Hidden = 1 << 3
    HardRock = 1 << 4
    SuddenDeath = 1 << 5
    DoubleTime = 1 << 6
    Relax = 1 << 7
    HalfTime = 1 << 8
    Nightcore = 1 << 9
    Flashlight = 1 << 10
    Autoplay = 1 << 11
    SpunOut = 1 << 12
    Autopilot = 1 << 13
    Perfect = 1 << 14
    Key4 = 1 << 15
    Key5 = 1 << 16
    Key6 = 1 << 17
    Key7 = 1 << 18
    Key8 = 1 << 19
    FadeIn = 1 << 20
    Random = 1 << 21
    Cinema = 1 << 22
    Target = 1 << 23
    Key9 = 1 << 24
    KeyCoop = 1 << 25
    Key1 = 1 << 26
    Key3 = 1 << 27
    Key2 = 1 << 28
    ScoreV2 = 1 << 29
    Mirror = 1 << 30
