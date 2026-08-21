# jerakeen

Python client and CLI for Atuin's local daemon gRPC interface.

The package vendors the Atuin daemon protobuf definitions under `proto/atuin/` and commits generated Python bindings under `src/jerakeen/_proto/`. Normal callers use the high-level API and do not import protobuf modules directly.

## Python API

```python
import asyncio

from jerakeen import HistoryEnded, connect


async def main() -> None:
    async with connect(socket="~/.cache/atuin.sock") as atuin:
        print(atuin.version, atuin.protocol)

        async for event in atuin.history.tail():
            print(event.command)
            if isinstance(event, HistoryEnded):
                print(await atuin.semantic.output(event.id))


asyncio.run(main())
```

The four daemon services are exposed as:

- `atuin.history` — status, history lifecycle, and live tailing
- `atuin.semantic` — captured command output and command capture submission
- `atuin.search` — one-shot, streaming, and session-oriented search
- `atuin.control` — force sync, reload settings, history index events, and shutdown

### Search

Search results expose history IDs as `uuid.UUID` values. Filter-specific context is validated before the request is sent.

```python
from jerakeen import FilterMode, SearchContext

result = await atuin.search.query(
    "git status",
    filter_mode=FilterMode.WORKSPACE,
    context=SearchContext(cwd="/repo", git_root="/repo"),
)
```

For interactive use, a search session assigns query IDs automatically and can correlate concurrent outstanding queries:

```python
async with atuin.search.session() as search:
    result = await search.query("git")
```

Explicit query IDs remain supported when an application needs them.

### History lifecycle

`history.command()` yields a lifecycle handle whose completion data can be set after the command runs:

```python
async with atuin.history.command(
    "make test",
    cwd="/repo",
    session="session-id",
    hostname="host:user",
) as command:
    completed = await run_command()
    command.exit_code = completed.returncode
```

On normal exit the history entry is ended; on an exception it is cancelled. `history.cancel()` returns the daemon's version/protocol metadata as `HistoryCancel`.

## CLI

```console
jerakeen --socket ~/.cache/atuin.sock
jerakeen --output
jerakeen --json
jerakeen --rpc-timeout 10
```

## Updating Atuin protobufs

The vendored source version is recorded in `proto/atuin/VERSION`.

1. Copy `crates/atuin-daemon/proto/*.proto` from the target Atuin release into `proto/atuin/`.
2. Update `proto/atuin/VERSION`.
3. Update `VENDORED_ATUIN_VERSION` and `SUPPORTED_PROTOCOLS` in `jerakeen.compatibility`.
4. Run `just proto`.
5. Review the generated diff and run `just check`.

`grpcio-tools` is a development dependency only. Users installing jerakeen receive the checked-in generated bindings and do not need `protoc`.

## Testing

The test suite includes unit coverage for public wrappers and conversion paths, protobuf contract checks, and real `grpc.aio` framing tests over TCP and Unix-domain sockets.

```console
just test
just typecheck
just check
```

A non-mutating smoke test can also be run against an installed local Atuin daemon:

```console
CATUIN_LIVE_TEST=1 uv run pytest tests/test_live_atuin.py
```
