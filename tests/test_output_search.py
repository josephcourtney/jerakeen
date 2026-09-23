from __future__ import annotations

import unittest
from uuid import UUID

import grpc
import pytest

from jerakeen._ids import history_id_to_proto
from jerakeen._proto import common_pb2, search_pb2
from jerakeen.exceptions import AtuinConnectionError, AtuinProtocolError
from jerakeen.search import SearchClient

HISTORY_ID = UUID("00112233-4455-6677-8899-aabbccddeeff")


class OutputSearchStub:
    def __init__(self) -> None:
        self.request: search_pb2.SearchCommandOutputRequest | None = None
        self.timeout: float | None = None
        self.replies = [
            search_pb2.OutputSearchMatch(
                history_id=history_id_to_proto(HISTORY_ID),
                lines=[
                    search_pb2.OutputSearchLine(
                        line=12,
                        content=common_pb2.HighlightedText(open=3, close=8, raw="abcTRACEbackxyz"),
                    )
                ],
                score=4.25,
            )
        ]

    def SearchCommandOutput(self, request, *, timeout=None):
        self.request = request
        self.timeout = timeout

        async def stream():
            for reply in self.replies:
                yield reply

        return stream()


class OutputSearchTests(unittest.IsolatedAsyncioTestCase):
    async def test_output_search_preserves_query_limit_context_and_matches(self) -> None:
        stub = OutputSearchStub()
        results = [result async for result in SearchClient(stub).output("traceback", limit=20, context=2)]
        assert stub.request is not None
        assert stub.request.query == "traceback"
        assert stub.request.limit == 20
        assert stub.request.HasField("context")
        assert stub.request.context == 2
        assert stub.timeout is None

        assert len(results) == 1
        result = results[0]
        assert result.history_id == HISTORY_ID
        assert result.score == 4.25
        assert result.lines[0].line == 12
        assert result.lines[0].content.raw == "abcTRACEbackxyz"
        assert (result.lines[0].content.open, result.lines[0].content.close) == (3, 8)

    async def test_output_search_omits_optional_context(self) -> None:
        stub = OutputSearchStub()
        _ = [result async for result in SearchClient(stub).output("x")]
        assert stub.request is not None
        assert not stub.request.HasField("context")

    async def test_output_search_accepts_explicit_stream_deadline(self) -> None:
        stub = OutputSearchStub()
        _ = [result async for result in SearchClient(stub).output("x", timeout=30.0)]
        assert stub.timeout == 30.0

    async def test_output_search_validates_uint32_values(self) -> None:
        client = SearchClient(OutputSearchStub())
        with pytest.raises(ValueError, match="limit"):
            _ = [result async for result in client.output("x", limit=-1)]
        with pytest.raises(ValueError, match="context"):
            _ = [result async for result in client.output("x", context=2**32)]

    async def test_output_search_rejects_missing_history_id(self) -> None:
        stub = OutputSearchStub()
        stub.replies = [search_pb2.OutputSearchMatch()]
        with pytest.raises(AtuinProtocolError, match="history id"):
            _ = [result async for result in SearchClient(stub).output("x")]

    async def test_output_search_rejects_missing_highlight_content(self) -> None:
        stub = OutputSearchStub()
        stub.replies = [
            search_pb2.OutputSearchMatch(
                history_id=history_id_to_proto(HISTORY_ID),
                lines=[search_pb2.OutputSearchLine(line=1)],
            )
        ]
        with pytest.raises(AtuinProtocolError, match="did not contain content"):
            _ = [result async for result in SearchClient(stub).output("x")]

    async def test_output_search_translates_grpc_errors(self) -> None:
        error = grpc.aio.AioRpcError(
            grpc.StatusCode.UNAVAILABLE,
            grpc.aio.Metadata(),
            grpc.aio.Metadata(),
            details="output search unavailable",
        )

        class ErrorStub(OutputSearchStub):
            def SearchCommandOutput(self, request, *, timeout=None):
                async def stream():
                    if False:
                        yield search_pb2.OutputSearchMatch()
                    raise error

                return stream()

        with pytest.raises(AtuinConnectionError, match="output search unavailable"):
            _ = [result async for result in SearchClient(ErrorStub()).output("x")]


if __name__ == "__main__":
    unittest.main()
