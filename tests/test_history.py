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
        self.tail_replies: list[history_pb2.TailHistoryReply] = []

    async def Status(self, request: history_pb2.StatusRequest) -> history_pb2.StatusReply:
        self.requests["status"] = request
        return history_pb2.StatusReply(healthy=True, version="18.19.0", pid=42, protocol=1)

    async def StartHistory(self, request: history_pb2.StartHistoryRequest) -> history_pb2.StartHistoryReply:
        self.requests["start"] = request
        return history_pb2.StartHistoryReply(id="started-id", version="18.19.0", protocol=1)

    async def EndHistory(self, request: history_pb2.EndHistoryRequest) -> history_pb2.EndHistoryReply:
        self.requests["end"] = request
        return history_pb2.EndHistoryReply(id=request.id, idx=99, version="18.19.0", protocol=1)

    async def CancelHistory(
        self, request: history_pb2.CancelHistoryRequest
    ) -> history_pb2.CancelHistoryReply:
        self.requests["cancel"] = request
        return history_pb2.CancelHistoryReply(version="18.19.0", protocol=1)

    async def Shutdown(self, request: history_pb2.ShutdownRequest) -> history_pb2.ShutdownReply:
        self.requests["shutdown"] = request
        return history_pb2.ShutdownReply(accepted=True)

    def TailHistory(
        self, request: history_pb2.TailHistoryRequest
    ) -> AsyncIterator[history_pb2.TailHistoryReply]:
        self.requests["tail"] = request

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

    async def test_status(self) -> None:
        status = await self.client.status()
        assert status.healthy
        assert status.version == "18.19.0"
        assert status.pid == 42
        assert status.protocol == 1
        assert isinstance(self.stub.requests["status"], history_pb2.StatusRequest)

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
        assert result.id == "started-id"
        assert result.version == "18.19.0"
        assert result.protocol == 1

        request = self.stub.requests["start"]
        assert isinstance(request, history_pb2.StartHistoryRequest)
        assert request.timestamp == 123456789
        assert request.command == "git status"
        assert request.cwd == "/tmp/repo"
        assert request.session == "session-1"
        assert request.hostname == "host:user"
        assert request.author == "agent"
        assert request.intent == "inspect"
        assert request.shell == "zsh"

    async def test_start_converts_optional_strings_to_proto_defaults(self) -> None:
        await self.client.start(
            "pwd",
            cwd="/tmp",
            session="s",
            hostname="h",
            timestamp_ns=1,
        )
        request = self.stub.requests["start"]
        assert isinstance(request, history_pb2.StartHistoryRequest)
        assert request.author == ""
        assert request.intent == ""
        assert request.shell == ""

    async def test_end(self) -> None:
        result = await self.client.end("history-id", exit_code=7, duration_ns=123)
        assert result.id == "history-id"
        assert result.idx == 99
        request = self.stub.requests["end"]
        assert isinstance(request, history_pb2.EndHistoryRequest)
        assert request.id == "history-id"
        assert request.exit == 7
        assert request.duration == 123

    async def test_cancel(self) -> None:
        assert await self.client.cancel("history-id") is None
        request = self.stub.requests["cancel"]
        assert isinstance(request, history_pb2.CancelHistoryRequest)
        assert request.id == "history-id"

    async def test_shutdown(self) -> None:
        assert await self.client.shutdown()
        assert isinstance(self.stub.requests["shutdown"], history_pb2.ShutdownRequest)

    async def test_tail_converts_started_and_ended_events(self) -> None:
        self.stub.tail_replies = [
            history_pb2.TailHistoryReply(
                kind=history_pb2.HISTORY_EVENT_KIND_STARTED,
                history=history_entry(),
            ),
            history_pb2.TailHistoryReply(
                kind=history_pb2.HISTORY_EVENT_KIND_ENDED,
                history=history_entry(),
            ),
        ]
        events = [event async for event in self.client.tail()]
        assert len(events) == 2

        started = events[0]
        assert isinstance(started, HistoryStarted)
        assert isinstance(started, HistoryStarted)
        assert started.id == "history-id"
        assert started.timestamp_ns == 1500000000
        assert started.timestamp.timestamp() == pytest.approx(1.5)
        assert started.author == "joseph"
        assert started.intent == "inspect cwd"
        assert started.shell == "zsh"

        ended = events[1]
        assert isinstance(ended, HistoryEnded)
        assert isinstance(ended, HistoryEnded)
        assert ended.exit_code == 0
        assert ended.duration_ns == 66000000
        assert isinstance(self.stub.requests["tail"], history_pb2.TailHistoryRequest)

    async def test_tail_skips_reply_without_history(self) -> None:
        self.stub.tail_replies = [
            history_pb2.TailHistoryReply(kind=history_pb2.HISTORY_EVENT_KIND_STARTED),
            history_pb2.TailHistoryReply(
                kind=history_pb2.HISTORY_EVENT_KIND_STARTED,
                history=history_entry(),
            ),
        ]
        events = [event async for event in self.client.tail()]
        assert len(events) == 1

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
            def TailHistory(
                self, request: history_pb2.TailHistoryRequest
            ) -> AsyncIterator[history_pb2.TailHistoryReply]:
                async def replies():
                    if False:
                        yield history_pb2.TailHistoryReply()
                    raise error

                return replies()

        client = HistoryClient(ErrorStub())
        with pytest.raises(AtuinConnectionError, match="tail unavailable"):
            _ = [event async for event in client.tail()]

    def test_event_conversion_rejects_missing_history(self) -> None:
        with pytest.raises(AtuinProtocolError, match="did not contain a history entry"):
            _event_from_proto(history_pb2.TailHistoryReply())

    async def test_command_context_manager_ends_on_success(self) -> None:
        async with self.client.command("pwd", cwd="/tmp", session="s", hostname="h", exit_code=3) as started:
            assert started.id == "started-id"

        assert "cancel" not in self.stub.requests
        request = self.stub.requests["end"]
        assert isinstance(request, history_pb2.EndHistoryRequest)
        assert request.id == "started-id"
        assert request.exit == 3
        assert request.duration > 0

    async def test_command_context_manager_cancels_on_exception(self) -> None:
        with pytest.raises(RuntimeError, match="boom"):  # ruff: ignore[pytest-raises-with-multiple-statements]
            async with self.client.command("pwd", cwd="/tmp", session="s", hostname="h"):
                msg = "boom"
                raise RuntimeError(msg)

        assert "end" not in self.stub.requests
        request = self.stub.requests["cancel"]
        assert isinstance(request, history_pb2.CancelHistoryRequest)
        assert request.id == "started-id"
