from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class CommandCapture(_message.Message):
    __slots__ = ("prompt", "command", "output", "exit_code", "history_id", "session_id", "output_truncated", "output_observed_bytes")
    PROMPT_FIELD_NUMBER: _ClassVar[int]
    COMMAND_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_FIELD_NUMBER: _ClassVar[int]
    EXIT_CODE_FIELD_NUMBER: _ClassVar[int]
    HISTORY_ID_FIELD_NUMBER: _ClassVar[int]
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_TRUNCATED_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_OBSERVED_BYTES_FIELD_NUMBER: _ClassVar[int]
    prompt: str
    command: str
    output: str
    exit_code: int
    history_id: str
    session_id: str
    output_truncated: bool
    output_observed_bytes: int
    def __init__(self, prompt: _Optional[str] = ..., command: _Optional[str] = ..., output: _Optional[str] = ..., exit_code: _Optional[int] = ..., history_id: _Optional[str] = ..., session_id: _Optional[str] = ..., output_truncated: _Optional[bool] = ..., output_observed_bytes: _Optional[int] = ...) -> None: ...

class RecordCommandsReply(_message.Message):
    __slots__ = ("accepted",)
    ACCEPTED_FIELD_NUMBER: _ClassVar[int]
    accepted: int
    def __init__(self, accepted: _Optional[int] = ...) -> None: ...

class CommandOutputRequest(_message.Message):
    __slots__ = ("history_id", "ranges")
    HISTORY_ID_FIELD_NUMBER: _ClassVar[int]
    RANGES_FIELD_NUMBER: _ClassVar[int]
    history_id: str
    ranges: _containers.RepeatedCompositeFieldContainer[OutputRange]
    def __init__(self, history_id: _Optional[str] = ..., ranges: _Optional[_Iterable[_Union[OutputRange, _Mapping]]] = ...) -> None: ...

class OutputRange(_message.Message):
    __slots__ = ("start", "end")
    START_FIELD_NUMBER: _ClassVar[int]
    END_FIELD_NUMBER: _ClassVar[int]
    start: int
    end: int
    def __init__(self, start: _Optional[int] = ..., end: _Optional[int] = ...) -> None: ...

class OutputLine(_message.Message):
    __slots__ = ("line_number", "content")
    LINE_NUMBER_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    line_number: int
    content: str
    def __init__(self, line_number: _Optional[int] = ..., content: _Optional[str] = ...) -> None: ...

class CommandOutputReply(_message.Message):
    __slots__ = ("found", "output", "total_bytes", "total_lines", "lines", "output_truncated", "output_observed_bytes")
    FOUND_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_FIELD_NUMBER: _ClassVar[int]
    TOTAL_BYTES_FIELD_NUMBER: _ClassVar[int]
    TOTAL_LINES_FIELD_NUMBER: _ClassVar[int]
    LINES_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_TRUNCATED_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_OBSERVED_BYTES_FIELD_NUMBER: _ClassVar[int]
    found: bool
    output: str
    total_bytes: int
    total_lines: int
    lines: _containers.RepeatedCompositeFieldContainer[OutputLine]
    output_truncated: bool
    output_observed_bytes: int
    def __init__(self, found: _Optional[bool] = ..., output: _Optional[str] = ..., total_bytes: _Optional[int] = ..., total_lines: _Optional[int] = ..., lines: _Optional[_Iterable[_Union[OutputLine, _Mapping]]] = ..., output_truncated: _Optional[bool] = ..., output_observed_bytes: _Optional[int] = ...) -> None: ...
