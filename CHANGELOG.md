# Changelog

## Unreleased

### Breaking changes

- Target Atuin 18.24.1's exact build-gated daemon interface. All four gRPC request shapes announce `x-atuin-build: 18.24.1`; customized or older binaries are rejected rather than bypassing the daemon's build guard.
- Adopt the Atuin 18.24.1 history proto snapshot, which removes the numeric daemon protocol and per-reply version/protocol fields. Public compatibility protocol metadata is now `None` where upstream removed it.

### Added

- Add exact-build identity interception, readable `AtuinCompatibilityError` for daemon build refusals, in-process TCP/Unix gRPC coverage, and strict protocol-shape tests.


### Added

- Vendor Atuin 18.24.0 / daemon protocol 5 while retaining protocol 3 compatibility for unchanged RPCs, including output retrieval and lagged history events.
- Expose protocol-5 `History.CompactStore` as an explicit, typed maintenance operation; live qualification never invokes it.
- Add protocol-5 TCP/Unix gRPC integration coverage and update the non-mutating live-daemon contract.


## 0.10.0 - 2026-09-23

### Breaking changes

- Move the supported daemon snapshot from Atuin 18.19 protocol 1 to Atuin 18.23 protocol 3. Protocol 1 is no longer accepted by this API line.
- Remove the obsolete public `SemanticClient`, `ControlClient`, `atuin.semantic`, and `atuin.control` service surfaces because Atuin removed those daemon services.
- Move captured-output registration and retrieval to `HistoryClient` as `register_output()` and `output()`.
- Change history lifecycle IDs to `uuid.UUID`; `HistoryEnd` now reports the protocol-3 `record_id` and `record_idx` rather than the old history `id`/`idx` reply shape.
- Replace the old semantic `CommandCapture` model with protocol-3 retained-output segments and `CommandCaptureMeta`.

### Added

- Protocol-3 `common.proto`, structured History/Record UUID conversion, protobuf `Duration` handling, history delete/rebuild RPCs, cancelled tail events, and lag notifications.
- Captured-output chunk/range models including retained head/tail line numbering and capture metadata.
- Full-text captured-output search through `SearchClient.output()` with ranked matches and highlighted lines.
- `AuthorKind`, `HistoryCancelled`, `HistoryLagged`, `HistoryDelete`, `HistoryRebuild`, `CommandCaptureMeta`, `OutputChunk`, `HighlightedText`, `OutputSearchLine`, and `OutputSearchMatch` public models.
- Deterministic protocol generation with `just proto-check`.

### Changed

- Whole-output retrieval explicitly requests Atuin's `[0, -1]` inclusive range and maps gRPC `NOT_FOUND` to `None`.
- `HistoryClient.end()` accepts an omitted duration and encodes supplied nanoseconds as `google.protobuf.Duration`.
- The CLI retrieves ended-command output through `History.GetCommandOutput` and reports `cancelled` and `lagged` tail events.
- Live-daemon coverage now verifies protocol 3 and non-mutating command-output retrieval.

### Fixed

- Prevent a protocol-1 client from connecting to a protocol-3 daemon and failing later with `UNIMPLEMENTED`; compatibility is rejected at the status handshake unless explicitly disabled for diagnostics.
