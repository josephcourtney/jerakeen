from __future__ import annotations

import asyncio
import unittest
from typing import TYPE_CHECKING
from uuid import UUID

import grpc
import pytest

from jerakeen._proto import search_pb2
from jerakeen.exceptions import AtuinConnectionError, AtuinProtocolError, AtuinTimeoutError
from jerakeen.models import FilterMode, SearchContext, SearchQuery
from jerakeen.search import SearchClient, _query_to_proto, _result_from_proto

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, AsyncIterator


def result_id(query_id: int) -> bytes:
    return UUID(int=query_id).bytes


class FakeSearchStub:
    def __init__(self) -> None:
        self.prepare_request: search_pb2.PrepareIndexRequest | None = None
        self.prepare_timeout: float | None = None
        self.search_requests: list[search_pb2.SearchRequest] = []
        self.search_timeouts: list[float | None] = []
        self.return_responses = True
        self.end_immediately = False

    async def PrepareIndex(
        self, request: search_pb2.PrepareIndexRequest, *, timeout: float | None = None
    ) -> search_pb2.PrepareIndexResponse:
        self.prepare_request = request
        self.prepare_timeout = timeout
        return search_pb2.PrepareIndexResponse()

    def Search(
        self,
        requests: AsyncIterable[search_pb2.SearchRequest],
        *,
        timeout: float | None = None,
    ) -> AsyncIterator[search_pb2.SearchResponse]:
        self.search_timeouts.append(timeout)

        async def replies():
            if self.end_immediately:
                return
            async for request in requests:
                self.search_requests.append(request)
                if self.return_responses:
                    yield search_pb2.SearchResponse(
                        query_id=request.query_id,
                        ids=[result_id(request.query_id)],
                    )

        return replies()


class SearchTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.stub = FakeSearchStub()
        self.client = SearchClient(self.stub)

    def test_all_filter_modes_map_to_proto_values(self) -> None:
        contexts = {
            FilterMode.GLOBAL: None,
            FilterMode.HOST: SearchContext(hostname="host:user"),
            FilterMode.SESSION: SearchContext(session_id="session"),
            FilterMode.DIRECTORY: SearchContext(cwd="/tmp"),
            FilterMode.WORKSPACE: SearchContext(git_root="/tmp/repo"),
            FilterMode.SESSION_PRELOAD: SearchContext(session_id="session"),
        }
        expected = {
            FilterMode.GLOBAL: search_pb2.GLOBAL,
            FilterMode.HOST: search_pb2.HOST,
            FilterMode.SESSION: search_pb2.SESSION,
            FilterMode.DIRECTORY: search_pb2.DIRECTORY,
            FilterMode.WORKSPACE: search_pb2.WORKSPACE,
            FilterMode.SESSION_PRELOAD: search_pb2.SESSION_PRELOAD,
        }
        for mode, proto_value in expected.items():
            with self.subTest(mode=mode):
                request = _query_to_proto(SearchQuery(query="git", filter_mode=mode, context=contexts[mode]))
                assert request.filter_mode == proto_value

    def test_filter_modes_reject_missing_required_context(self) -> None:
        for mode in FilterMode:
            if mode is FilterMode.GLOBAL:
                continue
            with self.subTest(mode=mode), pytest.raises(ValueError, match="requires"):
                SearchQuery(query="git", filter_mode=mode)

        with pytest.raises(ValueError, match="hostname"):
            SearchQuery(query="git", filter_mode=FilterMode.HOST, context=SearchContext())
        with pytest.raises(ValueError, match="session_id"):
            SearchQuery(query="git", filter_mode=FilterMode.SESSION, context=SearchContext())
        with pytest.raises(ValueError, match="cwd"):
            SearchQuery(query="git", filter_mode=FilterMode.DIRECTORY, context=SearchContext())
        with pytest.raises(ValueError, match="git_root or context.cwd"):
            SearchQuery(query="git", filter_mode=FilterMode.WORKSPACE, context=SearchContext())

    def test_workspace_accepts_git_root_or_cwd_fallback(self) -> None:
        SearchQuery(
            query="git",
            filter_mode=FilterMode.WORKSPACE,
            context=SearchContext(git_root="/repo"),
        )
        SearchQuery(
            query="git",
            filter_mode=FilterMode.WORKSPACE,
            context=SearchContext(cwd="/repo/subdir"),
        )

    def test_query_to_proto_preserves_context_shells_and_optional_git_root(self) -> None:
        request = _query_to_proto(
            SearchQuery(
                query="git status",
                query_id=42,
                filter_mode=FilterMode.WORKSPACE,
                context=SearchContext(
                    session_id="session",
                    cwd="/tmp/repo",
                    hostname="host:user",
                    host_id="host-id",
                    git_root="/tmp/repo",
                ),
                shells=("zsh", "bash"),
            )
        )
        assert request.query == "git status"
        assert request.query_id == 42
        assert request.filter_mode == search_pb2.WORKSPACE
        assert request.HasField("context")
        assert request.context.session_id == "session"
        assert request.context.cwd == "/tmp/repo"
        assert request.context.hostname == "host:user"
        assert request.context.host_id == "host-id"
        assert request.context.HasField("git_root")
        assert request.context.git_root == "/tmp/repo"
        assert list(request.shells) == ["zsh", "bash"]

    def test_query_to_proto_assigns_default_id_and_omits_optional_context(self) -> None:
        request = _query_to_proto(SearchQuery(query="git"))
        assert request.query_id == 1
        assert not request.HasField("context")

    def test_result_converts_history_ids_to_uuid(self) -> None:
        expected = UUID("00112233-4455-6677-8899-aabbccddeeff")
        result = _result_from_proto(search_pb2.SearchResponse(query_id=4, ids=[expected.bytes]))
        assert result.ids == (expected,)

    def test_result_rejects_malformed_history_id(self) -> None:
        with pytest.raises(AtuinProtocolError, match="expected 16"):
            _result_from_proto(search_pb2.SearchResponse(query_id=4, ids=[b"not-a-uuid"]))

    async def test_prepare_index_uses_client_deadline(self) -> None:
        assert await self.client.prepare_index(["zsh", "bash"]) is None
        assert self.stub.prepare_timeout == 5.0
        assert list(self.stub.prepare_request.shells) == ["zsh", "bash"]

    async def test_query_uses_deadline_and_pythonic_uuid(self) -> None:
        result = await self.client.query(
            "git",
            query_id=7,
            filter_mode=FilterMode.DIRECTORY,
            context=SearchContext(cwd="/tmp"),
            shells=["zsh"],
        )
        assert result.query_id == 7
        assert result.ids == (UUID(int=7),)
        assert self.stub.search_timeouts == [5.0]
        request = self.stub.search_requests[0]
        assert request.filter_mode == search_pb2.DIRECTORY
        assert request.context.cwd == "/tmp"

    async def test_query_auto_assigns_id(self) -> None:
        result = await self.client.query("git")
        assert result.query_id == 1
        assert self.stub.search_requests[0].query_id == 1

    async def test_query_rejects_mismatched_response_id(self) -> None:
        class WrongIdStub(FakeSearchStub):
            def Search(self, requests, *, timeout=None):
                async def replies():
                    async for request in requests:
                        yield search_pb2.SearchResponse(
                            query_id=request.query_id + 1,
                            ids=[result_id(request.query_id + 1)],
                        )

                return replies()

        with pytest.raises(AtuinProtocolError, match="did not match"):
            await SearchClient(WrongIdStub()).query("git", query_id=10)

    async def test_query_rejects_stream_that_ends_without_response(self) -> None:
        self.stub.end_immediately = True
        with pytest.raises(AtuinProtocolError, match="ended before returning a response"):
            await self.client.query("git")

    async def test_stream_auto_assigns_ids_without_unary_deadline(self) -> None:
        async def queries():
            yield SearchQuery(query="g")
            yield SearchQuery(
                query="gi",
                filter_mode=FilterMode.HOST,
                context=SearchContext(hostname="host"),
            )
            yield SearchQuery(query="git", query_id=9, shells=("zsh",))

        results = [result async for result in self.client.stream(queries())]
        assert [result.query_id for result in results] == [1, 2, 9]
        assert [result.ids for result in results] == [
            (UUID(int=1),),
            (UUID(int=2),),
            (UUID(int=9),),
        ]
        assert self.stub.search_timeouts == [None]

    async def test_query_stream_and_session_translate_grpc_errors(self) -> None:
        error = grpc.aio.AioRpcError(
            grpc.StatusCode.UNAVAILABLE,
            grpc.aio.Metadata(),
            grpc.aio.Metadata(),
            details="search unavailable",
        )

        class ErrorStub(FakeSearchStub):
            def Search(self, requests, *, timeout=None):
                async def replies():
                    if False:
                        yield search_pb2.SearchResponse()
                    raise error

                return replies()

        client = SearchClient(ErrorStub())
        with pytest.raises(AtuinConnectionError, match="search unavailable"):
            await client.query("git")

        async def queries():
            yield SearchQuery(query="git")

        with pytest.raises(AtuinConnectionError, match="search unavailable"):
            _ = [result async for result in client.stream(queries())]

        async with client.session() as session:
            with pytest.raises(AtuinConnectionError, match="search unavailable"):
                await session.query("git")

    async def test_session_requires_async_context_manager(self) -> None:
        session = self.client.session()
        with pytest.raises(RuntimeError, match="async context manager"):
            await session.query("git")

    async def test_session_allocates_incremental_ids(self) -> None:
        async with self.client.session() as session:
            first = await session.query("g")
            second = await session.query("git")
        assert (first.query_id, second.query_id) == (1, 2)
        assert [request.query_id for request in self.stub.search_requests] == [1, 2]
        assert self.stub.search_timeouts == [None]

    async def test_session_routes_concurrent_out_of_order_responses(self) -> None:
        class OutOfOrderStub(FakeSearchStub):
            def Search(self, requests, *, timeout=None):
                async def replies():
                    batch = []
                    async for request in requests:
                        self.search_requests.append(request)
                        batch.append(request)
                        if len(batch) == 2:
                            second, first = batch[1], batch[0]
                            yield search_pb2.SearchResponse(
                                query_id=second.query_id, ids=[result_id(second.query_id)]
                            )
                            yield search_pb2.SearchResponse(
                                query_id=first.query_id, ids=[result_id(first.query_id)]
                            )
                            batch.clear()

                return replies()

        client = SearchClient(OutOfOrderStub())
        async with client.session() as session:
            first_task = asyncio.create_task(session.query("first"))
            second_task = asyncio.create_task(session.query("second"))
            first, second = await asyncio.gather(first_task, second_task)
        assert (first.query_id, second.query_id) == (1, 2)
        assert (first.ids, second.ids) == ((UUID(int=1),), (UUID(int=2),))

    async def test_session_rejects_duplicate_outstanding_explicit_id(self) -> None:
        class SlowStub(FakeSearchStub):
            def Search(self, requests, *, timeout=None):
                async def replies():
                    async for request in requests:
                        self.search_requests.append(request)
                        await asyncio.sleep(10)
                        yield search_pb2.SearchResponse(
                            query_id=request.query_id, ids=[result_id(request.query_id)]
                        )

                return replies()

        client = SearchClient(SlowStub(), timeout=None)
        async with client.session() as session:
            first = asyncio.create_task(session.query("first", query_id=8))
            await asyncio.sleep(0)
            with pytest.raises(ValueError, match="already outstanding"):
                await session.query("second", query_id=8)
            first.cancel()
            with pytest.raises(asyncio.CancelledError):
                await first

    async def test_session_query_timeout_does_not_poison_session(self) -> None:
        class DelayedFirstStub(FakeSearchStub):
            def Search(self, requests, *, timeout=None):
                async def replies():
                    first = True
                    async for request in requests:
                        if first:
                            first = False
                            await asyncio.sleep(0.03)
                        yield search_pb2.SearchResponse(
                            query_id=request.query_id, ids=[result_id(request.query_id)]
                        )

                return replies()

        client = SearchClient(DelayedFirstStub(), timeout=0.01)
        async with client.session() as session:
            with pytest.raises(AtuinTimeoutError, match="deadline"):
                await session.query("slow")
            await asyncio.sleep(0.03)
            result = await session.query("fast")
        assert result.query_id == 2

    async def test_session_does_not_reuse_timed_out_id_before_late_response(self) -> None:
        class NeverReplyStub(FakeSearchStub):
            def Search(self, requests, *, timeout=None):
                async def replies():
                    async for _request in requests:
                        await asyncio.sleep(10)
                        if False:
                            yield search_pb2.SearchResponse()

                return replies()

        client = SearchClient(NeverReplyStub(), timeout=0.001)
        async with client.session() as session:
            with pytest.raises(AtuinTimeoutError):
                await session.query("first", query_id=7)
            with pytest.raises(ValueError, match="stale response"):
                await session.query("second", query_id=7)

    async def test_session_rejects_unknown_response_id(self) -> None:
        class WrongIdStub(FakeSearchStub):
            def Search(self, requests, *, timeout=None):
                async def replies():
                    async for request in requests:
                        yield search_pb2.SearchResponse(
                            query_id=request.query_id + 100,
                            ids=[result_id(request.query_id + 100)],
                        )

                return replies()

        async with SearchClient(WrongIdStub()).session() as session:
            with pytest.raises(AtuinProtocolError, match="unknown query_id"):
                await session.query("git")

    async def test_session_close_is_idempotent(self) -> None:
        session = self.client.session()
        await session.close()
        async with session:
            assert (await session.query("git")).query_id == 1
            await session.close()
            await session.close()


if __name__ == "__main__":
    unittest.main()
