from __future__ import annotations

import unittest
from pathlib import Path
from typing import TYPE_CHECKING

import grpc
import pytest

from jerakeen._proto import history_pb2
from jerakeen.exceptions import AtuinConnectionError, AtuinProtocolError
from jerakeen.history import HistoryClient, _event_from_proto
from jerakeen.models import HistoryEnded, HistoryStarted

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class FakeHistoryStub:
    def __init__(self) -> None:
        self.requests: dict[str, object] = {}
        self.timeouts: dict[str, float | None] = {}
        self.tail_replies: list[history_pb2.TailHistoryReply] = []

    async def Status(self, request, *, timeout=None):
        self.requests["status"] = request
        self.timeouts["status"] = timeout
        return history_pb2.StatusReply(healthy=True, version="18.19.0", pid=42, protocol=1)

    async def StartHistory(self, request, *, timeout=None):
        self.requests["start"] = request
        self.timeouts["start"] = timeout
        return history_pb2.StartHistoryReply(id="started-id", version="18.19.0", protocol=1)

    async def EndHistory(self, request, *, timeout=None):
        self.requests["end"] = request
        self.timeouts["end"] = timeout
        return history_pb2.EndHistoryReply(id=request.id, idx=99, version="18.19.0", protocol=1)

    async def CancelHistory(self, request, *, timeout=None):
        self.requests["cancel"] = request
        self.timeouts["cancel"] = timeout
        return history_pb2.CancelHistoryReply(version="18.19.0", protocol=1)

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


def history_entry(
    *,
    timestamp: int = 1_500_000_000,
    id: str = "history-id",
    command: str = "pwd",
    cwd: str = "/tmp",
    session: str = "session",
    hostname: str = "host:user",
    author: str = "joseph",
    intent: str = "inspect cwd",
    exit: int = 0,
    duration: int = 66_000_000,
    shell: str = "zsh",
) -> history_pb2.HistoryEntry:
    return history_pb2.HistoryEntry(
        timestamp=timestamp,
        id=id,
        command=command,
        cwd=cwd,
        session=session,
        hostname=hostname,
        author=author,
        intent=intent,
        exit=exit,
        duration=duration,
        shell=shell,
    )


class HistoryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.stub = FakeHistoryStub()
        self.client = HistoryClient(self.stub)

    async def test_status_and_finite_rpc_deadline(self) -> None:
        status = await self.client.status()
        assert (status.healthy, status.version, status.pid, status.protocol) == (
            True,
            "18.19.0",
            42,
            1,
        )
        assert self.stub.timeouts["status"] == 5.0

    async def test_start_populates_all_request_fields(self) -> None:
        result = await self.client.start(
            "git status",
            cwd=Path("/tmp/repo"),
            session="session-1",
            hostname="host:user",
            author="agent",
            intent="inspect",
            shell="zsh",
            timestamp_ns=123456789,
        )
        assert (result.id, result.version, result.protocol) == ("started-id", "18.19.0", 1)
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
        ) == (
            123456789,
            "git status",
            "/tmp/repo",
            "session-1",
            "host:user",
            "agent",
            "inspect",
            "zsh",
        )
        assert self.stub.timeouts["start"] == 5.0

    async def test_start_converts_optional_strings_to_proto_defaults(self) -> None:
        await self.client.start("pwd", cwd="/tmp", session="s", hostname="h", timestamp_ns=1)
        request = self.stub.requests["start"]
        assert isinstance(request, history_pb2.StartHistoryRequest)
        assert (request.author, request.intent, request.shell) == ("", "", "")

    async def test_end(self) -> None:
        result = await self.client.end("history-id", exit_code=7, duration_ns=123)
        assert (result.id, result.idx) == ("history-id", 99)
        request = self.stub.requests["end"]
        assert isinstance(request, history_pb2.EndHistoryRequest)
        assert (request.id, request.exit, request.duration) == ("history-id", 7, 123)
        assert self.stub.timeouts["end"] == 5.0

    async def test_cancel_preserves_reply_metadata(self) -> None:
        result = await self.client.cancel("history-id")
        assert (result.version, result.protocol) == ("18.19.0", 1)
        request = self.stub.requests["cancel"]
        assert isinstance(request, history_pb2.CancelHistoryRequest)
        assert request.id == "history-id"
        assert self.stub.timeouts["cancel"] == 5.0

    async def test_shutdown(self) -> None:
        assert await self.client.shutdown()
        assert self.stub.timeouts["shutdown"] == 5.0

    async def test_tail_converts_events_without_inheriting_unary_deadline(self) -> None:
        self.stub.tail_replies = [
            history_pb2.TailHistoryReply(
                kind=history_pb2.HISTORY_EVENT_KIND_STARTED, history=history_entry()
            ),
            history_pb2.TailHistoryReply(kind=history_pb2.HISTORY_EVENT_KIND_ENDED, history=history_entry()),
        ]
        events = [event async for event in self.client.tail()]
        assert isinstance(events[0], HistoryStarted)
        assert isinstance(events[1], HistoryEnded)
        assert events[0].timestamp.timestamp() == 1.5
        assert events[1].duration_ns == 66_000_000
        assert self.stub.timeouts["tail"] is None

    async def test_tail_accepts_explicit_whole_stream_deadline(self) -> None:
        _ = [event async for event in self.client.tail(timeout=30.0)]
        assert self.stub.timeouts["tail"] == 30.0

    async def test_tail_skips_reply_without_history(self) -> None:
        self.stub.tail_replies = [
            history_pb2.TailHistoryReply(kind=history_pb2.HISTORY_EVENT_KIND_STARTED),
            history_pb2.TailHistoryReply(
                kind=history_pb2.HISTORY_EVENT_KIND_STARTED, history=history_entry()
            ),
        ]
        assert len([event async for event in self.client.tail()]) == 1

    async def test_tail_rejects_unknown_event_kind(self) -> None:
        self.stub.tail_replies = [history_pb2.TailHistoryReply(kind=999, history=history_entry())]
        with pytest.raises(AtuinProtocolError, match="unknown history event kind"):
            _ = [event async for event in self.client.tail()]

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

    def test_event_conversion_rejects_missing_history(self) -> None:
        with pytest.raises(AtuinProtocolError, match="did not contain a history entry"):
            _event_from_proto(history_pb2.TailHistoryReply())

    async def test_command_context_allows_exit_status_after_execution(self) -> None:
        async with self.client.command("pwd", cwd="/tmp", session="s", hostname="h") as command:
            assert command.id == "started-id"
            command.exit_code = 17
            command.duration_ns = 1234

        request = self.stub.requests["end"]
        assert isinstance(request, history_pb2.EndHistoryRequest)
        assert (request.exit, request.duration) == (17, 1234)
        assert "cancel" not in self.stub.requests

    async def test_command_context_preserves_initial_exit_code_compatibility(self) -> None:
        async with self.client.command("pwd", cwd="/tmp", session="s", hostname="h", exit_code=3) as command:
            assert command.exit_code == 3
        request = self.stub.requests["end"]
        assert isinstance(request, history_pb2.EndHistoryRequest)
        assert request.exit == 3
        assert request.duration > 0

    async def test_command_context_manager_cancels_on_exception(self) -> None:
        with pytest.raises(RuntimeError, match="boom"):
            async with self.client.command("pwd", cwd="/tmp", session="s", hostname="h"):
                msg = "boom"
                raise RuntimeError(msg)
        assert "end" not in self.stub.requests
        assert isinstance(self.stub.requests["cancel"], history_pb2.CancelHistoryRequest)


if __name__ == "__main__":
    unittest.main()
