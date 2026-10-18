from __future__ import annotations

import grpc


class AtuinError(Exception):
    """Base exception raised by the jerakeen client API."""


class AtuinConnectionError(AtuinError):
    """The daemon could not be reached or became unavailable."""


class AtuinTimeoutError(AtuinError):
    """An Atuin operation exceeded its configured deadline."""


class AtuinNotFoundError(AtuinError):
    """The requested Atuin resource does not exist."""


class AtuinUnsupportedError(AtuinError):
    """The connected daemon does not implement the requested RPC."""


class AtuinProtocolError(AtuinError):
    """The daemon returned data that does not match the expected protocol."""


class AtuinCompatibilityError(AtuinProtocolError):
    """The daemon build or wire contract differs from the supported snapshot."""



class AtuinRpcError(AtuinError):
    """An RPC failed with a gRPC status that has no more specific mapping."""

    def __init__(self, code: grpc.StatusCode, details: str) -> None:
        self.code = code
        self.details = details
        super().__init__(f"{code.name}: {details}")


def from_grpc_error(exc: grpc.aio.AioRpcError) -> AtuinError:
    """Translate a raw grpc.aio failure into a public jerakeen exception."""

    details = exc.details() or exc.code().name
    match exc.code():
        case grpc.StatusCode.DEADLINE_EXCEEDED:
            return AtuinTimeoutError(details)
        case grpc.StatusCode.NOT_FOUND:
            return AtuinNotFoundError(details)
        case grpc.StatusCode.UNIMPLEMENTED:
            return AtuinUnsupportedError(details)
        case grpc.StatusCode.UNAVAILABLE:
            return AtuinConnectionError(details)
        case grpc.StatusCode.FAILED_PRECONDITION if details.startswith("daemon is build "):
            return AtuinCompatibilityError(
                f"{details}; Jerakeen targets Atuin 18.24.1's exact build contract"
            )
        case grpc.StatusCode.INTERNAL:
            return AtuinProtocolError(details)
        case _:
            return AtuinRpcError(exc.code(), details)
