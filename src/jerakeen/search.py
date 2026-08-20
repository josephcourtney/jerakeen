from __future__ import annotations

import asyncio
import contextlib
from dataclasses import replace
from typing import TYPE_CHECKING, Self
from uuid import UUID

import grpc

from jerakeen._proto import search_pb2
from jerakeen._rpc import call
from jerakeen.exceptions import AtuinProtocolError, AtuinTimeoutError, from_grpc_error
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


def _query_to_proto(query: SearchQuery, *, default_query_id: int = 1) -> search_pb2.SearchRequest:
    query_id = default_query_id if query.query_id is None else query.query_id
    request = search_pb2.SearchRequest(
        query=query.query,
        query_id=query_id,
        filter_mode=_FILTER_MODES[query.filter_mode],
        shells=list(query.shells),
    )
    context = _context_to_proto(query.context)
    if context is not None:
        request.context.CopyFrom(context)
    return request


def _result_from_proto(reply: search_pb2.SearchResponse) -> SearchResult:
    ids: list[UUID] = []
    for raw_id in reply.ids:
        try:
            ids.append(UUID(bytes=bytes(raw_id)))
        except ValueError as exc:
            msg = (
                f"search response {reply.query_id} contained a history id with "
                f"{len(raw_id)} bytes; expected 16"
            )
            raise AtuinProtocolError(msg) from exc
    return SearchResult(query_id=reply.query_id, ids=tuple(ids))


class SearchSession:
    """Long-lived bidirectional search stream for interactive callers.

    Query IDs are allocated automatically when omitted. Multiple calls to ``query`` may be
    outstanding concurrently; responses are routed to the matching caller by ``query_id``.
    """

    def __init__(self, stub: SearchStub, *, timeout: float | None = 5.0) -> None:
        self._stub = stub
        self._timeout = timeout
        self._queue: asyncio.Queue[search_pb2.SearchRequest | None] = asyncio.Queue()
        self._stream: AsyncIterable[search_pb2.SearchResponse] | None = None
        self._reader_task: asyncio.Task[None] | None = None
        self._pending: dict[int, asyncio.Future[SearchResult]] = {}
        self._expired: set[int] = set()
        self._next_query_id = 1
        self._terminal_error: BaseException | None = None
        self._active = False

    async def _requests(self) -> AsyncIterator[search_pb2.SearchRequest]:
        while True:
            request = await self._queue.get()
            if request is None:
                return
            yield request

    def _allocate_query_id(self, requested: int | None) -> int:
        if requested is not None:
            if requested in self._pending:
                msg = f"query_id {requested} is already outstanding"
                raise ValueError(msg)
            if requested in self._expired:
                msg = f"query_id {requested} is awaiting a stale response from a timed-out query"
                raise ValueError(msg)
            self._next_query_id = max(self._next_query_id, requested + 1)
            return requested

        while self._next_query_id in self._pending or self._next_query_id in self._expired:
            self._next_query_id += 1
        if self._next_query_id > 2**64 - 1:
            msg = "automatic search query IDs exhausted the uint64 range"
            raise OverflowError(msg)
        query_id = self._next_query_id
        self._next_query_id += 1
        return query_id

    def _fail_pending(self, error: BaseException) -> None:
        for future in self._pending.values():
            if not future.done():
                future.set_exception(error)
        self._pending.clear()

    async def _read_responses(self) -> None:
        assert self._stream is not None
        error: BaseException | None = None
        try:
            async for reply in self._stream:
                result = _result_from_proto(reply)
                future = self._pending.pop(result.query_id, None)
                if future is not None:
                    if not future.done():
                        future.set_result(result)
                    continue
                if result.query_id in self._expired:
                    self._expired.remove(result.query_id)
                    continue
                msg = f"search stream returned unknown query_id {result.query_id}"
                raise AtuinProtocolError(msg)
        except asyncio.CancelledError:
            raise
        except grpc.aio.AioRpcError as exc:
            error = from_grpc_error(exc)
        except BaseException as exc:
            error = exc
        else:
            error = AtuinProtocolError("search stream ended")
        finally:
            if error is not None:
                self._terminal_error = error
                self._fail_pending(error)
                self._active = False

    async def __aenter__(self) -> Self:
        if self._active:
            msg = "SearchSession is already active"
            raise RuntimeError(msg)
        self._terminal_error = None
        self._queue = asyncio.Queue()
        self._pending.clear()
        self._expired.clear()
        self._stream = self._stub.Search(self._requests())
        self._active = True
        self._reader_task = asyncio.create_task(self._read_responses())
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.close()

    async def query(
        self,
        query: SearchQuery | str,
        *,
        query_id: int | None = None,
        filter_mode: FilterMode = FilterMode.GLOBAL,
        context: SearchContext | None = None,
        shells: Iterable[str] = (),
    ) -> SearchResult:
        if not self._active:
            if self._terminal_error is not None:
                raise self._terminal_error
            msg = "SearchSession must be used as an async context manager"
            raise RuntimeError(msg)

        if isinstance(query, str):
            query = SearchQuery(
                query=query,
                query_id=query_id,
                filter_mode=filter_mode,
                context=context,
                shells=tuple(shells),
            )

        assigned_id = self._allocate_query_id(query.query_id)
        request = replace(query, query_id=assigned_id)
        future = asyncio.get_running_loop().create_future()
        self._pending[assigned_id] = future
        await self._queue.put(_query_to_proto(request))

        try:
            if self._timeout is None:
                return await future
            return await asyncio.wait_for(asyncio.shield(future), timeout=self._timeout)
        except TimeoutError as exc:
            self._pending.pop(assigned_id, None)
            self._expired.add(assigned_id)
            future.cancel()
            msg = f"Atuin search query {assigned_id} exceeded the {self._timeout:g}s deadline"
            raise AtuinTimeoutError(msg) from exc
        except asyncio.CancelledError:
            self._pending.pop(assigned_id, None)
            self._expired.add(assigned_id)
            future.cancel()
            raise

    async def close(self) -> None:
        if not self._active and self._reader_task is None:
            return

        self._active = False
        self._fail_pending(RuntimeError("SearchSession closed"))
        await self._queue.put(None)

        stream = self._stream
        if stream is not None:
            cancel = getattr(stream, "cancel", None)
            if callable(cancel):
                cancel()

        task = self._reader_task
        self._reader_task = None
        if task is not None and not task.done():
            task.cancel()
        if task is not None:
            with contextlib.suppress(asyncio.CancelledError):
                await task

        self._stream = None


class SearchClient:
    """Pythonic wrapper around Atuin's Search gRPC service."""

    def __init__(self, stub: SearchStub, *, timeout: float | None = 5.0) -> None:
        self._stub = stub
        self._timeout = timeout

    async def prepare_index(self, shells: Iterable[str] = ()) -> None:
        await call(
            self._stub.PrepareIndex(
                search_pb2.PrepareIndexRequest(shells=list(shells)),
                timeout=self._timeout,
            )
        )

    async def query(
        self,
        query: str,
        *,
        query_id: int | None = None,
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
        expected_id = 1 if request.query_id is None else request.query_id

        async def requests() -> AsyncIterator[search_pb2.SearchRequest]:
            yield _query_to_proto(request, default_query_id=expected_id)

        try:
            async for reply in self._stub.Search(requests(), timeout=self._timeout):
                result = _result_from_proto(reply)
                if result.query_id != expected_id:
                    msg = (
                        f"search response query_id {result.query_id} did not match request "
                        f"query_id {expected_id}"
                    )
                    raise AtuinProtocolError(msg)
                return result
        except grpc.aio.AioRpcError as exc:
            raise from_grpc_error(exc) from exc
        msg = "search stream ended before returning a response"
        raise AtuinProtocolError(msg)

    async def stream(
        self,
        queries: AsyncIterable[SearchQuery],
        *,
        timeout: float | None = None,
    ) -> AsyncIterator[SearchResult]:
        """Stream search requests and responses.

        The client-wide finite-RPC timeout is not applied to this potentially long-lived stream.
        ``timeout`` is an optional deadline for the entire stream.
        """

        async def requests() -> AsyncIterator[search_pb2.SearchRequest]:
            next_query_id = 1
            async for query in queries:
                if query.query_id is None:
                    query = replace(query, query_id=next_query_id)
                next_query_id = max(next_query_id, query.query_id + 1)
                yield _query_to_proto(query)

        try:
            async for reply in self._stub.Search(requests(), timeout=timeout):
                yield _result_from_proto(reply)
        except grpc.aio.AioRpcError as exc:
            raise from_grpc_error(exc) from exc

    def session(self) -> SearchSession:
        return SearchSession(self._stub, timeout=self._timeout)
