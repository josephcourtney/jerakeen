from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import grpc
import pytest

from jerakeen import (
    Atuin,
    AtuinNotFoundError,
    CommandCapture,
    FilterMode,
    HistoryEnded,
    HistoryStarted,
    SearchContext,
    SearchQuery,
    connect,
)
from jerakeen._proto import control_pb2, history_pb2, search_pb2, semantic_pb2


class FakeDaemonService:
    def __init__(self) -> None:
        self.start_requests: list[history_pb2.StartHistoryRequest] = []
        self.end_requests: list[history_pb2.EndHistoryRequest] = []
        self.cancel_requests: list[history_pb2.CancelHistoryRequest] = []
        self.shutdown_requests = 0
        self.semantic_output_requests: list[semantic_pb2.CommandOutputRequest] = []
        self.captures: list[semantic_pb2.CommandCapture] = []
        self.prepare_requests: list[search_pb2.PrepareIndexRequest] = []
        self.search_requests: list[search_pb2.SearchRequest] = []
        self.control_requests: list[control_pb2.SendEventRequest] = []
        self.status_error: grpc.StatusCode | None = None

    async def status(self, request: history_pb2.StatusRequest, context) -> history_pb2.StatusReply:
        if self.status_error is not None:
            await context.abort(self.status_error, "status failed")
        return history_pb2.StatusReply(healthy=True, version="18.19.0", pid=123, protocol=1)

    async def start_history(
        self, request: history_pb2.StartHistoryRequest, context
    ) -> history_pb2.StartHistoryReply:
        self.start_requests.append(request)
        return history_pb2.StartHistoryReply(id="server-history-id", version="18.19.0", protocol=1)

    async def end_history(
        self, request: history_pb2.EndHistoryRequest, context
    ) -> history_pb2.EndHistoryReply:
        self.end_requests.append(request)
        return history_pb2.EndHistoryReply(id=request.id, idx=77, version="18.19.0", protocol=1)

    async def cancel_history(
        self, request: history_pb2.CancelHistoryRequest, context
    ) -> history_pb2.CancelHistoryReply:
        self.cancel_requests.append(request)
        return history_pb2.CancelHistoryReply(version="18.19.0", protocol=1)

    async def tail_history(self, request: history_pb2.TailHistoryRequest, context):
        def entry(*, exit_code: int = 0, duration_ns: int = 0) -> history_pb2.HistoryEntry:
            return history_pb2.HistoryEntry(
                timestamp=1_500_000_000,
                id="tail-id",
                command="pwd",
                cwd="/tmp",
                session="session",
                hostname="host:user",
                author="agent",
                intent="inspect",
                exit=exit_code,
                duration=duration_ns,
                shell="zsh",
            )

        yield history_pb2.TailHistoryReply(
            kind=history_pb2.HISTORY_EVENT_KIND_STARTED,
            history=entry(),
        )
        yield history_pb2.TailHistoryReply(
            kind=history_pb2.HISTORY_EVENT_KIND_ENDED,
            history=entry(exit_code=0, duration_ns=12_000_000),
        )

    async def shutdown(self, request: history_pb2.ShutdownRequest, context) -> history_pb2.ShutdownReply:
        self.shutdown_requests += 1
        return history_pb2.ShutdownReply(accepted=True)

    async def command_output(
        self, request: semantic_pb2.CommandOutputRequest, context
    ) -> semantic_pb2.CommandOutputReply:
        self.semantic_output_requests.append(request)
        return semantic_pb2.CommandOutputReply(
            found=True,
            output="selected output",
            total_bytes=200,
            total_lines=20,
            lines=[
                semantic_pb2.OutputLine(line_number=2, content="two"),
                semantic_pb2.OutputLine(line_number=3, content="three"),
            ],
            output_truncated=True,
            output_observed_bytes=300,
        )

    async def record_commands(self, request_iterator, context) -> semantic_pb2.RecordCommandsReply:
        async for request in request_iterator:
            self.captures.append(request)
        return semantic_pb2.RecordCommandsReply(accepted=len(self.captures))

    async def prepare_index(
        self, request: search_pb2.PrepareIndexRequest, context
    ) -> search_pb2.PrepareIndexResponse:
        self.prepare_requests.append(request)
        return search_pb2.PrepareIndexResponse()

    async def search(self, request_iterator, context):
        async for request in request_iterator:
            self.search_requests.append(request)
            yield search_pb2.SearchResponse(
                query_id=request.query_id,
                ids=[f"result-{request.query_id}".encode()],
            )

    async def send_event(
        self, request: control_pb2.SendEventRequest, context
    ) -> control_pb2.SendEventResponse:
        self.control_requests.append(request)
        return control_pb2.SendEventResponse()


def _unary_unary(handler, request_type, response_type):
    return grpc.unary_unary_rpc_method_handler(
        handler,
        request_deserializer=request_type.FromString,
        response_serializer=response_type.SerializeToString,
    )


def _unary_stream(handler, request_type, response_type):
    return grpc.unary_stream_rpc_method_handler(
        handler,
        request_deserializer=request_type.FromString,
        response_serializer=response_type.SerializeToString,
    )


def _stream_unary(handler, request_type, response_type):
    return grpc.stream_unary_rpc_method_handler(
        handler,
        request_deserializer=request_type.FromString,
        response_serializer=response_type.SerializeToString,
    )


def _stream_stream(handler, request_type, response_type):
    return grpc.stream_stream_rpc_method_handler(
        handler,
        request_deserializer=request_type.FromString,
        response_serializer=response_type.SerializeToString,
    )


def add_test_services(server: grpc.aio.Server, daemon: FakeDaemonService) -> None:
    server.add_generic_rpc_handlers((
        grpc.method_handlers_generic_handler(
            "history.History",
            {
                "StartHistory": _unary_unary(
                    daemon.start_history,
                    history_pb2.StartHistoryRequest,
                    history_pb2.StartHistoryReply,
                ),
                "EndHistory": _unary_unary(
                    daemon.end_history,
                    history_pb2.EndHistoryRequest,
                    history_pb2.EndHistoryReply,
                ),
                "CancelHistory": _unary_unary(
                    daemon.cancel_history,
                    history_pb2.CancelHistoryRequest,
                    history_pb2.CancelHistoryReply,
                ),
                "TailHistory": _unary_stream(
                    daemon.tail_history,
                    history_pb2.TailHistoryRequest,
                    history_pb2.TailHistoryReply,
                ),
                "Status": _unary_unary(
                    daemon.status,
                    history_pb2.StatusRequest,
                    history_pb2.StatusReply,
                ),
                "Shutdown": _unary_unary(
                    daemon.shutdown,
                    history_pb2.ShutdownRequest,
                    history_pb2.ShutdownReply,
                ),
            },
        ),
        grpc.method_handlers_generic_handler(
            "semantic.Semantic",
            {
                "RecordCommands": _stream_unary(
                    daemon.record_commands,
                    semantic_pb2.CommandCapture,
                    semantic_pb2.RecordCommandsReply,
                ),
                "CommandOutput": _unary_unary(
                    daemon.command_output,
                    semantic_pb2.CommandOutputRequest,
                    semantic_pb2.CommandOutputReply,
                ),
            },
        ),
        grpc.method_handlers_generic_handler(
            "search.Search",
            {
                "Search": _stream_stream(
                    daemon.search,
                    search_pb2.SearchRequest,
                    search_pb2.SearchResponse,
                ),
                "PrepareIndex": _unary_unary(
                    daemon.prepare_index,
                    search_pb2.PrepareIndexRequest,
                    search_pb2.PrepareIndexResponse,
                ),
            },
        ),
        grpc.method_handlers_generic_handler(
            "control.Control",
            {
                "SendEvent": _unary_unary(
                    daemon.send_event,
                    control_pb2.SendEventRequest,
                    control_pb2.SendEventResponse,
                )
            },
        ),
    ))


class GrpcIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.daemon = FakeDaemonService()
        self.server = grpc.aio.server()
        add_test_services(self.server, self.daemon)
        self.port = self.server.add_insecure_port("127.0.0.1:0")
        self.tempdir = tempfile.TemporaryDirectory()
        self.socket = Path(self.tempdir.name) / "atuin.sock"
        if hasattr(grpc, "aio"):
            self.server.add_insecure_port(f"unix:{self.socket}")
        await self.server.start()

    async def asyncTearDown(self) -> None:
        await self.server.stop(None)
        self.tempdir.cleanup()

    async def _exercise_all_rpc_shapes(self, atuin: Atuin) -> None:
        status = await atuin.status()
        assert (status.version, status.protocol, status.pid) == ("18.19.0", 1, 123)

        started = await atuin.history.start(
            "git status",
            cwd="/tmp/repo",
            session="session",
            hostname="host:user",
            author="agent",
            intent="inspect",
            shell="zsh",
            timestamp_ns=123456789,
        )
        assert started.id == "server-history-id"

        ended = await atuin.history.end(started.id, exit_code=5, duration_ns=999)
        assert (ended.id, ended.idx) == ("server-history-id", 77)
        await atuin.history.cancel("cancel-id")
        assert await atuin.history.shutdown()

        tail = [event async for event in atuin.history.tail()]
        assert isinstance(tail[0], HistoryStarted)
        assert isinstance(tail[1], HistoryEnded)
        ended_event = tail[1]
        assert isinstance(ended_event, HistoryEnded)
        assert ended_event.duration_ns == 12000000

        output = await atuin.semantic.output(
            "history-id",
            ranges=[(0, 10), slice(20, 30)],
        )
        assert output is not None
        assert output is not None
        assert output.lines[0].line_number == 2
        assert output.truncated
        assert (
            await atuin.semantic.record_commands([
                CommandCapture(
                    prompt="$ ",
                    command="pwd",
                    output="/tmp",
                    exit_code=0,
                    history_id="history-id",
                    session_id="session",
                    output_truncated=True,
                    output_observed_bytes=10,
                )
            ])
            == 1
        )

        await atuin.search.prepare_index(["zsh", "bash"])
        query = await atuin.search.query(
            "git",
            query_id=10,
            filter_mode=FilterMode.WORKSPACE,
            context=SearchContext(
                session_id="session",
                cwd="/tmp/repo",
                hostname="host:user",
                host_id="host-id",
                git_root="/tmp/repo",
            ),
            shells=["zsh"],
        )
        assert query.ids == (b"result-10",)

        async def search_queries():
            yield SearchQuery(query="g", query_id=11, filter_mode=FilterMode.GLOBAL)
            yield SearchQuery(query="gi", query_id=12, filter_mode=FilterMode.HOST)

        streamed = [result async for result in atuin.search.stream(search_queries())]
        assert [result.query_id for result in streamed] == [11, 12]

        async with atuin.search.session() as session:
            result = await session.query("git", query_id=13, filter_mode=FilterMode.SESSION)
            assert result.query_id == 13

        await atuin.control.force_sync()
        await atuin.control.reload_settings()
        await atuin.control.history_pruned()
        await atuin.control.history_deleted(["a", "b"])
        await atuin.control.history_rebuilt()
        await atuin.control.shutdown()

        start_request = self.daemon.start_requests[-1]
        assert start_request.timestamp == 123456789
        assert start_request.author == "agent"
        assert self.daemon.end_requests[-1].exit == 5
        assert self.daemon.cancel_requests[-1].id == "cancel-id"
        assert self.daemon.shutdown_requests == 1

        output_request = self.daemon.semantic_output_requests[-1]
        assert output_request.history_id == "history-id"
        assert [(r.start, r.end) for r in output_request.ranges] == [(0, 10), (20, 30)]
        capture = self.daemon.captures[-1]
        assert capture.HasField("exit_code")
        assert capture.HasField("history_id")
        assert capture.HasField("session_id")
        assert capture.output_truncated

        assert list(self.daemon.prepare_requests[-1].shells) == ["zsh", "bash"]
        search_request = next(request for request in self.daemon.search_requests if request.query_id == 10)
        assert search_request.filter_mode == search_pb2.WORKSPACE
        assert search_request.context.git_root == "/tmp/repo"
        assert list(search_request.shells) == ["zsh"]

        assert [request.WhichOneof("event") for request in self.daemon.control_requests[-6:]] == [
            "force_sync",
            "settings_reloaded",
            "history_pruned",
            "history_deleted",
            "history_rebuilt",
            "shutdown",
        ]
        assert list(self.daemon.control_requests[-3].history_deleted.ids) == ["a", "b"]

    async def test_all_services_and_message_shapes_over_tcp(self) -> None:
        async with await Atuin.connect(tcp=f"127.0.0.1:{self.port}") as atuin:
            await self._exercise_all_rpc_shapes(atuin)

    @unittest.skipIf(__import__("os").name == "nt", "Unix-domain sockets are not available on Windows")
    async def test_all_services_and_message_shapes_over_unix_socket(self) -> None:
        async with await Atuin.connect(socket=self.socket) as atuin:
            await self._exercise_all_rpc_shapes(atuin)

    async def test_connect_context_manager_helper(self) -> None:
        async with connect(tcp=f"127.0.0.1:{self.port}") as atuin:
            status = await atuin.status()
            assert status.version == "18.19.0"

    async def test_real_grpc_status_is_translated(self) -> None:
        self.daemon.status_error = grpc.StatusCode.NOT_FOUND
        async with await Atuin.connect(tcp=f"127.0.0.1:{self.port}") as atuin:
            with pytest.raises(AtuinNotFoundError, match="status failed"):
                await atuin.status()


if __name__ == "__main__":
    unittest.main()
