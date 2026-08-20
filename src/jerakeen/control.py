from __future__ import annotations

from typing import TYPE_CHECKING

from jerakeen._proto import control_pb2
from jerakeen._rpc import call

if TYPE_CHECKING:
    from collections.abc import Iterable

    from jerakeen._interfaces import ControlStub


class ControlClient:
    """Semantic methods for Atuin's daemon event-bus Control service."""

    def __init__(self, stub: ControlStub, *, timeout: float | None = 5.0) -> None:
        self._stub = stub
        self._timeout = timeout

    async def _send(self, request: control_pb2.SendEventRequest) -> None:
        await call(self._stub.SendEvent(request, timeout=self._timeout))

    async def force_sync(self) -> None:
        await self._send(control_pb2.SendEventRequest(force_sync=control_pb2.ForceSyncEvent()))

    async def reload_settings(self) -> None:
        await self._send(control_pb2.SendEventRequest(settings_reloaded=control_pb2.SettingsReloadedEvent()))

    async def history_pruned(self) -> None:
        await self._send(control_pb2.SendEventRequest(history_pruned=control_pb2.HistoryPrunedEvent()))

    async def history_deleted(self, ids: Iterable[str]) -> None:
        await self._send(
            control_pb2.SendEventRequest(history_deleted=control_pb2.HistoryDeletedEvent(ids=list(ids)))
        )

    async def history_rebuilt(self) -> None:
        await self._send(control_pb2.SendEventRequest(history_rebuilt=control_pb2.HistoryRebuiltEvent()))

    async def shutdown(self) -> None:
        await self._send(control_pb2.SendEventRequest(shutdown=control_pb2.ShutdownEvent()))
