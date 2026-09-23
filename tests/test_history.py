from __future__ import annotations

import unittest
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch
from uuid import UUID

import grpc
import pytest

from jerakeen._ids import history_id_to_proto
from jerakeen._proto import common_pb2, history_pb2
from jerakeen.exceptions import AtuinConnectionError, AtuinNotFoundError, AtuinProtocolError
from jerakeen.history import HistoryClient, _event_from_proto
from jerakeen.models import (
    AuthorKind,
    CommandCapture,
    CommandCaptureMeta,
    HistoryCancelled,
    HistoryEnded,
    HistoryLagged,
    HistoryStarted,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

HISTORY_ID = UUID("00112233-4455-6677-8899-aabbccddeeff")
RECORD_ID = UUID("ffeeddcc-bbaa-9988-7766-554433221100")


def history_entry(
    *,
    history_id: UUID = HISTORY_ID,
    timestamp: int = 1_500_000_000,
    exit_code: int = 0,
    duration: int = 66_000_000,
) -> history_pb2.HistoryEntry:
    return history_pb2.HistoryEntry(
        timestamp=timestamp,
        id=history_id_to_proto(history_id),
        command="pwd",
        cwd="/tmp",
        session="session",
        hostname="host:user",
        author="joseph",
        intent="inspect cwd",
        exit=exit_code,
        duration=duration,
        shell="zsh",
        author_kind=history_pb2.AUTHOR_KIND_USER,
    )


class FakeHistoryStub:
    def __init__(self) -> None:
        self.requests: dict[str, object] = {}
        self.timeouts: dict[str, float | None] = {}
        self.delete_requests: list[history_pb2.DeleteHistoryRequest] = []
        self.tail_replies: list[history_pb2.TailHistoryReply] = []
        self.output_reply: history_pb2.GetCommandOutputResponse | None = history_pb2.GetCommandOutputResponse(
            chunks=[
                history_pb2.OutputChunk(
                    line_range=common_pb2.PyStyleIdxRange(start=0, end=1),
                    content="one\ntwo",
                )
            ],
            total_bytes=7,
            total_lines=2,
            meta=history_pb2.CommandCaptureMeta(
                output_observed_bytes=9,
                terminal_width=120,
                terminal_height=40,
            ),
            truncated=False,
        )
        self.output_error: Exception | None = None

    async def Status(self, request, *, timeout=None):
        self.requests["status"] = request
        self.timeouts["status"] = timeout
        return history_pb2.StatusReply(healthy=True, version="18.23.0", pid=42, protocol=3)

    async def StartHistory(self, request, *, timeout=None):
        self.requests["start"] = request
        self.timeouts["start"] = timeout
        return history_pb2.StartHistoryReply(
            id=history_id_to_proto(HISTORY_ID), version="18.23.0", protocol=3
        )

    async def EndHistory(self, request, *, timeout=None):
        self.requests["end"] = request
        self.timeouts["end"] = timeout
        return history_pb2.EndHistoryReply(
            record_id=common_pb2.RecordId(uuid=common_pb2.Uuid(value=RECORD_ID.bytes)),
            record_idx=99,
            version="18.23.0",
            protocol=3,
        )

    async def CancelHistory(self, request, *, timeout=None):
        self.requests["cancel"] = request
        self.timeouts["cancel"] = timeout
        return history_pb2.CancelHistoryReply(version="18.23.0", protocol=3)

    async def DeleteHistory(self, requests, *, timeout=None):
        self.timeouts["delete"] = timeout
        async for request in requests:
            self.delete_requests.append(request)
        return history_pb2.DeleteHistoryReply(deleted=3, version="18.23.0", protocol=3)

    async def RebuildHistory(self, request, *, timeout=None):
        self.requests["rebuild"] = request
        self.timeouts["rebuild"] = timeout
        return history_pb2.RebuildHistoryReply(version="18.23.0", protocol=3)

    async def Shutdown(self, request, *, timeout=None):
        self.requests["shutdown"] = request
        self.timeouts["shutdown"] = timeout
        return history_pb2.ShutdownReply(accepted=True)

    def TailHistory(self, request, *, timeout=None) -> AsyncIterator[history_pb2.TailHistoryReply]:
        self.requests["tail"] = request
        self.timeouts["tail"] = timeout

        async def replies():
            for reply in self.tail_replies:
                yield reply

        return replies()

    async def RegisterCommandOutput(self, request, *, timeout=None):
        self.requests["register_output"] = request
        self.timeouts["register_output"] = timeout
        return history_pb2.RegisterCommandOutputResponse()

    async def GetCommandOutput(self, request, *, timeout=None):
        self.requests["output"] = request
        self.timeouts["output"] = timeout
        if self.output_error is not None:
            raise self.output_error
        assert self.output_reply is not None
        return self.output_reply


class HistoryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.stub = FakeHistoryStub()
        self.client = HistoryClient(self.stub)

    async def test_status_and_finite_rpc_deadline(self) -> None:
        status = await self.client.status()
        assert (status.healthy, status.version, status.pid, status.protocol) == (
            True,
            "18.23.0",
            42,
            3,
        )
        assert self.stub.timeouts["status"] == 5.0

    async def test_start_populates_protocol3_fields(self) -> None:
        result = await self.client.start(
            "git status",
            cwd=Path("/tmp/repo"),
            session="session-1",
            hostname="host:user",
            author="agent",
            intent="inspect",
            shell="zsh",
            author_kind=AuthorKind.AGENT,
            timestamp_ns=123456789,
        )
        assert result.id == HISTORY_ID
        assert (result.version, result.protocol) == ("18.23.0", 3)
        request = self.stub.requests["start"]
        assert isinstance(request, history_pb2.StartHistoryRequest)
        assert (
            request.timestamp,
            request.command,
            request.cwd,
            request.session,
            request.hostname,
            request.author,
            request.intent,
            request.shell,
            request.author_kind,
        ) == (
            123456789,
            "git status",
            "/tmp/repo",
            "session-1",
            "host:user",
            "agent",
            "inspect",
            "zsh",
            history_pb2.AUTHOR_KIND_AGENT,
        )

    async def test_end_encodes_duration_and_record_reply(self) -> None:
        result = await self.client.end(HISTORY_ID, exit_code=7, duration_ns=2_000_000_123)
        assert (result.record_id, result.record_idx) == (RECORD_ID, 99)
        request = self.stub.requests["end"]
        assert isinstance(request, history_pb2.EndHistoryRequest)
        assert bytes(request.id.uuid.value) == HISTORY_ID.bytes
        assert request.exit == 7
        assert request.HasField("duration")
        assert (request.duration.seconds, request.duration.nanos) == (2, 123)

    async def test_end_can_omit_duration(self) -> None:
        await self.client.end(HISTORY_ID, exit_code=0)
        request = self.stub.requests["end"]
        assert isinstance(request, history_pb2.EndHistoryRequest)
        assert not request.HasField("duration")

    async def test_end_rejects_negative_duration(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            await self.client.end(HISTORY_ID, exit_code=0, duration_ns=-1)

    async def test_cancel_delete_rebuild_and_shutdown(self) -> None:
        cancelled = await self.client.cancel(HISTORY_ID)
        assert (cancelled.version, cancelled.protocol) == ("18.23.0", 3)

        ids = [HISTORY_ID, UUID(int=2), UUID(int=3)]
        with patch("jerakeen.history._DELETE_CHUNK_SIZE", 2):
            deleted = await self.client.delete(ids)
        assert deleted.deleted == 3
        assert [len(request.ids) for request in self.stub.delete_requests] == [2, 1]
        decoded = [
            UUID(bytes=bytes(identifier.uuid.value))
            for request in self.stub.delete_requests
            for identifier in request.ids
        ]
        assert decoded == ids

        rebuilt = await self.client.rebuild()
        assert (rebuilt.version, rebuilt.protocol) == ("18.23.0", 3)
        assert await self.client.shutdown()

    async def test_tail_preserves_all_protocol3_event_kinds(self) -> None:
        self.stub.tail_replies = [
            history_pb2.TailHistoryReply(started=history_entry()),
            history_pb2.TailHistoryReply(ended=history_entry(exit_code=5)),
            history_pb2.TailHistoryReply(cancelled=history_entry()),
            history_pb2.TailHistoryReply(lagged=history_pb2.Lagged(dropped=12)),
        ]
        events = [event async for event in self.client.tail()]
        assert isinstance(events[0], HistoryStarted)
        assert isinstance(events[1], HistoryEnded)
        assert isinstance(events[2], HistoryCancelled)
        assert isinstance(events[3], HistoryLagged)
        assert events[0].id == HISTORY_ID
        assert events[0].author_kind is AuthorKind.USER
        assert events[1].duration_ns == 66_000_000
        assert events[3].dropped == 12
        assert self.stub.timeouts["tail"] is None

    async def test_tail_accepts_explicit_whole_stream_deadline(self) -> None:
        _ = [event async for event in self.client.tail(timeout=30.0)]
        assert self.stub.timeouts["tail"] == 30.0

    def test_event_conversion_rejects_missing_event(self) -> None:
        with pytest.raises(AtuinProtocolError, match="recognized event"):
            _event_from_proto(history_pb2.TailHistoryReply())

    def test_event_conversion_rejects_unknown_author_kind(self) -> None:
        entry = history_entry()
        entry.author_kind = 999
        with pytest.raises(AtuinProtocolError, match="unknown author_kind"):
            _event_from_proto(history_pb2.TailHistoryReply(started=entry))

    async def test_tail_translates_grpc_errors(self) -> None:
        error = grpc.aio.AioRpcError(
            grpc.StatusCode.UNAVAILABLE,
            grpc.aio.Metadata(),
            grpc.aio.Metadata(),
            details="tail unavailable",
        )

        class ErrorStub(FakeHistoryStub):
            def TailHistory(self, request, *, timeout=None):
                async def replies():
                    if False:
                        yield history_pb2.TailHistoryReply()
                    raise error

                return replies()

        with pytest.raises(AtuinConnectionError, match="tail unavailable"):
            _ = [event async for event in HistoryClient(ErrorStub()).tail()]

    async def test_whole_output_uses_explicit_full_range_and_decodes_metadata(self) -> None:
        output = await self.client.output(HISTORY_ID)
        assert output is not None
        assert output.text == "one\ntwo"
        assert output.total_bytes == 7
        assert output.total_lines == 2
        assert output.chunks[0].start_line == 0
        assert output.chunks[0].end_line == 1
        assert output.observed_bytes == 9
        assert output.meta.terminal_width == 120
        request = self.stub.requests["output"]
        assert isinstance(request, history_pb2.GetCommandOutputRequest)
        assert [(item.start, item.end) for item in request.line_ranges] == [(0, -1)]

    async def test_output_preserves_explicit_ranges_and_truncated_chunks(self) -> None:
        self.stub.output_reply = history_pb2.GetCommandOutputResponse(
            chunks=[
                history_pb2.OutputChunk(
                    line_range=common_pb2.PyStyleIdxRange(start=0, end=1), content="head"
                ),
                history_pb2.OutputChunk(
                    line_range=common_pb2.PyStyleIdxRange(start=-2, end=-1), content="tail"
                ),
            ],
            total_bytes=1000,
            total_lines=100,
            meta=history_pb2.CommandCaptureMeta(output_observed_bytes=2000),
            truncated=True,
        )
        output = await self.client.output(HISTORY_ID, ranges=[(0, 3), slice(-4, -1)])
        assert output is not None
        assert output.text == "head\ntail"
        assert output.truncated
        assert [(chunk.start_line, chunk.end_line) for chunk in output.chunks] == [(0, 1), (-2, -1)]
        request = self.stub.requests["output"]
        assert isinstance(request, history_pb2.GetCommandOutputRequest)
        assert [(item.start, item.end) for item in request.line_ranges] == [(0, 3), (-4, -1)]

    async def test_output_not_found_is_none(self) -> None:
        self.stub.output_error = AtuinNotFoundError("missing")
        assert await self.client.output(HISTORY_ID) is None

    async def test_output_rejects_missing_required_metadata(self) -> None:
        self.stub.output_reply = history_pb2.GetCommandOutputResponse()
        with pytest.raises(AtuinProtocolError, match="capture metadata"):
            await self.client.output(HISTORY_ID)

    async def test_output_rejects_chunk_without_range(self) -> None:
        self.stub.output_reply = history_pb2.GetCommandOutputResponse(
            chunks=[history_pb2.OutputChunk(content="broken")],
            meta=history_pb2.CommandCaptureMeta(),
        )
        with pytest.raises(AtuinProtocolError, match="has no line range"):
            await self.client.output(HISTORY_ID)

    async def test_register_output_preserves_optional_tail_and_metadata(self) -> None:
        capture = CommandCapture(
            output_start="head",
            output_end="tail",
            meta=CommandCaptureMeta(observed_bytes=400, terminal_width=100, terminal_height=30),
        )
        await self.client.register_output(HISTORY_ID, capture)
        request = self.stub.requests["register_output"]
        assert isinstance(request, history_pb2.RegisterCommandOutputRequest)
        assert bytes(request.history_id.uuid.value) == HISTORY_ID.bytes
        assert request.capture.output_start == "head"
        assert request.capture.HasField("output_end")
        assert request.capture.output_end == "tail"
        assert request.capture.meta.output_observed_bytes == 400
        assert request.capture.meta.terminal_width == 100
        assert request.capture.meta.terminal_height == 30

    async def test_command_context_records_completion(self) -> None:
        async with self.client.command("pwd", cwd="/tmp", session="s", hostname="h") as command:
            assert command.id == HISTORY_ID
            command.exit_code = 17
            command.duration_ns = 1234
        request = self.stub.requests["end"]
        assert isinstance(request, history_pb2.EndHistoryRequest)
        assert request.exit == 17
        assert request.duration.nanos == 1234
        assert "cancel" not in self.stub.requests

    async def test_command_context_cancels_on_exception(self) -> None:
        with pytest.raises(RuntimeError, match="boom"):
            async with self.client.command("pwd", cwd="/tmp", session="s", hostname="h"):
                raise RuntimeError("boom")
        assert "end" not in self.stub.requests
        assert isinstance(self.stub.requests["cancel"], history_pb2.CancelHistoryRequest)


if __name__ == "__main__":
    unittest.main()
