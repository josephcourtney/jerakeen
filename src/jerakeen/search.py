from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Self

import grpc

from jerakeen._proto import search_pb2
from jerakeen._rpc import call
from jerakeen.exceptions import AtuinProtocolError, from_grpc_error
from jerakeen.models import FilterMode, SearchContext, SearchQuery, SearchResult

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, AsyncIterator, Iterable

    from jerakeen._interfaces import SearchStub

_FILTER_MODES = {
    FilterMode.GLOBAL: search_pb2.GLOBAL,
    FilterMode.HOST: search_pb2.HOST,
    FilterMode.SESSION: search_pb2.SESSION,
    FilterMode.DIRECTORY: search_pb2.DIRECTORY,
    FilterMode.WORKSPACE: search_pb2.WORKSPACE,
    FilterMode.SESSION_PRELOAD: search_pb2.SESSION_PRELOAD,
}


def _context_to_proto(context: SearchContext | None) -> search_pb2.SearchContext | None:
    if context is None:
        return None
    message = search_pb2.SearchContext(
        session_id=context.session_id,
        cwd=context.cwd,
        hostname=context.hostname,
        host_id=context.host_id,
    )
    if context.git_root is not None:
        message.git_root = context.git_root
    return message


def _query_to_proto(query: SearchQuery) -> search_pb2.SearchRequest:
    request = search_pb2.SearchRequest(
        query=query.query,
        query_id=query.query_id,
        filter_mode=_FILTER_MODES[query.filter_mode],
        shells=list(query.shells),
    )
    context = _context_to_proto(query.context)
    if context is not None:
        request.context.CopyFrom(context)
    return request


def _result_from_proto(reply: search_pb2.SearchResponse) -> SearchResult:
    return SearchResult(query_id=reply.query_id, ids=tuple(reply.ids))


class SearchSession:
    """Long-lived bidirectional search stream for interactive callers."""

    def __init__(self, stub: SearchStub) -> None:
        self._stub = stub
        self._queue: asyncio.Queue[search_pb2.SearchRequest | None] = asyncio.Queue()
        self._stream: AsyncIterator[search_pb2.SearchResponse] | None = None
        self._lock = asyncio.Lock()

    async def _requests(self) -> AsyncIterator[search_pb2.SearchRequest]:
        while True:
            request = await self._queue.get()
            if request is None:
                return
            yield request

    async def __aenter__(self) -> Self:
        self._stream = self._stub.Search(self._requests()).__aiter__()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.close()

    async def query(
        self,
        query: SearchQuery | str,
        *,
        query_id: int = 1,
        filter_mode: FilterMode = FilterMode.GLOBAL,
        context: SearchContext | None = None,
        shells: Iterable[str] = (),
    ) -> SearchResult:
        if isinstance(query, str):
            query = SearchQuery(
                query=query,
                query_id=query_id,
                filter_mode=filter_mode,
                context=context,
                shells=tuple(shells),
            )
        if self._stream is None:
            msg = "SearchSession must be used as an async context manager"
            raise RuntimeError(msg)

        async with self._lock:
            await self._queue.put(_query_to_proto(query))
            try:
                reply = await anext(self._stream)
            except StopAsyncIteration as exc:
                msg = "search stream ended before returning a response"
                raise AtuinProtocolError(msg) from exc
            except grpc.aio.AioRpcError as exc:
                raise from_grpc_error(exc) from exc
            return _result_from_proto(reply)

    async def close(self) -> None:
        if self._stream is None:
            return
        await self._queue.put(None)
        self._stream = None


class SearchClient:
    """Pythonic wrapper around Atuin's Search gRPC service."""

    def __init__(self, stub: SearchStub) -> None:
        self._stub = stub

    async def prepare_index(self, shells: Iterable[str] = ()) -> None:
        await call(self._stub.PrepareIndex(search_pb2.PrepareIndexRequest(shells=list(shells))))

    async def query(
        self,
        query: str,
        *,
        query_id: int = 1,
        filter_mode: FilterMode = FilterMode.GLOBAL,
        context: SearchContext | None = None,
        shells: Iterable[str] = (),
    ) -> SearchResult:
        request = SearchQuery(
            query=query,
            query_id=query_id,
            filter_mode=filter_mode,
            context=context,
            shells=tuple(shells),
        )

        async def requests() -> AsyncIterator[search_pb2.SearchRequest]:
            yield _query_to_proto(request)

        try:
            async for reply in self._stub.Search(requests()):
                return _result_from_proto(reply)
        except grpc.aio.AioRpcError as exc:
            raise from_grpc_error(exc) from exc
        msg = "search stream ended before returning a response"
        raise AtuinProtocolError(msg)

    async def stream(
        self,
        queries: AsyncIterable[SearchQuery],
    ) -> AsyncIterator[SearchResult]:
        async def requests() -> AsyncIterator[search_pb2.SearchRequest]:
            async for query in queries:
                yield _query_to_proto(query)

        try:
            async for reply in self._stub.Search(requests()):
                yield _result_from_proto(reply)
        except grpc.aio.AioRpcError as exc:
            raise from_grpc_error(exc) from exc

    def session(self) -> SearchSession:
        return SearchSession(self._stub)
