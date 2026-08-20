from __future__ import annotations

import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import grpc

from jerakeen._proto import history_pb2
from jerakeen._rpc import call
from jerakeen.exceptions import AtuinProtocolError, from_grpc_error
from jerakeen.models import (
    DaemonStatus,
    HistoryEnd,
    HistoryEnded,
    HistoryEventRecord,
    HistoryStart,
    HistoryStarted,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

    from jerakeen._interfaces import HistoryStub

NANOSECONDS_PER_SECOND = 1_000_000_000


def _event_from_proto(reply: history_pb2.TailHistoryReply) -> HistoryEventRecord:
    if not reply.HasField("history"):
        msg = "TailHistoryReply did not contain a history entry"
        raise AtuinProtocolError(msg)

    entry = reply.history
    common = {
        "id": entry.id,
        "timestamp": datetime.fromtimestamp(entry.timestamp / NANOSECONDS_PER_SECOND, tz=UTC),
        "timestamp_ns": entry.timestamp,
        "command": entry.command,
        "cwd": entry.cwd,
        "session": entry.session,
        "hostname": entry.hostname,
        "author": entry.author or None,
        "intent": entry.intent or None,
        "shell": entry.shell or None,
    }

    if reply.kind == history_pb2.HISTORY_EVENT_KIND_STARTED:
        return HistoryStarted(**common)
    if reply.kind == history_pb2.HISTORY_EVENT_KIND_ENDED:
        return HistoryEnded(
            **common,
            exit_code=entry.exit,
            duration_ns=entry.duration,
        )

    msg = f"unknown history event kind: {reply.kind}"
    raise AtuinProtocolError(msg)


class HistoryClient:
    """Pythonic wrapper around Atuin's History gRPC service."""

    def __init__(self, stub: HistoryStub) -> None:
        self._stub = stub

    async def status(self) -> DaemonStatus:
        reply = await call(self._stub.Status(history_pb2.StatusRequest()))
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
                )
            )
        )
        return HistoryStart(id=reply.id, version=reply.version, protocol=reply.protocol)

    async def end(
        self,
        history_id: str,
        *,
        exit_code: int,
        duration_ns: int,
    ) -> HistoryEnd:
        reply = await call(
            self._stub.EndHistory(
                history_pb2.EndHistoryRequest(
                    id=history_id,
                    exit=exit_code,
                    duration=duration_ns,
                )
            )
        )
        return HistoryEnd(
            id=reply.id,
            idx=reply.idx,
            version=reply.version,
            protocol=reply.protocol,
        )

    async def cancel(self, history_id: str) -> None:
        await call(self._stub.CancelHistory(history_pb2.CancelHistoryRequest(id=history_id)))

    async def shutdown(self) -> bool:
        reply = await call(self._stub.Shutdown(history_pb2.ShutdownRequest()))
        return reply.accepted

    async def tail(self) -> AsyncIterator[HistoryEventRecord]:
        try:
            async for reply in self._stub.TailHistory(history_pb2.TailHistoryRequest()):
                if not reply.HasField("history"):
                    continue
                yield _event_from_proto(reply)
        except grpc.aio.AioRpcError as exc:
            raise from_grpc_error(exc) from exc

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
        exit_code: int = 0,
    ) -> AsyncIterator[HistoryStart]:
        started_at = time.monotonic_ns()
        started = await self.start(
            command,
            cwd=cwd,
            session=session,
            hostname=hostname,
            author=author,
            intent=intent,
            shell=shell,
        )
        try:
            yield started
        except BaseException:
            await self.cancel(started.id)
            raise
        else:
            await self.end(
                started.id,
                exit_code=exit_code,
                duration_ns=time.monotonic_ns() - started_at,
            )
