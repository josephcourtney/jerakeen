from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from uuid import UUID

import grpc
import pytest

from jerakeen import Atuin, AtuinCompatibilityError, HistoryEnded, HistoryLagged, HistoryStarted, connect
from jerakeen._ids import history_id_to_proto
from jerakeen._proto import common_pb2, history_pb2, search_pb2

HISTORY_ID = UUID("00112233-4455-6677-8899-aabbccddeeff")
RECORD_ID = UUID("ffeeddcc-bbaa-9988-7766-554433221100")


class FakeDaemon:
    def __init__(self) -> None:
        self.version = "18.24.1"
        self.build = "18.24.1"
        self.seen_builds: list[str | None] = []
        self.output_missing = False
        self.output_requests: list[history_pb2.GetCommandOutputRequest] = []

    async def require_build(self, context) -> None:
        supplied = dict(context.invocation_metadata()).get("x-atuin-build")
        self.seen_builds.append(supplied)
        if supplied != self.build:
            await context.abort(
                grpc.StatusCode.FAILED_PRECONDITION,
                f"daemon is build {self.build}, client is build {supplied}",
            )

    async def status(self, request, context):
        await self.require_build(context)
        return history_pb2.StatusReply(healthy=True, version=self.version, pid=123)

    async def start_history(self, request, context):
        await self.require_build(context)
        await self.require_build(context)
        return history_pb2.StartHistoryReply(id=history_id_to_proto(HISTORY_ID))

    async def end_history(self, request, context):
        await self.require_build(context)
        return history_pb2.EndHistoryReply(
            record_id=common_pb2.RecordId(uuid=common_pb2.Uuid(value=RECORD_ID.bytes)),
            record_idx=77,
        )

    async def tail_history(self, request, context):
        await self.require_build(context)
        entry = history_pb2.HistoryEntry(
            timestamp=1_500_000_000,
            id=history_id_to_proto(HISTORY_ID),
            command="pwd",
            cwd="/tmp",
            session="session",
            hostname="host:user",
            shell="zsh",
        )
        yield history_pb2.TailHistoryReply(started=entry)
        entry.exit = 0
        entry.duration = 12_000_000
        yield history_pb2.TailHistoryReply(ended=entry)
        yield history_pb2.TailHistoryReply(lagged=common_pb2.Lagged(dropped=4))

    async def compact_store(self, request, context):
        await self.require_build(context)
        return history_pb2.CompactStoreReply(rewritten=12)

    async def get_command_output(self, request, context):
        await self.require_build(context)
        self.output_requests.append(request)
        if self.output_missing:
            await context.abort(grpc.StatusCode.NOT_FOUND, "output not found")
        return history_pb2.GetCommandOutputResponse(
            chunks=[
                history_pb2.OutputChunk(
                    line_range=common_pb2.PyStyleIdxRange(start=0, end=0),
                    content="captured",
                )
            ],
            total_bytes=8,
            total_lines=1,
            meta=history_pb2.CommandCaptureMeta(
                output_observed_bytes=8, terminal_width=80, terminal_height=24
            ),
        )

    async def search(self, requests, context):
        await self.require_build(context)
        async for request in requests:
            yield search_pb2.SearchResponse(
                query_id=request.query_id,
                ids=[HISTORY_ID.bytes],
            )

    async def search_command_output(self, request, context):
        await self.require_build(context)
        yield search_pb2.OutputSearchMatch(
            history_id=history_id_to_proto(HISTORY_ID),
            lines=[
                search_pb2.OutputSearchLine(
                    line=0,
                    content=common_pb2.HighlightedText(open=0, close=8, raw="captured"),
                )
            ],
            score=1.0,
        )


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


def _stream_stream(handler, request_type, response_type):
    return grpc.stream_stream_rpc_method_handler(
        handler,
        request_deserializer=request_type.FromString,
        response_serializer=response_type.SerializeToString,
    )


def add_services(server: grpc.aio.Server, daemon: FakeDaemon) -> None:
    server.add_generic_rpc_handlers((
        grpc.method_handlers_generic_handler(
            "history.History",
            {
                "Status": _unary_unary(daemon.status, history_pb2.StatusRequest, history_pb2.StatusReply),
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
                "CompactStore": _unary_unary(
                    daemon.compact_store,
                    history_pb2.CompactStoreRequest,
                    history_pb2.CompactStoreReply,
                ),
                "TailHistory": _unary_stream(
                    daemon.tail_history,
                    history_pb2.TailHistoryRequest,
                    history_pb2.TailHistoryReply,
                ),
                "GetCommandOutput": _unary_unary(
                    daemon.get_command_output,
                    history_pb2.GetCommandOutputRequest,
                    history_pb2.GetCommandOutputResponse,
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
                "SearchCommandOutput": _unary_stream(
                    daemon.search_command_output,
                    search_pb2.SearchCommandOutputRequest,
                    search_pb2.OutputSearchMatch,
                ),
            },
        ),
    ))


class GrpcIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.daemon = FakeDaemon()
        self.server = grpc.aio.server()
        add_services(self.server, self.daemon)
        self.port = self.server.add_insecure_port("127.0.0.1:0")
        self.tempdir = tempfile.TemporaryDirectory()
        self.socket = Path(self.tempdir.name) / "atuin.sock"
        if os.name != "nt":
            self.server.add_insecure_port(f"unix:{self.socket}")
        await self.server.start()

    async def asyncTearDown(self) -> None:
        await self.server.stop(None)
        self.tempdir.cleanup()

    async def _exercise(self, atuin: Atuin) -> None:
        assert atuin.version == "18.24.1"
        assert atuin.protocol is None
        assert atuin.compatibility.compatible

        started = await atuin.history.start(
            "pwd", cwd="/tmp", session="s", hostname="host:user", timestamp_ns=1
        )
        assert started.id == HISTORY_ID
        ended = await atuin.history.end(started.id, exit_code=0, duration_ns=123)
        assert ended.record_id == RECORD_ID
        assert ended.record_idx == 77

        events = [event async for event in atuin.history.tail()]
        assert isinstance(events[0], HistoryStarted)
        assert isinstance(events[1], HistoryEnded)
        assert isinstance(events[2], HistoryLagged)
        assert events[2].dropped == 4

        output = await atuin.history.output(HISTORY_ID)
        assert output is not None
        assert output.text == "captured"
        assert output.meta.terminal_width == 80
        assert [(r.start, r.end) for r in self.daemon.output_requests[-1].line_ranges] == [(0, -1)]

        result = await atuin.search.query("pwd", query_id=9)
        assert result.ids == (HISTORY_ID,)
        matches = [match async for match in atuin.search.output("captured")]
        assert matches[0].history_id == HISTORY_ID
        assert matches[0].lines[0].content.raw == "captured"
        assert len(self.daemon.seen_builds) >= 6
        assert set(self.daemon.seen_builds) == {"18.24.1"}

    async def test_18_24_1_over_tcp(self) -> None:
        async with await Atuin.connect(tcp=f"127.0.0.1:{self.port}") as atuin:
            await self._exercise(atuin)

    @unittest.skipIf(os.name == "nt", "Unix-domain sockets are not available on Windows")
    async def test_18_24_1_over_unix_socket(self) -> None:
        async with await Atuin.connect(socket=self.socket) as atuin:
            await self._exercise(atuin)

    async def test_compact_store_on_fake_build_gated_daemon(self) -> None:
        async with await Atuin.connect(tcp=f"127.0.0.1:{self.port}") as atuin:
            result = await atuin.history.compact_store()
            assert (result.rewritten, result.version, result.protocol) == (12, None, None)

    async def test_output_not_found_maps_to_none_over_real_grpc(self) -> None:
        self.daemon.output_missing = True
        async with await Atuin.connect(tcp=f"127.0.0.1:{self.port}") as atuin:
            assert await atuin.history.output(HISTORY_ID) is None

    async def test_incompatible_daemon_build_is_rejected_by_server(self) -> None:
        self.daemon.build = "18.24.1+different"
        with pytest.raises(AtuinCompatibilityError, match="daemon is build"):
            await Atuin.connect(tcp=f"127.0.0.1:{self.port}")

    async def test_incompatible_status_version_is_rejected_by_client(self) -> None:
        self.daemon.version = "18.24.2"
        with pytest.raises(AtuinCompatibilityError, match="incompatible"):
            await Atuin.connect(tcp=f"127.0.0.1:{self.port}")

    async def test_compatibility_can_be_inspected_without_feature_guarantee(self) -> None:
        self.daemon.version = "18.24.2"
        async with await Atuin.connect(
            tcp=f"127.0.0.1:{self.port}", check_compatibility=False
        ) as atuin:
            assert atuin.protocol is None
            assert not atuin.compatibility.compatible

    async def test_connect_context_manager_helper(self) -> None:
        async with connect(tcp=f"127.0.0.1:{self.port}") as atuin:
            assert (await atuin.status()).protocol is None


if __name__ == "__main__":
    unittest.main()
