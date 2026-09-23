from collections.abc import Sequence
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message

DESCRIPTOR: _descriptor.FileDescriptor

class Uuid(_message.Message):
    value: bytes
    def __init__(self, **kwargs: object) -> None: ...

class HistoryId(_message.Message):
    uuid: Uuid
    def __init__(self, **kwargs: object) -> None: ...

class RecordId(_message.Message):
    uuid: Uuid
    def __init__(self, **kwargs: object) -> None: ...

class PyStyleIdxRange(_message.Message):
    start: int
    end: int
    def __init__(self, **kwargs: object) -> None: ...

class UnsignedIdxRange(_message.Message):
    start: int
    end: int
    def __init__(self, **kwargs: object) -> None: ...

class HighlightedText(_message.Message):
    open: int
    close: int
    raw: str
    def __init__(self, **kwargs: object) -> None: ...

