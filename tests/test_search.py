from __future__ import annotations

import unittest
from typing import TYPE_CHECKING

import grpc
import pytest

from jerakeen._proto import search_pb2
from jerakeen.exceptions import AtuinConnectionError, AtuinProtocolError
from jerakeen.models import FilterMode, SearchContext, SearchQuery
from jerakeen.search import SearchClient, _query_to_proto

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, AsyncIterator


class FakeSearchStub:
    def __init__(self) -> None:
        self.prepare_request: search_pb2.PrepareIndexRequest | None = None
        self.search_requests: list[search_pb2.SearchRequest] = []
        self.return_responses = True
        self.end_immediately = False

    async def PrepareIndex(self, request: search_pb2.PrepareIndexRequest) -> search_pb2.PrepareIndexResponse:
        self.prepare_request = request
        return search_pb2.PrepareIndexResponse()

    def Search(
        self, requests: AsyncIterable[search_pb2.SearchRequest]
    ) -> AsyncIterator[search_pb2.SearchResponse]:
        async def replies():
            if self.end_immediately:
                return
            async for request in requests:
                self.search_requests.append(request)
                if self.return_responses:
                    yield search_pb2.SearchResponse(
                        query_id=request.query_id,
                        ids=[f"id-{request.query_id}".encode()],
                    )

        return replies()


class SearchTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.stub = FakeSearchStub()
        self.client = SearchClient(self.stub)

    def test_all_filter_modes_map_to_proto_values(self) -> None:
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
                request = _query_to_proto(SearchQuery(query="git", filter_mode=mode))
                assert request.filter_mode == proto_value

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

    def test_query_to_proto_omits_optional_context_and_git_root(self) -> None:
        request = _query_to_proto(SearchQuery(query="git"))
        assert not request.HasField("context")

        request = _query_to_proto(SearchQuery(query="git", context=SearchContext(cwd="/tmp")))
        assert request.HasField("context")
        assert not request.context.HasField("git_root")

    async def test_prepare_index(self) -> None:
        assert await self.client.prepare_index(["zsh", "bash"]) is None
        request = self.stub.prepare_request
        assert request is not None
        assert list(request.shells) == ["zsh", "bash"]

    async def test_query(self) -> None:
        result = await self.client.query(
            "git",
            query_id=7,
            filter_mode=FilterMode.DIRECTORY,
            context=SearchContext(cwd="/tmp"),
            shells=["zsh"],
        )
        assert result.query_id == 7
        assert result.ids == (b"id-7",)
        assert len(self.stub.search_requests) == 1
        request = self.stub.search_requests[0]
        assert request.query == "git"
        assert request.filter_mode == search_pb2.DIRECTORY
        assert request.context.cwd == "/tmp"
        assert list(request.shells) == ["zsh"]

    async def test_query_rejects_stream_that_ends_without_response(self) -> None:
        self.stub.end_immediately = True
        with pytest.raises(AtuinProtocolError, match="ended before returning a response"):
            await self.client.query("git")

    async def test_stream_multiple_queries(self) -> None:
        async def queries():
            yield SearchQuery(query="g", query_id=1)
            yield SearchQuery(query="gi", query_id=2, filter_mode=FilterMode.HOST)
            yield SearchQuery(query="git", query_id=3, shells=("zsh",))

        results = [result async for result in self.client.stream(queries())]
        assert [result.query_id for result in results] == [1, 2, 3]
        assert [result.ids for result in results] == [(b"id-1",), (b"id-2",), (b"id-3",)]
        assert [request.query for request in self.stub.search_requests] == ["g", "gi", "git"]

    async def test_query_stream_and_session_translate_grpc_errors(self) -> None:
        error = grpc.aio.AioRpcError(
            grpc.StatusCode.UNAVAILABLE,
            grpc.aio.Metadata(),
            grpc.aio.Metadata(),
            details="search unavailable",
        )

        class ErrorStub(FakeSearchStub):
            def Search(
                self, requests: AsyncIterable[search_pb2.SearchRequest]
            ) -> AsyncIterator[search_pb2.SearchResponse]:
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

    async def test_session_supports_string_queries_and_incremental_ids(self) -> None:
        async with self.client.session() as session:
            first = await session.query("g", query_id=10)
            second = await session.query(
                "git",
                query_id=11,
                filter_mode=FilterMode.SESSION,
                context=SearchContext(session_id="session"),
            )
        assert first.query_id == 10
        assert second.query_id == 11
        assert [request.query_id for request in self.stub.search_requests] == [10, 11]
        assert self.stub.search_requests[1].filter_mode == search_pb2.SESSION

    async def test_session_accepts_search_query_object(self) -> None:
        async with self.client.session() as session:
            result = await session.query(
                SearchQuery(
                    query="git",
                    query_id=22,
                    filter_mode=FilterMode.WORKSPACE,
                    context=SearchContext(git_root="/repo"),
                    shells=("fish",),
                )
            )
        assert result.query_id == 22
        request = self.stub.search_requests[0]
        assert request.query_id == 22
        assert request.context.git_root == "/repo"
        assert list(request.shells) == ["fish"]

    async def test_session_rejects_stream_that_ends_without_response(self) -> None:
        self.stub.end_immediately = True
        async with self.client.session() as session:
            with pytest.raises(AtuinProtocolError, match="ended before returning a response"):
                await session.query("git")

    async def test_session_close_is_idempotent(self) -> None:
        session = self.client.session()
        await session.close()
        async with session:
            await session.query("git")
            await session.close()
            await session.close()


if __name__ == "__main__":
    unittest.main()
