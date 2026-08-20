# Changelog

## Unreleased

### Changed

- Add a configurable finite-RPC deadline (`rpc_timeout`, default 5 seconds) while leaving live history and general search streams unbounded unless explicitly requested.
- Perform a daemon status/compatibility handshake during connection and expose `Atuin.version`, `Atuin.protocol`, and `Atuin.compatibility`.
- Convert daemon search-result history IDs from their 16-byte wire representation to `uuid.UUID` objects.
- Validate search contexts for host, session, directory, workspace, and session-preload filters so incomplete requests cannot silently degrade to global search.
- Make `SearchSession` allocate query IDs automatically, correlate responses by ID, support concurrent outstanding queries, and apply the RPC timeout per interactive query.
- Return `HistoryCancel` metadata from `HistoryClient.cancel()`.
- Yield a mutable `HistoryCommand` lifecycle handle from `HistoryClient.command()` so exit status and duration can be supplied after command execution.
- Derive `jerakeen.__version__` from installed package metadata instead of maintaining a second version constant.

### Added

- `AtuinTimeoutError` and `AtuinCompatibilityError`.
- Protocol compatibility metadata for the vendored Atuin 18.19.0 daemon protocol.
- Opt-in, non-mutating live-daemon integration coverage via `CATUIN_LIVE_TEST=1`.
- Tests for RPC deadlines, search response correlation, out-of-order concurrent queries, malformed history IDs, query timeouts, search-context validation, and incompatible daemon protocols.

### Fixed

- Replace stale Copout/MCP contributor and product-policy documentation with jerakeen's daemon-gRPC architecture and compatibility policy.
- Align the package metadata version with the 0.9.3 API line.
