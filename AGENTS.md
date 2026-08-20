# AGENTS.md

jerakeen is a small, typed Python client for Atuin's local daemon gRPC interface.

## Architecture constraints

- Treat the vendored files under `proto/atuin/` as the wire-protocol source of truth for the supported Atuin snapshot.
- Generated protobuf/gRPC modules under `src/jerakeen/_proto/` are private implementation detail. Public APIs must use Python domain models and standard Python types.
- Keep the public decomposition aligned with the daemon services: `history`, `semantic`, `search`, and `control`.
- Do not depend on Atuin's SQLite schema, MCP server, CLI output formats, or other interfaces when the daemon RPC already exposes the capability.
- Preserve protocol semantics, including protobuf optional-field presence, streaming shape, query correlation, and daemon protocol versioning.
- Finite RPCs must have configurable deadlines. Long-lived streams must not inherit a short unary-RPC deadline implicitly.
- New daemon protocol versions must be added deliberately: update the vendored protos, `proto/atuin/VERSION`, compatibility metadata, generated bindings, contract tests, and integration tests together.

## Public API

- Prefer immutable slotted dataclasses for returned values and Python-native representations such as `datetime`, `Path`, `UUID`, iterables, and async iterators.
- Translate raw gRPC failures into the public `AtuinError` hierarchy.
- Validate caller mistakes locally when the daemon would otherwise silently change semantics.
- Avoid exposing `_proto`, generated stubs, grpc call objects, or protobuf enum integers through the normal API.

## Validation

Run `just check` for substantive changes. Protocol changes additionally require `just proto` and the protobuf contract tests. The opt-in live-daemon test is run with `CATUIN_LIVE_TEST=1` against an installed Atuin daemon and must remain non-mutating.
