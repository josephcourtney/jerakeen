# POLICY.md

## Product boundary

jerakeen exposes Atuin's local daemon gRPC API as a Pythonic, typed async client. Atuin remains authoritative for history storage, search indexing, command-output capture, synchronization, and daemon lifecycle.

jerakeen owns transport discovery, protocol binding, compatibility checks, Python model conversion, validation, timeout policy, error translation, and higher-level conveniences that preserve daemon semantics.

## Protocol compatibility

The supported wire protocol is the vendored Atuin snapshot recorded in `proto/atuin/VERSION`. A release supports only protocols for which its complete generated bindings and service wrappers are tested. Adding a protocol number to `SUPPORTED_PROTOCOLS` without migrating every affected wire shape is not sufficient.

Connection performs a stable `History.Status` handshake and rejects an unsupported daemon protocol by default. Callers may disable rejection to inspect an incompatible daemon, but jerakeen does not promise correct feature RPC behavior in that mode.

Generated protobuf code is private API. Backward compatibility applies to documented `jerakeen` imports and call semantics, not `jerakeen._proto`.

## Service model

Public decomposition follows the daemon services in the vendored snapshot. For Atuin 18.23 / protocol 3 that means `history` and `search`. Removed daemon services are not kept alive as synthetic protocol facades. Functionality that moved between Atuin services moves to the corresponding Jerakeen client.

Wire identifiers are converted to `uuid.UUID` at the public boundary. Optional fields, oneofs, stream direction, line-range conventions, and `NOT_FOUND` semantics must be preserved rather than inferred from older protocol versions.

## Reliability

Finite daemon operations use a configurable gRPC deadline. Live history tails, general search streams, and captured-output search streams are intentionally unbounded unless an explicit whole-stream timeout is supplied. Interactive search sessions apply the configured timeout per query while retaining a long-lived bidirectional stream.

Malformed logically-required protocol fields raise `AtuinProtocolError`. gRPC status codes are translated into the public `AtuinError` hierarchy.

## Privacy and persistence

jerakeen does not add a history database, command-output cache, or telemetry store. Data returned by Atuin is held only as required by the caller and normal Python object lifetimes.

## Releases

Public behavior changes belong in `CHANGELOG.md`. Protocol updates must update the vendored proto snapshot, generated bindings, compatibility metadata, public wrappers, contract tests, live integration coverage, and documentation together.
