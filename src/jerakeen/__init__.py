from jerakeen.client import Atuin, connect
from jerakeen.control import ControlClient
from jerakeen.exceptions import (
    AtuinConnectionError,
    AtuinError,
    AtuinNotFoundError,
    AtuinProtocolError,
    AtuinRpcError,
    AtuinUnsupportedError,
)
from jerakeen.history import HistoryClient
from jerakeen.models import (
    CommandCapture,
    CommandOutput,
    DaemonStatus,
    FilterMode,
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

__version__ = "0.9.3"

__all__ = [
    "Atuin",
    "AtuinConnectionError",
    "AtuinError",
    "AtuinNotFoundError",
    "AtuinProtocolError",
    "AtuinRpcError",
    "AtuinUnsupportedError",
    "CommandCapture",
    "CommandOutput",
    "ControlClient",
    "DaemonStatus",
    "FilterMode",
    "HistoryClient",
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
