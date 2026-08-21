import asyncio
from dataclasses import dataclass

from jerakeen import AtuinError, connect


async def atuin_is_running() -> bool:
    try:
        async with connect(timeout=1.0) as atuin:
            status = await atuin.status()
    except (AtuinError, FileNotFoundError):
        return False

    if status:
        print("healthy:", status.healthy)
        print("version:", status.version)
        print("protocol:", status.protocol)
        print("pid:", status.pid)
        return status.healthy
    return None


@dataclass(frozen=True)
class PreviousCommand:
    history_id: str
    command: str
    timestamp: str
    duration: str
    exit_status: int
    output: str | None


def markdown_escape_code(code):
    if len(code.splitlines()) > 1:
        return f"```\n{code}\n```"
    return f"`{code}`"


async def get_last_history() -> tuple[str, str, str, str, int]:
    # IMPORTANT:
    # Run Atuin before creating the jerakeen/gRPC connection.
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

    text = stdout.decode().rstrip("\n")

    history_id, exit_status, timestamp, duration, command = text.split("\t", 4)

    return (
        history_id,
        command,
        timestamp,
        duration,
        int(exit_status),
    )


async def main() -> None:
    # Fork/spawn first, before gRPC has started any threads.
    (
        history_id,
        command,
        timestamp,
        duration,
        exit_status,
    ) = await get_last_history()

    # Only now start using jerakeen/gRPC.
    try:
        async with connect(timeout=1.0) as atuin:
            status = await atuin.status()
    except (AtuinError, FileNotFoundError):
        print("Atuin daemon is not running")
        return

    print("healthy:", status.healthy)
    print("version:", status.version)
    print("protocol:", status.protocol)
    print("pid:", status.pid)
    print()

    async with connect(timeout=1.0) as atuin:
        captured = await atuin.semantic.output(history_id)

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
    if previous.command:
        print(markdown_escape_code(previous.command))
    else:
        print("<no command>")

    print(f"command: `{previous.command}`")

    print("stdout:")
    if previous.output:
        print(markdown_escape_code(previous.output))
    else:
        print("<stdout capture empty>")

    print("stderr:")
    if previous.error:
        print(markdown_escape_code(previous.error))
    else:
        print("<stderr capture empty>")


asyncio.run(main())
