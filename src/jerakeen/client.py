from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Self, cast

import grpc

from jerakeen._proto import history_pb2, history_pb2_grpc, search_pb2_grpc
from jerakeen._transport import (
    BUILD_HEADER,
    VALIDATED_BUILD,
    BuildMetadata,
    create_channel,
    discover_target,
    local_atuin_build,
    supported_build,
)
from jerakeen.compatibility import Compatibility, assess_compatibility
from jerakeen.exceptions import AtuinConnectionError, AtuinProtocolError, from_grpc_error
from jerakeen.history import HistoryClient
from jerakeen.models import DaemonStatus
from jerakeen.search import SearchClient

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path


async def _handshake(
    channel: grpc.aio.Channel, timeout: float | None, local_build: str | None
) -> DaemonStatus:
    # The Status request is gated by Atuin 18.24.1; its first request already
    # carries the validated local executable build.
    request = history_pb2.StatusRequest()
    call = cast(
        "grpc.aio.UnaryUnaryCall",
        history_pb2_grpc.HistoryStub(channel).Status(request, timeout=timeout),
    )
    try:
        reply = await call
    except grpc.aio.AioRpcError as exc:
        raise from_grpc_error(exc) from exc
    metadata = await call.initial_metadata()
    raw_build = next((v for k, v in metadata if k == BUILD_HEADER), None)
    advertised = (
        raw_build.decode("ascii", errors="replace")
        if isinstance(raw_build, bytes)
        else raw_build
    )
    if (reply.version == VALIDATED_BUILD or supported_build(local_build)) and (
        not supported_build(advertised) or local_build != advertised
    ):
        msg = f"Unsupported or missing Atuin build: daemon={advertised!r}, local={local_build!r}"
        raise AtuinProtocolError(msg)
    if advertised is not None and not supported_build(advertised):
        msg = f"Unsupported Atuin build: daemon={advertised!r}"
        raise AtuinProtocolError(msg)
    # The legacy protobuf decoder yields zero for the removed StatusReply.protocol.
    protocol = 5 if supported_build(advertised) else reply.protocol
    return DaemonStatus(reply.healthy, reply.version, reply.pid, protocol)


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
        build = BuildMetadata(local_build if supported_build(local_build) else None)
        channel = create_channel(target, build=build)
        try:
            await asyncio.wait_for(channel.channel_ready(), timeout=timeout)
        except TimeoutError as exc:
            await channel.close()
            msg = f"timed out connecting to Atuin daemon at {description}"
            raise AtuinConnectionError(msg) from exc

        client = cls(channel, description=description, rpc_timeout=rpc_timeout)
        try:
            status = await _handshake(channel, rpc_timeout, local_build)
            compatibility = assess_compatibility(status)
            if check_compatibility:
                compatibility.require()
        except BaseException:
            await client.close()
            raise
        client.search = SearchClient(
            search_pb2_grpc.SearchStub(channel),
            timeout=rpc_timeout,
            build=local_build if local_build == VALIDATED_BUILD else None,
        )
        client.history.set_daemon_identity(status.version, status.protocol)
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
