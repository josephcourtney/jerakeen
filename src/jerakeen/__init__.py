from importlib.metadata import PackageNotFoundError, version

from jerakeen.client import Atuin, connect
from jerakeen.compatibility import (
    SUPPORTED_PROTOCOLS,
    VENDORED_ATUIN_VERSION,
    Compatibility,
)
from jerakeen.exceptions import (
    AtuinCompatibilityError,
    AtuinConnectionError,
    AtuinError,
    AtuinNotFoundError,
    AtuinProtocolError,
    AtuinRpcError,
    AtuinTimeoutError,
    AtuinUnsupportedError,
)
from jerakeen.history import HistoryClient
from jerakeen.models import (
    AuthorKind,
    CommandCapture,
    CommandCaptureMeta,
    CommandOutput,
    DaemonStatus,
    FilterMode,
    HighlightedText,
    HistoryCancel,
    HistoryCancelled,
    HistoryCommand,
    HistoryDelete,
    HistoryEnd,
    HistoryEnded,
    HistoryEvent,
    HistoryEventRecord,
    HistoryLagged,
    HistoryRebuild,
    HistoryStart,
    HistoryStarted,
    OutputChunk,
    OutputSearchLine,
    OutputSearchMatch,
    SearchContext,
    SearchQuery,
    SearchResult,
)
from jerakeen.search import SearchClient, SearchSession

try:
    __version__ = version("jerakeen")
except PackageNotFoundError:
    __version__ = "0+unknown"

__all__ = [
    "SUPPORTED_PROTOCOLS",
    "VENDORED_ATUIN_VERSION",
    "Atuin",
    "AtuinCompatibilityError",
    "AtuinConnectionError",
    "AtuinError",
    "AtuinNotFoundError",
    "AtuinProtocolError",
    "AtuinRpcError",
    "AtuinTimeoutError",
    "AtuinUnsupportedError",
    "AuthorKind",
    "CommandCapture",
    "CommandCaptureMeta",
    "CommandOutput",
    "Compatibility",
    "DaemonStatus",
    "FilterMode",
    "HighlightedText",
    "HistoryCancel",
    "HistoryCancelled",
    "HistoryClient",
    "HistoryCommand",
    "HistoryDelete",
    "HistoryEnd",
    "HistoryEnded",
    "HistoryEvent",
    "HistoryEventRecord",
    "HistoryLagged",
    "HistoryRebuild",
    "HistoryStart",
    "HistoryStarted",
    "OutputChunk",
    "OutputSearchLine",
    "OutputSearchMatch",
    "SearchClient",
    "SearchContext",
    "SearchQuery",
    "SearchResult",
    "SearchSession",
    "connect",
]
