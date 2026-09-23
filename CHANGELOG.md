# Changelog

## 0.10.0 - 2026-09-23

### Breaking changes

- Move the supported daemon snapshot from Atuin 18.19 protocol 1 to Atuin 18.23 protocol 3. Protocol 1 is no longer accepted by this release.
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
