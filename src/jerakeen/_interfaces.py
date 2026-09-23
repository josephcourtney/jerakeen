from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, Awaitable

    from jerakeen._proto import history_pb2, search_pb2


class HistoryStub(Protocol):
    def StartHistory(
        self, request: history_pb2.StartHistoryRequest, *, timeout: float | None = None
    ) -> Awaitable[history_pb2.StartHistoryReply]: ...

    def EndHistory(
        self, request: history_pb2.EndHistoryRequest, *, timeout: float | None = None
    ) -> Awaitable[history_pb2.EndHistoryReply]: ...

    def CancelHistory(
        self, request: history_pb2.CancelHistoryRequest, *, timeout: float | None = None
    ) -> Awaitable[history_pb2.CancelHistoryReply]: ...

    def DeleteHistory(
        self,
        request_iterator: AsyncIterable[history_pb2.DeleteHistoryRequest],
        /,
        *,
        timeout: float | None = None,
    ) -> Awaitable[history_pb2.DeleteHistoryReply]: ...

    def RebuildHistory(
        self, request: history_pb2.RebuildHistoryRequest, *, timeout: float | None = None
    ) -> Awaitable[history_pb2.RebuildHistoryReply]: ...

    def TailHistory(
        self, request: history_pb2.TailHistoryRequest, *, timeout: float | None = None
    ) -> AsyncIterable[history_pb2.TailHistoryReply]: ...

    def Status(
        self, request: history_pb2.StatusRequest, *, timeout: float | None = None
    ) -> Awaitable[history_pb2.StatusReply]: ...

    def Shutdown(
        self, request: history_pb2.ShutdownRequest, *, timeout: float | None = None
    ) -> Awaitable[history_pb2.ShutdownReply]: ...

    def RegisterCommandOutput(
        self,
        request: history_pb2.RegisterCommandOutputRequest,
        *,
        timeout: float | None = None,
    ) -> Awaitable[history_pb2.RegisterCommandOutputResponse]: ...

    def GetCommandOutput(
        self, request: history_pb2.GetCommandOutputRequest, *, timeout: float | None = None
    ) -> Awaitable[history_pb2.GetCommandOutputResponse]: ...


class SearchStub(Protocol):
    def Search(
        self,
        request_iterator: AsyncIterable[search_pb2.SearchRequest],
        /,
        *,
        timeout: float | None = None,
    ) -> AsyncIterable[search_pb2.SearchResponse]: ...

    def PrepareIndex(
        self, request: search_pb2.PrepareIndexRequest, *, timeout: float | None = None
    ) -> Awaitable[search_pb2.PrepareIndexResponse]: ...

    def SearchCommandOutput(
        self,
        request: search_pb2.SearchCommandOutputRequest,
        *,
        timeout: float | None = None,
    ) -> AsyncIterable[search_pb2.OutputSearchMatch]: ...
