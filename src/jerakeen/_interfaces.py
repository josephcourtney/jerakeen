from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, Awaitable

    from jerakeen._proto import control_pb2, history_pb2, search_pb2, semantic_pb2


class HistoryStub(Protocol):
    def StartHistory(  # inherited from protocol
        self, request: history_pb2.StartHistoryRequest, *, timeout: float | None = None
    ) -> Awaitable[history_pb2.StartHistoryReply]: ...

    def EndHistory(  # inherited from protocol
        self, request: history_pb2.EndHistoryRequest, *, timeout: float | None = None
    ) -> Awaitable[history_pb2.EndHistoryReply]: ...

    def CancelHistory(  # inherited from protocol
        self, request: history_pb2.CancelHistoryRequest, *, timeout: float | None = None
    ) -> Awaitable[history_pb2.CancelHistoryReply]: ...

    def TailHistory(  # inherited from protocol
        self, request: history_pb2.TailHistoryRequest, *, timeout: float | None = None
    ) -> AsyncIterable[history_pb2.TailHistoryReply]: ...

    def Status(  # inherited from protocol
        self, request: history_pb2.StatusRequest, *, timeout: float | None = None
    ) -> Awaitable[history_pb2.StatusReply]: ...

    def Shutdown(  # inherited from protocol
        self, request: history_pb2.ShutdownRequest, *, timeout: float | None = None
    ) -> Awaitable[history_pb2.ShutdownReply]: ...


class SemanticStub(Protocol):
    def RecordCommands(  # inherited from protocol
        self,
        request_iterator: AsyncIterable[semantic_pb2.CommandCapture],
        /,
        *,
        timeout: float | None = None,
    ) -> Awaitable[semantic_pb2.RecordCommandsReply]: ...

    def CommandOutput(  # inherited from protocol
        self, request: semantic_pb2.CommandOutputRequest, *, timeout: float | None = None
    ) -> Awaitable[semantic_pb2.CommandOutputReply]: ...


class SearchStub(Protocol):
    def Search(  # inherited from protocol
        self,
        request_iterator: AsyncIterable[search_pb2.SearchRequest],
        /,
        *,
        timeout: float | None = None,
    ) -> AsyncIterable[search_pb2.SearchResponse]: ...

    def PrepareIndex(  # inherited from protocol
        self, request: search_pb2.PrepareIndexRequest, *, timeout: float | None = None
    ) -> Awaitable[search_pb2.PrepareIndexResponse]: ...


class ControlStub(Protocol):
    def SendEvent(  # inherited from protocol
        self, request: control_pb2.SendEventRequest, *, timeout: float | None = None
    ) -> Awaitable[control_pb2.SendEventResponse]: ...
