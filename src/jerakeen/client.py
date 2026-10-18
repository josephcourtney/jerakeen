from __future__ import annotations

import asyncio

import grpc
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Self

from jerakeen._proto import history_pb2, history_pb2_grpc, search_pb2_grpc
from jerakeen._transport import BUILD_HEADER, VALIDATED_BUILD, BuildMetadata, create_channel, discover_target, local_atuin_build
from jerakeen.compatibility import Compatibility, assess_compatibility
from jerakeen.exceptions import AtuinConnectionError, AtuinProtocolError, from_grpc_error
from jerakeen.history import HistoryClient
from jerakeen.models import DaemonStatus
from jerakeen.search import SearchClient

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

    import grpc

    from jerakeen.models import DaemonStatus


class Atuin:
    """High-level async client for a local Atuin daemon."""

    def __init__(
        self,
        channel: grpc.aio.Channel,
        *,
        description: str,
        rpc_timeout: float | None = 5.0,
    ) -> None:
        self._channel = channel
        self._status: DaemonStatus | None = None
        self._compatibility: Compatibility | None = None
        self.description = description
        self.rpc_timeout = rpc_timeout
        self.history = HistoryClient(history_pb2_grpc.HistoryStub(channel), timeout=rpc_timeout)
        self.search = SearchClient(search_pb2_grpc.SearchStub(channel), timeout=rpc_timeout)

    @property
    def version(self) -> str:
        if self._status is None:
            msg = "Atuin client has not completed its compatibility handshake"
            raise RuntimeError(msg)
        return self._status.version

    @property
    def protocol(self) -> int:
        if self._status is None:
            msg = "Atuin client has not completed its compatibility handshake"
            raise RuntimeError(msg)
        return self._status.protocol

    @property
    def compatibility(self) -> Compatibility:
        if self._compatibility is None:
            msg = "Atuin client has not completed its compatibility handshake"
            raise RuntimeError(msg)
        return self._compatibility

    @classmethod
    async def connect(
        cls,
        *,
        socket: str | Path | None = None,
        tcp: str | None = None,
        timeout: float = 5.0,
        rpc_timeout: float | None = 5.0,
        check_compatibility: bool = True,
    ) -> Atuin:
        target, description = discover_target(socket, tcp)
        local_build = local_atuin_build()
        if local_build != VALIDATED_BUILD:
            raise AtuinProtocolError(
                f'Local Atuin build {local_build!r} is not validated; expected {VALIDATED_BUILD}'
            )
        build = BuildMetadata(local_build)
        channel = create_channel(target, build=build)
        try:
            await asyncio.wait_for(channel.channel_ready(), timeout=timeout)
        except TimeoutError as exc:
            await channel.close()
            msg = f"timed out connecting to Atuin daemon at {description}"
            raise AtuinConnectionError(msg) from exc

        client = cls(channel, description=description, rpc_timeout=rpc_timeout)
        try:
            # Status is ungated; inspect the daemon build before ordinary RPCs.
            request = history_pb2.StatusRequest()
            status_call = history_pb2_grpc.HistoryStub(channel).Status(
                request, timeout=rpc_timeout
            )
            try:
                reply = await status_call
            except grpc.aio.AioRpcError as exc:
                raise from_grpc_error(exc) from exc
            metadata = await status_call.initial_metadata()
            advertised = next((v for k, v in metadata if k == BUILD_HEADER), None)
            status = DaemonStatus(
                healthy=reply.healthy, version=reply.version,
                pid=reply.pid, protocol=reply.protocol,
            )
            # Atuin 18.24.1 removed StatusReply.protocol; build validation
            # supersedes its previous integer protocol negotiation.
            status = DaemonStatus(status.healthy, status.version, status.pid, 5)
            compatibility = assess_compatibility(status)
            if check_compatibility:
                compatibility.require()
            if advertised != local_build:
                raise AtuinProtocolError(
                    f'Atuin daemon build {advertised!r} differs from client build {local_build!r}'
                )
        except BaseException:
            await client.close()
            raise

        client._status = status
        client._compatibility = compatibility
        return client

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.close()

    async def close(self) -> None:
        await self._channel.close()

    async def status(self) -> DaemonStatus:
        return await self.history.status()


@asynccontextmanager
async def connect(
    *,
    socket: str | Path | None = None,
    tcp: str | None = None,
    timeout: float = 5.0,
    rpc_timeout: float | None = 5.0,
    check_compatibility: bool = True,
) -> AsyncIterator[Atuin]:
    """Open an Atuin client and close its channel on context exit."""

    client = await Atuin.connect(
        socket=socket,
        tcp=tcp,
        timeout=timeout,
        rpc_timeout=rpc_timeout,
        check_compatibility=check_compatibility,
    )
    async with client:
        yield client
