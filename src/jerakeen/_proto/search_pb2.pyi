from collections.abc import Sequence
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from . import common_pb2

DESCRIPTOR: _descriptor.FileDescriptor

GLOBAL: int
HOST: int
SESSION: int
DIRECTORY: int
WORKSPACE: int
SESSION_PRELOAD: int

class SearchContext(_message.Message):
    session_id: str
    cwd: str
    hostname: str
    host_id: str
    git_root: str
    def __init__(self, **kwargs: object) -> None: ...

class SearchRequest(_message.Message):
    query: str
    query_id: int
    filter_mode: int
    context: SearchContext
    shells: Sequence[str]
    def __init__(self, **kwargs: object) -> None: ...

class SearchResponse(_message.Message):
    query_id: int
    ids: Sequence[bytes]
    def __init__(self, **kwargs: object) -> None: ...

class PrepareIndexRequest(_message.Message):
    shells: Sequence[str]
    def __init__(self, **kwargs: object) -> None: ...

class PrepareIndexResponse(_message.Message):
    def __init__(self, **kwargs: object) -> None: ...

class SearchCommandOutputRequest(_message.Message):
    query: str
    limit: int
    context: int
    def __init__(self, **kwargs: object) -> None: ...

class OutputSearchLine(_message.Message):
    line: int
    content: common_pb2.HighlightedText
    def __init__(self, **kwargs: object) -> None: ...

class OutputSearchMatch(_message.Message):
    history_id: common_pb2.HistoryId
    lines: Sequence[OutputSearchLine]
    score: float
    def __init__(self, **kwargs: object) -> None: ...

