from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class FilterMode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    GLOBAL: _ClassVar[FilterMode]
    HOST: _ClassVar[FilterMode]
    SESSION: _ClassVar[FilterMode]
    DIRECTORY: _ClassVar[FilterMode]
    WORKSPACE: _ClassVar[FilterMode]
    SESSION_PRELOAD: _ClassVar[FilterMode]
GLOBAL: FilterMode
HOST: FilterMode
SESSION: FilterMode
DIRECTORY: FilterMode
WORKSPACE: FilterMode
SESSION_PRELOAD: FilterMode

class SearchContext(_message.Message):
    __slots__ = ("session_id", "cwd", "hostname", "host_id", "git_root")
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    CWD_FIELD_NUMBER: _ClassVar[int]
    HOSTNAME_FIELD_NUMBER: _ClassVar[int]
    HOST_ID_FIELD_NUMBER: _ClassVar[int]
    GIT_ROOT_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    cwd: str
    hostname: str
    host_id: str
    git_root: str
    def __init__(self, session_id: _Optional[str] = ..., cwd: _Optional[str] = ..., hostname: _Optional[str] = ..., host_id: _Optional[str] = ..., git_root: _Optional[str] = ...) -> None: ...

class SearchRequest(_message.Message):
    __slots__ = ("query", "query_id", "filter_mode", "context", "shells")
    QUERY_FIELD_NUMBER: _ClassVar[int]
    QUERY_ID_FIELD_NUMBER: _ClassVar[int]
    FILTER_MODE_FIELD_NUMBER: _ClassVar[int]
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    SHELLS_FIELD_NUMBER: _ClassVar[int]
    query: str
    query_id: int
    filter_mode: FilterMode
    context: SearchContext
    shells: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, query: _Optional[str] = ..., query_id: _Optional[int] = ..., filter_mode: _Optional[_Union[FilterMode, str]] = ..., context: _Optional[_Union[SearchContext, _Mapping]] = ..., shells: _Optional[_Iterable[str]] = ...) -> None: ...

class SearchResponse(_message.Message):
    __slots__ = ("query_id", "ids")
    QUERY_ID_FIELD_NUMBER: _ClassVar[int]
    IDS_FIELD_NUMBER: _ClassVar[int]
    query_id: int
    ids: _containers.RepeatedScalarFieldContainer[bytes]
    def __init__(self, query_id: _Optional[int] = ..., ids: _Optional[_Iterable[bytes]] = ...) -> None: ...

class PrepareIndexRequest(_message.Message):
    __slots__ = ("shells",)
    SHELLS_FIELD_NUMBER: _ClassVar[int]
    shells: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, shells: _Optional[_Iterable[str]] = ...) -> None: ...

class PrepareIndexResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...
