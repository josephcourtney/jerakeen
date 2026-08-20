# POLICY.md

## Product boundary

jerakeen exposes Atuin's local daemon gRPC API as a Pythonic, typed async client. Atuin remains authoritative for history storage, search indexing, command-output capture, synchronization, and daemon lifecycle.

jerakeen owns transport discovery, protocol binding, compatibility checks, Python model conversion, validation, timeout policy, error translation, and higher-level conveniences that preserve daemon semantics.

## Protocol compatibility

The supported wire protocol is the vendored Atuin snapshot recorded in `proto/atuin/VERSION`. Connection performs a History/Status handshake and rejects an unsupported daemon protocol by default. Callers may disable rejection to inspect an incompatible daemon, but jerakeen does not promise correct RPC behavior in that mode.

Generated protobuf code is not public API. Backward compatibility applies to documented `jerakeen` imports and call semantics, not `jerakeen._proto`.

## Reliability

Finite daemon operations use a configurable gRPC deadline. Live history tails and general search streams are intentionally unbounded unless an explicit whole-stream timeout is supplied. Interactive search sessions apply the configured timeout per query while retaining a long-lived bidirectional stream.

## Privacy and persistence

jerakeen does not add a history database, command-output cache, or telemetry store. Data returned by Atuin is held only as required by the caller and normal Python object lifetimes.

## Releases

Public behavior changes belong in `CHANGELOG.md`. When updating Atuin protobufs, update compatibility metadata and contract coverage in the same change.
