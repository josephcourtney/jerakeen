from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class HistoryEventKind(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    HISTORY_EVENT_KIND_UNSPECIFIED: _ClassVar[HistoryEventKind]
    HISTORY_EVENT_KIND_STARTED: _ClassVar[HistoryEventKind]
    HISTORY_EVENT_KIND_ENDED: _ClassVar[HistoryEventKind]
HISTORY_EVENT_KIND_UNSPECIFIED: HistoryEventKind
HISTORY_EVENT_KIND_STARTED: HistoryEventKind
HISTORY_EVENT_KIND_ENDED: HistoryEventKind

class StartHistoryRequest(_message.Message):
    __slots__ = ("timestamp", "command", "cwd", "session", "hostname", "author", "intent", "shell")
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    COMMAND_FIELD_NUMBER: _ClassVar[int]
    CWD_FIELD_NUMBER: _ClassVar[int]
    SESSION_FIELD_NUMBER: _ClassVar[int]
    HOSTNAME_FIELD_NUMBER: _ClassVar[int]
    AUTHOR_FIELD_NUMBER: _ClassVar[int]
    INTENT_FIELD_NUMBER: _ClassVar[int]
    SHELL_FIELD_NUMBER: _ClassVar[int]
    timestamp: int
    command: str
    cwd: str
    session: str
    hostname: str
    author: str
    intent: str
    shell: str
    def __init__(self, timestamp: _Optional[int] = ..., command: _Optional[str] = ..., cwd: _Optional[str] = ..., session: _Optional[str] = ..., hostname: _Optional[str] = ..., author: _Optional[str] = ..., intent: _Optional[str] = ..., shell: _Optional[str] = ...) -> None: ...

class EndHistoryRequest(_message.Message):
    __slots__ = ("id", "exit", "duration")
    ID_FIELD_NUMBER: _ClassVar[int]
    EXIT_FIELD_NUMBER: _ClassVar[int]
    DURATION_FIELD_NUMBER: _ClassVar[int]
    id: str
    exit: int
    duration: int
    def __init__(self, id: _Optional[str] = ..., exit: _Optional[int] = ..., duration: _Optional[int] = ...) -> None: ...

class CancelHistoryRequest(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class StartHistoryReply(_message.Message):
    __slots__ = ("id", "version", "protocol")
    ID_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    PROTOCOL_FIELD_NUMBER: _ClassVar[int]
    id: str
    version: str
    protocol: int
    def __init__(self, id: _Optional[str] = ..., version: _Optional[str] = ..., protocol: _Optional[int] = ...) -> None: ...

class EndHistoryReply(_message.Message):
    __slots__ = ("id", "idx", "version", "protocol")
    ID_FIELD_NUMBER: _ClassVar[int]
    IDX_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    PROTOCOL_FIELD_NUMBER: _ClassVar[int]
    id: str
    idx: int
    version: str
    protocol: int
    def __init__(self, id: _Optional[str] = ..., idx: _Optional[int] = ..., version: _Optional[str] = ..., protocol: _Optional[int] = ...) -> None: ...

class CancelHistoryReply(_message.Message):
    __slots__ = ("version", "protocol")
    VERSION_FIELD_NUMBER: _ClassVar[int]
    PROTOCOL_FIELD_NUMBER: _ClassVar[int]
    version: str
    protocol: int
    def __init__(self, version: _Optional[str] = ..., protocol: _Optional[int] = ...) -> None: ...

class StatusRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class StatusReply(_message.Message):
    __slots__ = ("healthy", "version", "pid", "protocol")
    HEALTHY_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    PID_FIELD_NUMBER: _ClassVar[int]
    PROTOCOL_FIELD_NUMBER: _ClassVar[int]
    healthy: bool
    version: str
    pid: int
    protocol: int
    def __init__(self, healthy: _Optional[bool] = ..., version: _Optional[str] = ..., pid: _Optional[int] = ..., protocol: _Optional[int] = ...) -> None: ...

class ShutdownRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ShutdownReply(_message.Message):
    __slots__ = ("accepted",)
    ACCEPTED_FIELD_NUMBER: _ClassVar[int]
    accepted: bool
    def __init__(self, accepted: _Optional[bool] = ...) -> None: ...

class TailHistoryRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class HistoryEntry(_message.Message):
    __slots__ = ("timestamp", "id", "command", "cwd", "session", "hostname", "author", "intent", "exit", "duration", "shell")
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    COMMAND_FIELD_NUMBER: _ClassVar[int]
    CWD_FIELD_NUMBER: _ClassVar[int]
    SESSION_FIELD_NUMBER: _ClassVar[int]
    HOSTNAME_FIELD_NUMBER: _ClassVar[int]
    AUTHOR_FIELD_NUMBER: _ClassVar[int]
    INTENT_FIELD_NUMBER: _ClassVar[int]
    EXIT_FIELD_NUMBER: _ClassVar[int]
    DURATION_FIELD_NUMBER: _ClassVar[int]
    SHELL_FIELD_NUMBER: _ClassVar[int]
    timestamp: int
    id: str
    command: str
    cwd: str
    session: str
    hostname: str
    author: str
    intent: str
    exit: int
    duration: int
    shell: str
    def __init__(self, timestamp: _Optional[int] = ..., id: _Optional[str] = ..., command: _Optional[str] = ..., cwd: _Optional[str] = ..., session: _Optional[str] = ..., hostname: _Optional[str] = ..., author: _Optional[str] = ..., intent: _Optional[str] = ..., exit: _Optional[int] = ..., duration: _Optional[int] = ..., shell: _Optional[str] = ...) -> None: ...

class TailHistoryReply(_message.Message):
    __slots__ = ("kind", "history")
    KIND_FIELD_NUMBER: _ClassVar[int]
    HISTORY_FIELD_NUMBER: _ClassVar[int]
    kind: HistoryEventKind
    history: HistoryEntry
    def __init__(self, kind: _Optional[_Union[HistoryEventKind, str]] = ..., history: _Optional[_Union[HistoryEntry, _Mapping]] = ...) -> None: ...
