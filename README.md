# jerakeen

Python client and CLI for Atuin's local daemon gRPC interface.

The package vendors the Atuin daemon protobuf definitions under `proto/atuin/` and commits their generated Python bindings under `src/jerakeen/_proto/`. Normal callers use the high-level API and do not need to import protobuf modules directly.

## Python API

```python
import asyncio

from jerakeen import HistoryEnded, connect


async def main() -> None:
    async with connect(socket="~/.cache/atuin.sock") as atuin:
        status = await atuin.status()
        print(status.version)

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

The protobuf/gRPC layer is private implementation detail in `jerakeen._proto`.

## CLI

```console
jerakeen --socket ~/.cache/atuin.sock
jerakeen --output
jerakeen --json
```

## Updating Atuin protobufs

The vendored source version is recorded in `proto/atuin/VERSION`.

1. Copy `crates/atuin-daemon/proto/*.proto` from the target Atuin release into `proto/atuin/`.
2. Update `proto/atuin/VERSION`.
3. Run `just proto`.
4. Review the generated diff and run `just check`.

`grpcio-tools` is a development dependency only. Users installing `jerakeen` receive the checked-in generated bindings and do not need `protoc`.

## Testing

The test suite has three layers:

- unit tests for every public service-wrapper method and message conversion path;
- protobuf contract tests covering every vendored message, field number, enum, `oneof`, RPC, and streaming shape;
- real `grpc.aio` integration tests exercising all four services over TCP and Unix-domain sockets (where supported).

Run the full suite with:

```console
just test
```

Run it with branch-aware coverage with:

```console
just test-cov
```

Run the static type checker with:

```console
just typecheck
```

The integration server uses the checked-in generated serializers and deserializers, so these tests exercise actual protobuf encoding and gRPC framing rather than only fake stubs.
