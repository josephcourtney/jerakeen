# POLICY.md

## Product boundary

jerakeen is a Python client library and CLI for Atuin's local daemon gRPC interface.

Atuin owns command history, command metadata, search state, semantic command output, daemon lifecycle, and the underlying storage. jerakeen owns only the client-side transport, typed Python API, protocol adaptation, CLI presentation, and diagnostics around that daemon interface.

jerakeen must not become a second history system.

## Protocol boundary

The supported integration boundary is the Atuin daemon gRPC API represented by the protobuf definitions vendored under `proto/atuin/`.

jerakeen must not depend on:

- Atuin's private SQLite schema;
- undocumented database files or internal storage layouts;
- implementation details that bypass the daemon RPC interface.

The generated protobuf and gRPC modules under `src/jerakeen/_proto/` are private implementation details. Public callers should use the high-level jerakeen API instead.

The vendored Atuin proto version is recorded in `proto/atuin/VERSION`. Changes to those files must be regenerated through `scripts/generate_protos.py` and validated before release.

## Data ownership and persistence

jerakeen does not maintain its own persistent command-history database, semantic-output cache, journal, synchronization store, or background daemon.

History and semantic output remain owned by Atuin.

Captured command output may be unavailable or may expire according to Atuin's behavior. jerakeen must treat that as a supported partial-data state rather than persisting a duplicate copy.

## Compatibility

jerakeen should preserve a stable Python-facing API where practical even when the underlying protobuf interface evolves.

Protocol evolution should be handled at the wrapper boundary by:

- converting protobuf messages to jerakeen domain models;
- keeping generated bindings private;
- translating gRPC errors into jerakeen exceptions;
- validating unknown or malformed protocol values and raising `AtuinProtocolError` when appropriate.

Do not silently reinterpret incompatible protocol changes.

## Transport

Unix-domain sockets are the normal local transport on supported Unix systems; TCP may be used where appropriate.

Transport-specific behavior belongs in `_transport.py`.

The Atuin HTTP/2 authority value required for Unix-socket compatibility is part of jerakeen's transport implementation and should not leak into normal caller code.

## Privacy

jerakeen should request only the daemon data needed for the caller's operation.

It should not persist command output or history beyond normal in-memory objects created while servicing a request.

Atuin's own retention, encryption, synchronization, and privacy behavior governs the underlying data.

## Testing and releases

Changes to service wrappers or protobuf handling should include coverage at the appropriate levels:

- unit wrapper tests;
- protobuf contract tests;
- real gRPC integration tests.

User-visible behavior changes belong in `CHANGELOG.md`.

Before release, run `just check` and review generated protobuf diffs when the vendored protocol has changed.

Do not claim validation succeeded when a required tool or check was not actually run.
