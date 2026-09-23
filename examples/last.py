import asyncio
from dataclasses import dataclass

from jerakeen import AtuinError, connect


@dataclass(frozen=True)
class PreviousCommand:
    history_id: str
    command: str
    timestamp: str
    duration: str
    exit_status: int
    output: str | None


def markdown_escape_code(code: str) -> str:
    if len(code.splitlines()) > 1:
        return f"```\n{code}\n```"
    return f"`{code}`"


async def get_last_history() -> tuple[str, str, str, str, int]:
    # Run Atuin before opening a gRPC channel; grpcio owns background threads and
    # POSIX fork after gRPC initialization can produce warnings.
    proc = await asyncio.create_subprocess_exec(
        "atuin",
        "history",
        "last",
        "--format",
        "{uuid}\t{exit}\t{time}\t{duration}\t{command}",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(stderr.decode())

    history_id, exit_status, timestamp, duration, command = stdout.decode().rstrip("\n").split(
        "\t", 4
    )
    return history_id, command, timestamp, duration, int(exit_status)


async def main() -> None:
    history_id, command, timestamp, duration, exit_status = await get_last_history()

    try:
        async with connect(timeout=1.0) as atuin:
            status = await atuin.status()
            captured = await atuin.history.output(history_id)
    except (AtuinError, FileNotFoundError):
        print("Atuin daemon is not running or is incompatible")
        return

    print("healthy:", status.healthy)
    print("version:", status.version)
    print("protocol:", status.protocol)
    print("pid:", status.pid)
    print()

    previous = PreviousCommand(
        history_id=history_id,
        command=command,
        timestamp=timestamp,
        duration=duration,
        exit_status=exit_status,
        output=None if captured is None else captured.text,
    )

    print(f"id:       {previous.history_id}")
    print(f"ran at:   {previous.timestamp}")
    print(f"duration: {previous.duration}")
    print(f"exit:     {previous.exit_status}")
    print("command:")
    print(markdown_escape_code(previous.command) if previous.command else "<no command>")
    print("output:")
    print(markdown_escape_code(previous.output) if previous.output else "<captured output empty>")


asyncio.run(main())
