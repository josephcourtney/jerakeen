from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class SendEventRequest(_message.Message):
    __slots__ = ("history_pruned", "history_deleted", "force_sync", "settings_reloaded", "shutdown", "history_rebuilt")
    HISTORY_PRUNED_FIELD_NUMBER: _ClassVar[int]
    HISTORY_DELETED_FIELD_NUMBER: _ClassVar[int]
    FORCE_SYNC_FIELD_NUMBER: _ClassVar[int]
    SETTINGS_RELOADED_FIELD_NUMBER: _ClassVar[int]
    SHUTDOWN_FIELD_NUMBER: _ClassVar[int]
    HISTORY_REBUILT_FIELD_NUMBER: _ClassVar[int]
    history_pruned: HistoryPrunedEvent
    history_deleted: HistoryDeletedEvent
    force_sync: ForceSyncEvent
    settings_reloaded: SettingsReloadedEvent
    shutdown: ShutdownEvent
    history_rebuilt: HistoryRebuiltEvent
    def __init__(self, history_pruned: _Optional[_Union[HistoryPrunedEvent, _Mapping]] = ..., history_deleted: _Optional[_Union[HistoryDeletedEvent, _Mapping]] = ..., force_sync: _Optional[_Union[ForceSyncEvent, _Mapping]] = ..., settings_reloaded: _Optional[_Union[SettingsReloadedEvent, _Mapping]] = ..., shutdown: _Optional[_Union[ShutdownEvent, _Mapping]] = ..., history_rebuilt: _Optional[_Union[HistoryRebuiltEvent, _Mapping]] = ...) -> None: ...

class SendEventResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class HistoryPrunedEvent(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class HistoryRebuiltEvent(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class HistoryDeletedEvent(_message.Message):
    __slots__ = ("ids",)
    IDS_FIELD_NUMBER: _ClassVar[int]
    ids: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, ids: _Optional[_Iterable[str]] = ...) -> None: ...

class ForceSyncEvent(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class SettingsReloadedEvent(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ShutdownEvent(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...
