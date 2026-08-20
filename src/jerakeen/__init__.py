from importlib.metadata import PackageNotFoundError, version

from jerakeen.client import Atuin, connect
from jerakeen.compatibility import (
    SUPPORTED_PROTOCOLS,
    VENDORED_ATUIN_VERSION,
    Compatibility,
)
from jerakeen.control import ControlClient
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
    CommandCapture,
    CommandOutput,
    DaemonStatus,
    FilterMode,
    HistoryCancel,
    HistoryCommand,
    HistoryEnd,
    HistoryEnded,
    HistoryEvent,
    HistoryEventRecord,
    HistoryStart,
    HistoryStarted,
    OutputLine,
    SearchContext,
    SearchQuery,
    SearchResult,
)
from jerakeen.search import SearchClient, SearchSession
from jerakeen.semantic import SemanticClient

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
    "CommandCapture",
    "CommandOutput",
    "Compatibility",
    "ControlClient",
    "DaemonStatus",
    "FilterMode",
    "HistoryCancel",
    "HistoryClient",
    "HistoryCommand",
    "HistoryEnd",
    "HistoryEnded",
    "HistoryEvent",
    "HistoryEventRecord",
    "HistoryStart",
    "HistoryStarted",
    "OutputLine",
    "SearchClient",
    "SearchContext",
    "SearchQuery",
    "SearchResult",
    "SearchSession",
    "SemanticClient",
    "connect",
]
