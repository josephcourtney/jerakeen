# AGENTS.md

jerakeen is a small Python client library and CLI for Atuin's local daemon gRPC interface.

Atuin is authoritative for command history, command metadata, search state, semantic command output, and daemon lifecycle. jerakeen provides a typed, Pythonic async API over that interface and a small CLI for observing live history activity.

## Architecture constraints

- Treat the vendored Atuin protobuf definitions under `proto/atuin/` as the protocol source of truth.
- Keep generated protobuf and gRPC bindings under `src/jerakeen/_proto/` private implementation details.
- Expose normal callers to the high-level API in `client.py`, `history.py`, `semantic.py`, `search.py`, and `control.py`.
- Do not depend on Atuin's private SQLite schema or other internal storage details.
- Do not add a second command-history database, output cache, journal, daemon, or persistent synchronization layer to jerakeen.
- Preserve Atuin's daemon as the owner of history and captured output. Missing or expired semantic output is a supported state.
- Keep protobuf-to-domain conversion at the service-wrapper boundary. Public APIs should prefer dataclasses, enums, async iterators, and jerakeen exceptions over raw protobuf messages and `grpc.aio.AioRpcError`.
- Keep transport-specific behavior, including Unix-socket discovery and the Atuin HTTP/2 authority workaround, isolated in `_transport.py`.
- Keep gRPC error translation isolated in `_rpc.py` and `exceptions.py`.
- Prefer small structural `Protocol` interfaces for service stubs so production generated stubs and typed test doubles can share the same wrapper code.
- Do not edit generated `_pb2.py`, `_pb2.pyi`, `_pb2_grpc.py`, or `_pb2_grpc.pyi` files by hand when the same change can be made reproducibly in `scripts/generate_protos.py`.

## Protobuf updates

The Atuin daemon protobuf version vendored by jerakeen is recorded in `proto/atuin/VERSION`.

When updating the daemon interface:

1. Copy `crates/atuin-daemon/proto/*.proto` from the intended Atuin release into `proto/atuin/`.
2. Update `proto/atuin/VERSION`.
3. Run `just proto`.
4. Review all generated diffs.
5. Run `just check`.

Generated bindings are committed so users do not need `protoc` or `grpcio-tools` at runtime.

## Public API guidance

- Keep `jerakeen._proto` private.
- Prefer backwards-compatible additions to public dataclasses and service methods.
- Keep async streaming APIs as `AsyncIterator`/`AsyncIterable` abstractions where practical.
- Translate protocol inconsistencies into `AtuinProtocolError`.
- Translate gRPC transport/status failures into the public jerakeen exception hierarchy.
- Avoid exposing transport configuration unless callers genuinely need it.
- Keep the CLI implemented in terms of the same public client API used by library consumers.

## Testing

The test suite should cover three layers:

- unit tests for every public wrapper method and conversion path;
- protobuf contract tests for vendored messages, fields, enums, `oneof`s, RPCs, and streaming shapes;
- real `grpc.aio` integration tests over TCP and Unix-domain sockets where supported.

When adding or changing an RPC wrapper, add tests for both the Python-facing behavior and the underlying request/response shape.

## Validation

Run `just check` for substantive changes. It runs syntax checks, formatting, linting, static type checking, and tests.

Use targeted pytest tests while iterating.

Do not claim a check passed when the required tool was unavailable or not run.
