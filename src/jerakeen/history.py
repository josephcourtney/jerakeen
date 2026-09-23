from __future__ import annotations

import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import TYPE_CHECKING, TypedDict

import grpc
from google.protobuf import duration_pb2

from jerakeen._ids import history_id_from_proto, history_id_to_proto, record_id_from_proto
from jerakeen._proto import common_pb2, history_pb2
from jerakeen._rpc import call
from jerakeen.exceptions import AtuinNotFoundError, AtuinProtocolError, from_grpc_error
from jerakeen.models import (
    AuthorKind,
    CommandCapture,
    CommandCaptureMeta,
    CommandOutput,
    DaemonStatus,
    HistoryCancel,
    HistoryCancelled,
    HistoryCommand,
    HistoryDelete,
    HistoryEnd,
    HistoryEnded,
    HistoryEventRecord,
    HistoryLagged,
    HistoryRebuild,
    HistoryStart,
    HistoryStarted,
    OutputChunk,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterable
    from pathlib import Path
    from uuid import UUID

    from jerakeen._interfaces import HistoryStub

NANOSECONDS_PER_SECOND = 1_000_000_000
_DELETE_CHUNK_SIZE = 50_000

_AUTHOR_TO_PROTO = {
    AuthorKind.UNSPECIFIED: history_pb2.AUTHOR_KIND_UNSPECIFIED,
    AuthorKind.USER: history_pb2.AUTHOR_KIND_USER,
    AuthorKind.AGENT: history_pb2.AUTHOR_KIND_AGENT,
}
_PROTO_TO_AUTHOR = {value: key for key, value in _AUTHOR_TO_PROTO.items()}


class _EventCommon(TypedDict):
    id: UUID
    timestamp: datetime
    timestamp_ns: int
    command: str
    cwd: str
    session: str
    hostname: str
    author: str | None
    intent: str | None
    shell: str | None
    author_kind: AuthorKind


def _duration_from_ns(value: int | None) -> duration_pb2.Duration | None:
    if value is None:
        return None
    if value < 0:
        msg = "duration_ns must be non-negative"
        raise ValueError(msg)
    seconds, nanos = divmod(value, NANOSECONDS_PER_SECOND)
    return duration_pb2.Duration(seconds=seconds, nanos=nanos)


def _range_to_proto(value: slice | tuple[int, int]) -> common_pb2.PyStyleIdxRange:
    if isinstance(value, tuple):
        start, end = value
    else:
        if value.step not in {None, 1}:
            msg = "output range slices do not support a step"
            raise ValueError(msg)
        if value.start is None or value.stop is None:
            msg = "output range slices require both start and stop"
            raise ValueError(msg)
        start, end = value.start, value.stop
    return common_pb2.PyStyleIdxRange(start=start, end=end)


def _meta_from_proto(value: history_pb2.CommandCaptureMeta) -> CommandCaptureMeta:
    return CommandCaptureMeta(
        observed_bytes=value.output_observed_bytes,
        terminal_width=value.terminal_width,
        terminal_height=value.terminal_height,
    )


def _capture_to_proto(value: CommandCapture) -> history_pb2.CommandCapture:
    capture = history_pb2.CommandCapture(
        output_start=value.output_start,
        meta=history_pb2.CommandCaptureMeta(
            output_observed_bytes=value.meta.observed_bytes,
            terminal_width=value.meta.terminal_width,
            terminal_height=value.meta.terminal_height,
        ),
    )
    if value.output_end is not None:
        capture.output_end = value.output_end
    return capture


def _event_common(entry: history_pb2.HistoryEntry, *, source: str) -> _EventCommon:
    try:
        author_kind = _PROTO_TO_AUTHOR[entry.author_kind]
    except KeyError as exc:
        msg = f"{source} contained unknown author_kind {entry.author_kind}"
        raise AtuinProtocolError(msg) from exc
    return {
        "id": history_id_from_proto(entry.id, source=f"{source}.id"),
        "timestamp": datetime.fromtimestamp(entry.timestamp / NANOSECONDS_PER_SECOND, tz=UTC),
        "timestamp_ns": entry.timestamp,
        "command": entry.command,
        "cwd": entry.cwd,
        "session": entry.session,
        "hostname": entry.hostname,
        "author": entry.author or None,
        "intent": entry.intent or None,
        "shell": entry.shell or None,
        "author_kind": author_kind,
    }


def _event_from_proto(reply: history_pb2.TailHistoryReply) -> HistoryEventRecord:
    kind = reply.WhichOneof("event")
    if kind == "started":
        return HistoryStarted(**_event_common(reply.started, source="TailHistoryReply.started"))
    if kind == "ended":
        return HistoryEnded(
            **_event_common(reply.ended, source="TailHistoryReply.ended"),
            exit_code=reply.ended.exit,
            duration_ns=reply.ended.duration,
        )
    if kind == "cancelled":
        return HistoryCancelled(**_event_common(reply.cancelled, source="TailHistoryReply.cancelled"))
    if kind == "lagged":
        return HistoryLagged(dropped=reply.lagged.dropped)
    msg = "TailHistoryReply did not contain a recognized event"
    raise AtuinProtocolError(msg)


class HistoryClient:
    """Pythonic wrapper around Atuin's protocol-3 History gRPC service."""

    def __init__(self, stub: HistoryStub, *, timeout: float | None = 5.0) -> None:
        self._stub = stub
        self._timeout = timeout

    async def status(self) -> DaemonStatus:
        reply = await call(self._stub.Status(history_pb2.StatusRequest(), timeout=self._timeout))
        return DaemonStatus(
            healthy=reply.healthy,
            version=reply.version,
            pid=reply.pid,
            protocol=reply.protocol,
        )

    async def start(
        self,
        command: str,
        *,
        cwd: str | Path,
        session: str,
        hostname: str,
        author: str | None = None,
        intent: str | None = None,
        shell: str | None = None,
        author_kind: AuthorKind = AuthorKind.UNSPECIFIED,
        timestamp_ns: int | None = None,
    ) -> HistoryStart:
        reply = await call(
            self._stub.StartHistory(
                history_pb2.StartHistoryRequest(
                    timestamp=time.time_ns() if timestamp_ns is None else timestamp_ns,
                    command=command,
                    cwd=str(cwd),
                    session=session,
                    hostname=hostname,
                    author=author or "",
                    intent=intent or "",
                    shell=shell or "",
                    author_kind=_AUTHOR_TO_PROTO[author_kind],
                ),
                timeout=self._timeout,
            )
        )
        return HistoryStart(
            id=history_id_from_proto(reply.id, source="StartHistoryReply.id"),
            version=reply.version,
            protocol=reply.protocol,
        )

    async def end(
        self,
        history_id: UUID | str,
        *,
        exit_code: int,
        duration_ns: int | None = None,
    ) -> HistoryEnd:
        request = history_pb2.EndHistoryRequest(id=history_id_to_proto(history_id), exit=exit_code)
        duration = _duration_from_ns(duration_ns)
        if duration is not None:
            request.duration.CopyFrom(duration)
        reply = await call(self._stub.EndHistory(request, timeout=self._timeout))
        return HistoryEnd(
            record_id=record_id_from_proto(reply.record_id, source="EndHistoryReply.record_id"),
            record_idx=reply.record_idx,
            version=reply.version,
            protocol=reply.protocol,
        )

    async def cancel(self, history_id: UUID | str) -> HistoryCancel:
        reply = await call(
            self._stub.CancelHistory(
                history_pb2.CancelHistoryRequest(id=history_id_to_proto(history_id)),
                timeout=self._timeout,
            )
        )
        return HistoryCancel(version=reply.version, protocol=reply.protocol)

    async def delete(self, history_ids: Iterable[UUID | str]) -> HistoryDelete:
        async def requests() -> AsyncIterator[history_pb2.DeleteHistoryRequest]:
            chunk: list[common_pb2.HistoryId] = []
            for history_id in history_ids:
                chunk.append(history_id_to_proto(history_id))
                if len(chunk) == _DELETE_CHUNK_SIZE:
                    yield history_pb2.DeleteHistoryRequest(ids=chunk)
                    chunk = []
            if chunk:
                yield history_pb2.DeleteHistoryRequest(ids=chunk)

        reply = await call(self._stub.DeleteHistory(requests(), timeout=self._timeout))
        return HistoryDelete(deleted=reply.deleted, version=reply.version, protocol=reply.protocol)

    async def rebuild(self) -> HistoryRebuild:
        reply = await call(
            self._stub.RebuildHistory(history_pb2.RebuildHistoryRequest(), timeout=self._timeout)
        )
        return HistoryRebuild(version=reply.version, protocol=reply.protocol)

    async def shutdown(self) -> bool:
        reply = await call(self._stub.Shutdown(history_pb2.ShutdownRequest(), timeout=self._timeout))
        return reply.accepted

    async def tail(self, *, timeout: float | None = None) -> AsyncIterator[HistoryEventRecord]:
        try:
            async for reply in self._stub.TailHistory(history_pb2.TailHistoryRequest(), timeout=timeout):
                yield _event_from_proto(reply)
        except grpc.aio.AioRpcError as exc:
            raise from_grpc_error(exc) from exc

    async def register_output(self, history_id: UUID | str, capture: CommandCapture) -> None:
        await call(
            self._stub.RegisterCommandOutput(
                history_pb2.RegisterCommandOutputRequest(
                    history_id=history_id_to_proto(history_id),
                    capture=_capture_to_proto(capture),
                ),
                timeout=self._timeout,
            )
        )

    async def output(
        self,
        history_id: UUID | str,
        *,
        ranges: Iterable[slice | tuple[int, int]] | None = None,
    ) -> CommandOutput | None:
        selected = (
            [common_pb2.PyStyleIdxRange(start=0, end=-1)]
            if ranges is None
            else [_range_to_proto(value) for value in ranges]
        )
        try:
            reply = await call(
                self._stub.GetCommandOutput(
                    history_pb2.GetCommandOutputRequest(
                        id=history_id_to_proto(history_id),
                        line_ranges=selected,
                    ),
                    timeout=self._timeout,
                )
            )
        except AtuinNotFoundError:
            return None

        chunks: list[OutputChunk] = []
        for index, chunk in enumerate(reply.chunks):
            if not chunk.HasField("line_range"):
                msg = f"GetCommandOutputResponse.chunks[{index}] has no line range"
                raise AtuinProtocolError(msg)
            chunks.append(
                OutputChunk(
                    start_line=chunk.line_range.start,
                    end_line=chunk.line_range.end,
                    content=chunk.content,
                )
            )
        if not reply.HasField("meta"):
            msg = "GetCommandOutputResponse did not contain capture metadata"
            raise AtuinProtocolError(msg)
        return CommandOutput(
            text="\n".join(chunk.content for chunk in chunks),
            total_bytes=reply.total_bytes,
            total_lines=reply.total_lines,
            chunks=tuple(chunks),
            truncated=reply.truncated,
            meta=_meta_from_proto(reply.meta),
        )

    @asynccontextmanager
    async def command(
        self,
        command: str,
        *,
        cwd: str | Path,
        session: str,
        hostname: str,
        author: str | None = None,
        intent: str | None = None,
        shell: str | None = None,
        author_kind: AuthorKind = AuthorKind.UNSPECIFIED,
        exit_code: int = 0,
    ) -> AsyncIterator[HistoryCommand]:
        started_at = time.monotonic_ns()
        started = await self.start(
            command,
            cwd=cwd,
            session=session,
            hostname=hostname,
            author=author,
            intent=intent,
            shell=shell,
            author_kind=author_kind,
        )
        handle = HistoryCommand(start=started, exit_code=exit_code)
        try:
            yield handle
        except BaseException:
            await self.cancel(started.id)
            raise
        else:
            await self.end(
                started.id,
                exit_code=handle.exit_code,
                duration_ns=(
                    time.monotonic_ns() - started_at if handle.duration_ns is None else handle.duration_ns
                ),
            )
