from __future__ import annotations

import contextlib
import io
import json
import unittest
from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch
from uuid import UUID

from jerakeen import _cli_output
from jerakeen.exceptions import AtuinProtocolError
from jerakeen.models import (
    AuthorKind,
    CommandCaptureMeta,
    CommandOutput,
    HistoryCancelled,
    HistoryEnded,
    HistoryLagged,
    HistoryStarted,
    OutputChunk,
)

HISTORY_ID = UUID("00112233-4455-6677-8899-aabbccddeeff")


def event_common() -> dict[str, Any]:
    return {
        "id": HISTORY_ID,
        "timestamp": datetime.fromtimestamp(1.5, tz=UTC),
        "timestamp_ns": 1_500_000_000,
        "command": "pwd",
        "cwd": "/tmp",
        "session": "s",
        "hostname": "h",
        "author": "a",
        "author_kind": AuthorKind.USER,
        "intent": "i",
        "shell": "zsh",
    }


def command_output(text: str = "hello", *, truncated: bool = False) -> CommandOutput:
    return CommandOutput(
        text=text,
        total_bytes=len(text.encode()),
        total_lines=max(1, len(text.splitlines())),
        chunks=(OutputChunk(start_line=0, end_line=0, content=text),),
        truncated=truncated,
        meta=CommandCaptureMeta(observed_bytes=9, terminal_width=120, terminal_height=40),
    )


class CliOutputTests(unittest.TestCase):
    def test_format_duration_all_units(self) -> None:
        cases = {
            0: "-",
            999: "999ns",
            1_000: "1.0us",
            999_999: "1000.0us",
            1_000_000: "1.0ms",
            999_999_999: "1000.0ms",
            1_000_000_000: "1.000s",
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                assert _cli_output.format_duration(value) == expected

    def test_event_to_dict_all_tail_event_kinds(self) -> None:
        started = _cli_output.event_to_dict(HistoryStarted(**event_common()))
        assert started["event"] == "started"
        assert started["id"] == str(HISTORY_ID)
        assert started["author_kind"] == "user"

        ended = _cli_output.event_to_dict(
            HistoryEnded(**event_common(), exit_code=7, duration_ns=123)
        )
        assert ended["event"] == "ended"
        assert ended["exit"] == 7
        assert ended["duration_ns"] == 123

        cancelled = _cli_output.event_to_dict(HistoryCancelled(**event_common()))
        assert cancelled["event"] == "cancelled"

        lagged = _cli_output.event_to_dict(HistoryLagged(dropped=4))
        assert lagged == {"event": "lagged", "dropped": 4}

    def test_captured_output_to_dict_includes_protocol3_metadata(self) -> None:
        result = _cli_output._captured_output_to_dict(command_output(truncated=True))
        assert result == {
            "output": "hello",
            "total_bytes": 5,
            "total_lines": 1,
            "output_truncated": True,
            "output_observed_bytes": 9,
            "terminal_width": 120,
            "terminal_height": 40,
        }

    def test_print_human_handles_lag_notification(self) -> None:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            _cli_output.print_human({"event": "lagged", "dropped": 11}, include_output=False)
        assert buffer.getvalue().strip() == "LAGGED  dropped=11 events"


class FakeHistory:
    def __init__(self, events, output: CommandOutput | None = None, error: Exception | None = None):
        self.events = events
        self.result = output
        self.error = error
        self.output_ids: list[UUID] = []

    async def tail(self):
        for event in self.events:
            yield event

    async def output(self, history_id: UUID) -> CommandOutput | None:
        self.output_ids.append(history_id)
        if self.error is not None:
            raise self.error
        return self.result


class FakeAtuin:
    def __init__(self, history: FakeHistory) -> None:
        self.description = "/tmp/atuin.sock"
        self.history = history

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        return None

    async def status(self):
        class Status:
            version = "18.23.0"
            protocol = 3
            pid = 123
            healthy = True

        return Status()


class CliRunTests(unittest.IsolatedAsyncioTestCase):
    def _ended(self) -> HistoryEnded:
        return HistoryEnded(**event_common(), exit_code=0, duration_ns=10)

    async def test_run_json_fetches_output_through_history_service(self) -> None:
        history = FakeHistory([self._ended()], command_output("ok"))
        client = FakeAtuin(history)
        buffer = io.StringIO()
        with (
            patch("jerakeen._cli_output.Atuin.connect", return_value=client),
            contextlib.redirect_stdout(buffer),
        ):
            await _cli_output.run(
                socket=None,
                tcp=None,
                output=True,
                json_output=True,
                connect_timeout=1,
            )
        payload = json.loads(buffer.getvalue())
        assert payload["event"] == "ended"
        assert payload["captured_output"]["output"] == "ok"
        assert history.output_ids == [HISTORY_ID]

    async def test_run_records_output_error_without_losing_event(self) -> None:
        history = FakeHistory([self._ended()], error=AtuinProtocolError("bad output"))
        client = FakeAtuin(history)
        buffer = io.StringIO()
        with (
            patch("jerakeen._cli_output.Atuin.connect", return_value=client),
            contextlib.redirect_stdout(buffer),
        ):
            await _cli_output.run(
                socket=None,
                tcp=None,
                output=True,
                json_output=True,
                connect_timeout=1,
            )
        payload = json.loads(buffer.getvalue())
        assert payload["captured_output_error"] == "bad output"


if __name__ == "__main__":
    unittest.main()
