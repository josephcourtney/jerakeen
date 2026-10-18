from __future__ import annotations

import os
import re
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - fixed executable, no shell
from pathlib import Path

import grpc

ATUIN_AUTHORITY = "atuin_local_daemon:0"

BUILD_HEADER = "x-atuin-build"
VALIDATED_BUILD = "18.24.1"


# A Git-checkout build is accepted only when both peers report the *same*
# version and revision. A matching version prefix alone is insufficient.
def supported_build(value: str | None) -> bool:
    return value is not None and re.fullmatch(
        rf"{re.escape(VALIDATED_BUILD)}(?:\+[0-9a-f]{{40}})?", value
    ) is not None


def local_atuin_build() -> str | None:
    """Identify the installed executable build, not the daemon identity."""
    executable = shutil.which("atuin")
    if executable is None:
        return None
    result = subprocess.run(
        [executable, "--version"],
        capture_output=True,
        text=True,
        check=True,
        timeout=5,
    )
    match = re.fullmatch(r"atuin ([0-9]+\.[0-9]+\.[0-9]+) \(([^)]+)\)", result.stdout.strip())
    if match is None:
        msg = "Cannot determine local Atuin build"
        raise RuntimeError(msg)
    version, revision = match.groups()
    return version if revision == "NO_GIT" else f"{version}+{revision}"


class BuildMetadata:
    """Connection-scoped build identity established before any gated RPC."""

    def __init__(self, value: str | None = None) -> None:
        self.value = value

    def details(self, details: grpc.aio.ClientCallDetails) -> grpc.aio.ClientCallDetails:
        if self.value is None:
            return details
        metadata = tuple((k, v) for k, v in (details.metadata or ()) if k != BUILD_HEADER)
        return grpc.aio.ClientCallDetails(
            details.method,
            details.timeout,
            (*metadata, (BUILD_HEADER, self.value)),
            details.credentials,
            details.wait_for_ready,
        )


class BuildInterceptor(
    grpc.aio.UnaryUnaryClientInterceptor,
    grpc.aio.UnaryStreamClientInterceptor,
    grpc.aio.StreamUnaryClientInterceptor,
    grpc.aio.StreamStreamClientInterceptor,
):
    """Stamp all four gRPC method shapes with the validated build."""

    def __init__(self, state: BuildMetadata) -> None:
        self.state = state

    async def intercept_unary_unary(self, continuation, client_call_details, request):
        return await continuation(self.state.details(client_call_details), request)

    async def intercept_unary_stream(self, continuation, client_call_details, request):
        return await continuation(self.state.details(client_call_details), request)

    async def intercept_stream_unary(self, continuation, client_call_details, request_iterator):
        return await continuation(self.state.details(client_call_details), request_iterator)

    async def intercept_stream_stream(self, continuation, client_call_details, request_iterator):
        return await continuation(self.state.details(client_call_details), request_iterator)


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


def discover_target(
    socket: str | Path | None,
    tcp: str | None,
) -> tuple[str, str]:
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


def create_channel(target: str, *, build: BuildMetadata | None = None) -> grpc.aio.Channel:
    # Atuin's tonic client uses http://atuin_local_daemon:0 as the logical
    # endpoint while transporting over the Unix socket. grpcio must send the
    # same HTTP/2 :authority or tonic/hyper can reset streaming RPCs.
    if build is None:
        return grpc.aio.insecure_channel(target, options=(("grpc.default_authority", ATUIN_AUTHORITY),))
    return grpc.aio.insecure_channel(
        target,
        options=(("grpc.default_authority", ATUIN_AUTHORITY),),
        interceptors=[BuildInterceptor(build)],
    )
