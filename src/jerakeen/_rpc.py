from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

import grpc

from jerakeen.exceptions import from_grpc_error

if TYPE_CHECKING:
    from collections.abc import Awaitable

T = TypeVar("T")


async def call[T](awaitable: Awaitable[T]) -> T:
    try:
        return await awaitable
    except grpc.aio.AioRpcError as exc:
        raise from_grpc_error(exc) from exc
