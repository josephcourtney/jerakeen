from __future__ import annotations

import os
from pathlib import Path

import grpc

from jerakeen.compatibility import VENDORED_ATUIN_VERSION

ATUIN_AUTHORITY = "atuin_local_daemon:0"
BUILD_HEADER = "x-atuin-build"


def _versioned_details(details: grpc.aio.ClientCallDetails) -> grpc.aio.ClientCallDetails:
    """Announce the vendored client build, never echo a daemon-supplied build."""
    existing = tuple(
        (key, value) for key, value in (details.metadata or ()) if key.lower() != BUILD_HEADER
    )
    return grpc.aio.ClientCallDetails(
        details.method,
        details.timeout,
        (*existing, (BUILD_HEADER, VENDORED_ATUIN_VERSION)),
        details.credentials,
        details.wait_for_ready,
    )


class _BuildInterceptor(
    grpc.aio.UnaryUnaryClientInterceptor,
    grpc.aio.UnaryStreamClientInterceptor,
    grpc.aio.StreamUnaryClientInterceptor,
    grpc.aio.StreamStreamClientInterceptor,
):
    """Stamp all gRPC call shapes with the exact build identity."""

    async def intercept_unary_unary(self, continuation, details, request):  # noqa: ANN001, ANN201
        return await continuation(_versioned_details(details), request)

    async def intercept_unary_stream(self, continuation, details, request):  # noqa: ANN001, ANN201
        return await continuation(_versioned_details(details), request)

    async def intercept_stream_unary(self, continuation, details, request_iterator):  # noqa: ANN001, ANN201
        return await continuation(_versioned_details(details), request_iterator)

    async def intercept_stream_stream(self, continuation, details, request_iterator):  # noqa: ANN001, ANN201
        return await continuation(_versioned_details(details), request_iterator)


def unix_socket_candidates() -> list[Path]:
    candidates: list[Path] = []
    tmpdir = Path(os.environ.get("TMPDIR") or "/tmp")
    if hasattr(os, "getuid"):
        candidates.append(tmpdir / f"atuin-{os.getuid()}" / "atuin.sock")

    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if runtime:
        candidates.append(Path(runtime) / "atuin.sock")

    data_home = os.environ.get("XDG_DATA_HOME")
    if data_home:
        candidates.append(Path(data_home) / "atuin" / "atuin.sock")
    else:
        candidates.append(Path.home() / ".local" / "share" / "atuin" / "atuin.sock")

    return list(dict.fromkeys(candidates))


def discover_target(socket: str | Path | None, tcp: str | None) -> tuple[str, str]:
    if tcp:
        return tcp, tcp

    if os.name == "nt":
        target = "127.0.0.1:8889"
        return target, target

    if socket is not None:
        sock = Path(socket).expanduser().resolve()
        return f"unix://{sock}", str(sock)

    for sock in unix_socket_candidates():
        if sock.exists():
            return f"unix://{sock}", str(sock)

    checked = "\n".join(f"  - {candidate}" for candidate in unix_socket_candidates())
    msg = (
        "Could not find an Atuin daemon socket.\n"
        f"Checked:\n{checked}\n"
        "If daemon.socket_path is customized, pass socket=/path/to/atuin.sock."
    )
    raise FileNotFoundError(msg)


def create_channel(target: str) -> grpc.aio.Channel:
    # Atuin's tonic UDS client uses this HTTP/2 :authority for streaming.
    # The version interceptor deliberately never reflects the daemon build:
    # differing builds must not bypass Atuin's compatibility check.
    return grpc.aio.insecure_channel(
        target,
        options=(("grpc.default_authority", ATUIN_AUTHORITY),),
        interceptors=(_BuildInterceptor(),),
    )
