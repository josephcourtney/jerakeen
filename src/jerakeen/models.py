from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(frozen=True, slots=True)
class DaemonStatus:
    healthy: bool
    version: str
    pid: int
    protocol: int


@dataclass(frozen=True, slots=True, kw_only=True)
class HistoryEvent:
    id: str
    timestamp: datetime
    timestamp_ns: int
    command: str
    cwd: str
    session: str
    hostname: str
    author: str | None
    intent: str | None
    shell: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class HistoryStarted(HistoryEvent):
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class HistoryEnded(HistoryEvent):
    exit_code: int
    duration_ns: int


type HistoryEventRecord = HistoryStarted | HistoryEnded


@dataclass(frozen=True, slots=True)
class HistoryStart:
    id: str
    version: str
    protocol: int


@dataclass(frozen=True, slots=True)
class HistoryEnd:
    id: str
    idx: int
    version: str
    protocol: int


@dataclass(frozen=True, slots=True)
class OutputLine:
    line_number: int
    content: str


@dataclass(frozen=True, slots=True)
class CommandOutput:
    text: str
    total_bytes: int
    total_lines: int
    lines: tuple[OutputLine, ...]
    truncated: bool
    observed_bytes: int


@dataclass(frozen=True, slots=True)
class CommandCapture:
    prompt: str
    command: str
    output: str
    exit_code: int | None = None
    history_id: str | None = None
    session_id: str | None = None
    output_truncated: bool = False
    output_observed_bytes: int = 0


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
    query_id: int = 1
    filter_mode: FilterMode = FilterMode.GLOBAL
    context: SearchContext | None = None
    shells: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SearchResult:
    query_id: int
    ids: tuple[bytes, ...]
