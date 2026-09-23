from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


@dataclass(frozen=True, slots=True)
class DaemonStatus:
    healthy: bool
    version: str
    pid: int
    protocol: int


class AuthorKind(StrEnum):
    UNSPECIFIED = "unspecified"
    USER = "user"
    AGENT = "agent"


@dataclass(frozen=True, slots=True, kw_only=True)
class HistoryEvent:
    id: UUID
    timestamp: datetime
    timestamp_ns: int
    command: str
    cwd: str
    session: str
    hostname: str
    author: str | None
    intent: str | None
    shell: str | None
    author_kind: AuthorKind


@dataclass(frozen=True, slots=True, kw_only=True)
class HistoryStarted(HistoryEvent):
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class HistoryEnded(HistoryEvent):
    exit_code: int
    duration_ns: int


@dataclass(frozen=True, slots=True, kw_only=True)
class HistoryCancelled(HistoryEvent):
    pass


@dataclass(frozen=True, slots=True)
class HistoryLagged:
    dropped: int


type HistoryEventRecord = HistoryStarted | HistoryEnded | HistoryCancelled | HistoryLagged


@dataclass(frozen=True, slots=True)
class HistoryStart:
    id: UUID
    version: str
    protocol: int


@dataclass(frozen=True, slots=True)
class HistoryEnd:
    record_id: UUID
    record_idx: int
    version: str
    protocol: int


@dataclass(frozen=True, slots=True)
class HistoryCancel:
    version: str
    protocol: int


@dataclass(frozen=True, slots=True)
class HistoryDelete:
    deleted: int
    version: str
    protocol: int


@dataclass(frozen=True, slots=True)
class HistoryRebuild:
    version: str
    protocol: int


@dataclass(slots=True)
class HistoryCommand:
    """A command lifecycle whose completion fields can be set inside the context."""

    start: HistoryStart
    exit_code: int = 0
    duration_ns: int | None = None

    @property
    def id(self) -> UUID:
        return self.start.id

    @property
    def version(self) -> str:
        return self.start.version

    @property
    def protocol(self) -> int:
        return self.start.protocol


@dataclass(frozen=True, slots=True)
class CommandCaptureMeta:
    observed_bytes: int
    terminal_width: int
    terminal_height: int


@dataclass(frozen=True, slots=True)
class CommandCapture:
    output_start: str
    meta: CommandCaptureMeta
    output_end: str | None = None


@dataclass(frozen=True, slots=True)
class OutputChunk:
    """One returned output span; start/end line numbers are inclusive."""

    start_line: int
    end_line: int
    content: str


@dataclass(frozen=True, slots=True)
class CommandOutput:
    text: str
    total_bytes: int
    total_lines: int
    chunks: tuple[OutputChunk, ...]
    truncated: bool
    meta: CommandCaptureMeta

    @property
    def observed_bytes(self) -> int:
        return self.meta.observed_bytes


@dataclass(frozen=True, slots=True)
class HighlightedText:
    raw: str
    open: int
    close: int


@dataclass(frozen=True, slots=True)
class OutputSearchLine:
    line: int
    content: HighlightedText


@dataclass(frozen=True, slots=True)
class OutputSearchMatch:
    history_id: UUID
    lines: tuple[OutputSearchLine, ...]
    score: float


class FilterMode(StrEnum):
    GLOBAL = "global"
    HOST = "host"
    SESSION = "session"
    DIRECTORY = "directory"
    WORKSPACE = "workspace"
    SESSION_PRELOAD = "session_preload"


@dataclass(frozen=True, slots=True)
class SearchContext:
    session_id: str = ""
    cwd: str = ""
    hostname: str = ""
    host_id: str = ""
    git_root: str | None = None


@dataclass(frozen=True, slots=True)
class SearchQuery:
    query: str
    query_id: int | None = None
    filter_mode: FilterMode = FilterMode.GLOBAL
    context: SearchContext | None = None
    shells: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.query_id is not None and not 0 <= self.query_id <= 2**64 - 1:
            raise ValueError("query_id must fit an unsigned 64-bit integer")

        if self.filter_mode is FilterMode.GLOBAL:
            return

        context = self.context
        if context is None:
            raise ValueError(f"{self.filter_mode.value} search requires a SearchContext")

        required = {
            FilterMode.HOST: ("hostname", context.hostname),
            FilterMode.SESSION: ("session_id", context.session_id),
            FilterMode.SESSION_PRELOAD: ("session_id", context.session_id),
            FilterMode.DIRECTORY: ("cwd", context.cwd),
        }
        if self.filter_mode in required:
            field, value = required[self.filter_mode]
            if not value:
                raise ValueError(f"{self.filter_mode.value} search requires context.{field}")
            return

        if self.filter_mode is FilterMode.WORKSPACE and not (context.git_root or context.cwd):
            raise ValueError("workspace search requires context.git_root or context.cwd")


@dataclass(frozen=True, slots=True)
class SearchResult:
    query_id: int
    ids: tuple[UUID, ...]
