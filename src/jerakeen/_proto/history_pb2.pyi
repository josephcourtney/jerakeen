from collections.abc import Sequence
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from . import common_pb2
from google.protobuf import duration_pb2

DESCRIPTOR: _descriptor.FileDescriptor

AUTHOR_KIND_UNSPECIFIED: int
AUTHOR_KIND_USER: int
AUTHOR_KIND_AGENT: int

class StartHistoryRequest(_message.Message):
    timestamp: int
    command: str
    cwd: str
    session: str
    hostname: str
    author: str
    intent: str
    shell: str
    author_kind: int
    def __init__(self, **kwargs: object) -> None: ...

class EndHistoryRequest(_message.Message):
    id: common_pb2.HistoryId
    exit: int
    duration: duration_pb2.Duration
    def __init__(self, **kwargs: object) -> None: ...

class CancelHistoryRequest(_message.Message):
    id: common_pb2.HistoryId
    def __init__(self, **kwargs: object) -> None: ...

class StartHistoryReply(_message.Message):
    id: common_pb2.HistoryId
    version: str
    protocol: int
    def __init__(self, **kwargs: object) -> None: ...

class EndHistoryReply(_message.Message):
    record_id: common_pb2.RecordId
    record_idx: int
    version: str
    protocol: int
    def __init__(self, **kwargs: object) -> None: ...

class CancelHistoryReply(_message.Message):
    version: str
    protocol: int
    def __init__(self, **kwargs: object) -> None: ...

class DeleteHistoryRequest(_message.Message):
    ids: Sequence[common_pb2.HistoryId]
    def __init__(self, **kwargs: object) -> None: ...

class DeleteHistoryReply(_message.Message):
    deleted: int
    version: str
    protocol: int
    def __init__(self, **kwargs: object) -> None: ...

class RebuildHistoryRequest(_message.Message):
    def __init__(self, **kwargs: object) -> None: ...

class RebuildHistoryReply(_message.Message):
    version: str
    protocol: int
    def __init__(self, **kwargs: object) -> None: ...

class StatusRequest(_message.Message):
    def __init__(self, **kwargs: object) -> None: ...

class StatusReply(_message.Message):
    healthy: bool
    version: str
    pid: int
    protocol: int
    def __init__(self, **kwargs: object) -> None: ...

class ShutdownRequest(_message.Message):
    def __init__(self, **kwargs: object) -> None: ...

class ShutdownReply(_message.Message):
    accepted: bool
    def __init__(self, **kwargs: object) -> None: ...

class TailHistoryRequest(_message.Message):
    def __init__(self, **kwargs: object) -> None: ...

class HistoryEntry(_message.Message):
    timestamp: int
    id: common_pb2.HistoryId
    command: str
    cwd: str
    session: str
    hostname: str
    author: str
    intent: str
    exit: int
    duration: int
    shell: str
    author_kind: int
    def __init__(self, **kwargs: object) -> None: ...

class Lagged(_message.Message):
    dropped: int
    def __init__(self, **kwargs: object) -> None: ...

class TailHistoryReply(_message.Message):
    started: HistoryEntry
    ended: HistoryEntry
    cancelled: HistoryEntry
    lagged: Lagged
    def __init__(self, **kwargs: object) -> None: ...

class CommandCaptureMeta(_message.Message):
    output_observed_bytes: int
    terminal_width: int
    terminal_height: int
    def __init__(self, **kwargs: object) -> None: ...

class CommandCapture(_message.Message):
    output_start: str
    output_end: str
    meta: CommandCaptureMeta
    def __init__(self, **kwargs: object) -> None: ...

class RegisterCommandOutputRequest(_message.Message):
    history_id: common_pb2.HistoryId
    capture: CommandCapture
    def __init__(self, **kwargs: object) -> None: ...

class RegisterCommandOutputResponse(_message.Message):
    def __init__(self, **kwargs: object) -> None: ...

class GetCommandOutputRequest(_message.Message):
    id: common_pb2.HistoryId
    line_ranges: Sequence[common_pb2.PyStyleIdxRange]
    def __init__(self, **kwargs: object) -> None: ...

class GetCommandOutputResponse(_message.Message):
    chunks: Sequence[OutputChunk]
    total_bytes: int
    total_lines: int
    meta: CommandCaptureMeta
    truncated: bool
    def __init__(self, **kwargs: object) -> None: ...

class OutputChunk(_message.Message):
    line_range: common_pb2.PyStyleIdxRange
    content: str
    def __init__(self, **kwargs: object) -> None: ...

