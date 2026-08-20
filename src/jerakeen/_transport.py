from __future__ import annotations

import os
from pathlib import Path

import grpc

ATUIN_AUTHORITY = "atuin_local_daemon:0"


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


def create_channel(target: str) -> grpc.aio.Channel:
    # Atuin's tonic client uses http://atuin_local_daemon:0 as the logical
    # endpoint while transporting over the Unix socket. grpcio must send the
    # same HTTP/2 :authority or tonic/hyper can reset streaming RPCs.
    return grpc.aio.insecure_channel(
        target,
        options=(("grpc.default_authority", ATUIN_AUTHORITY),),
    )
