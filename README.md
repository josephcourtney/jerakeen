# jerakeen

Typed async Python client and CLI for Atuin's local daemon gRPC interface.

Jerakeen vendors the daemon protobuf snapshot it supports under `proto/atuin/` and commits private generated bindings under `src/jerakeen/_proto/`. The public API exposes Python models (`UUID`, `datetime`, dataclasses, iterables, async iterators) rather than protobuf objects.

The current API targets **Atuin 18.23 / daemon protocol 3**. Protocol 1 is intentionally not accepted by this release because Atuin's daemon API changed service boundaries and wire types substantially between 18.19 and 18.23.

## Services

Protocol 3 exposes two daemon services through Jerakeen:

- `atuin.history` — status, command lifecycle, deletion/rebuild, live tailing, command-output registration and retrieval, daemon shutdown
- `atuin.search` — history search, interactive search sessions, index preparation, and full-text search across captured output

Atuin 18.23 removed the old `Semantic` and `Control` gRPC services. Their functionality is not emulated as fake services: command output now belongs to `History`; maintenance operations that remain public are exposed by `History`.

## Connect

```python
from jerakeen import connect

async with connect() as atuin:
    print(atuin.version, atuin.protocol)
    status = await atuin.status()
    print(status.healthy)
```

Connection performs a stable `History.Status` handshake and rejects unsupported daemon protocols by default. Pass `check_compatibility=False` only for diagnostics; other RPCs are not promised to work against an incompatible protocol.

## Captured command output

```python
output = await atuin.history.output(history_id)
if output is not None:
    print(output.text)
    print(output.total_lines, output.truncated)
```

`history.output()` requests the complete retained output by default using Atuin's `[0, -1]` line range. It returns `None` when the daemon reports `NOT_FOUND`. Partial ranges can be requested with inclusive `(start, end)` tuples or slices:

```python
output = await atuin.history.output(history_id, ranges=[(0, 10), slice(-10, -1)])
```

Captured output can be registered explicitly:

```python
from jerakeen import CommandCapture, CommandCaptureMeta

await atuin.history.register_output(
    history_id,
    CommandCapture(
        output_start="first retained output",
        output_end="last retained output",
        meta=CommandCaptureMeta(
            observed_bytes=200_000,
            terminal_width=120,
            terminal_height=40,
        ),
    ),
)
```

## History lifecycle

History IDs and record IDs are exposed as `uuid.UUID` values. Protocol-3 structured UUID messages are confined to the private wire layer.

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

`history.end()` accepts `duration_ns=None`; when omitted, the daemon derives duration from the command start time. `TailHistory` yields started, ended, cancelled, and lagged events. Lagged events are preserved so callers know when the daemon dropped live events.

Maintenance RPCs are available directly:

```python
await atuin.history.delete(history_ids)
await atuin.history.rebuild()
await atuin.history.shutdown()
```

## Search

History search retains the query-correlation API from earlier Jerakeen releases:

```python
from jerakeen import FilterMode, SearchContext

result = await atuin.search.query(
    "git status",
    filter_mode=FilterMode.WORKSPACE,
    context=SearchContext(cwd="/repo", git_root="/repo"),
)
```

For interactive search:

```python
async with atuin.search.session() as search:
    result = await search.query("git")
```

Protocol 3 also supports full-text search over captured command output:

```python
async for match in atuin.search.output("traceback", limit=20, context=2):
    print(match.history_id, match.score)
    for line in match.lines:
        print(line.line, line.content.raw)
```

## CLI

```console
jerakeen
jerakeen --output
jerakeen --json
jerakeen --rpc-timeout 10
```

The CLI streams `History.TailHistory`. `--output` fetches captured output for ended commands through `History.GetCommandOutput`.

## Updating the Atuin protocol snapshot

1. Copy the target release's `crates/atuin-daemon/proto/*.proto` files into `proto/atuin/`.
2. Update `proto/atuin/VERSION`.
3. Update `VENDORED_ATUIN_VERSION` and `SUPPORTED_PROTOCOLS` in `jerakeen.compatibility`.
4. Run `just proto`.
5. Run `just proto-check` and inspect the service/message contract changes.
6. Update the Python service wrappers and contract/integration tests in the same change.
7. Run `just check`.

`generate_protos.py` canonicalizes generated modules from protobuf descriptors so committed output is deterministic and package-relative. `grpcio-tools` is a development dependency only.

## Testing

```console
just check
```

A non-mutating live contract test can be run against an installed Atuin 18.23 daemon:

```console
CATUIN_LIVE_TEST=1 uv run pytest tests/test_live_atuin.py
```
