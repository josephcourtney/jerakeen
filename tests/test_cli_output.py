from __future__ import annotations

import contextlib
import io
import json
import unittest
from datetime import UTC, datetime
from unittest.mock import patch

from jerakeen import _cli_output
from jerakeen.exceptions import AtuinProtocolError
from jerakeen.models import CommandOutput, HistoryEnded, HistoryStarted, OutputLine


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

    def test_event_to_dict_started_and_ended(self) -> None:
        common = {
            "id": "id",
            "timestamp": datetime.fromtimestamp(1.5, tz=UTC),
            "timestamp_ns": 1_500_000_000,
            "command": "pwd",
            "cwd": "/tmp",
            "session": "s",
            "hostname": "h",
            "author": "a",
            "intent": "i",
            "shell": "zsh",
        }
        started = _cli_output.event_to_dict(HistoryStarted(**common))
        assert started["event"] == "started"
        assert started["exit"] is None
        assert started["duration_ns"] is None

        ended = _cli_output.event_to_dict(HistoryEnded(**common, exit_code=7, duration_ns=123))
        assert ended["event"] == "ended"
        assert ended["exit"] == 7
        assert ended["duration_ns"] == 123

    def test_captured_output_to_dict(self) -> None:
        result = _cli_output._captured_output_to_dict(
            CommandOutput(
                text="hello",
                total_bytes=5,
                total_lines=1,
                lines=(OutputLine(line_number=1, content="hello"),),
                truncated=True,
                observed_bytes=9,
            )
        )
        assert result == {
            "output": "hello",
            "total_bytes": 5,
            "total_lines": 1,
            "output_truncated": True,
            "output_observed_bytes": 9,
        }

    def test_print_human_with_metadata_and_captured_output(self) -> None:
        event: _cli_output.EventDict = {
            "event": "ended",
            "timestamp": "2026-08-19T15:29:59.932-04:00",
            "timestamp_ns": 1,
            "id": "id",
            "command": "pwd",
            "cwd": "/tmp",
            "session": "s",
            "hostname": "h",
            "author": "joseph",
            "intent": "inspect",
            "shell": "zsh",
            "exit": 0,
            "duration_ns": 66_000_000,
            "captured_output": {
                "output": "one\ntwo",
                "total_bytes": 7,
                "total_lines": 2,
                "output_truncated": True,
                "output_observed_bytes": 10,
            },
        }
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            _cli_output.print_human(event, include_output=True)
        text = buffer.getvalue()
        assert "ENDED" in text
        assert "exit=0 duration=66.0ms" in text
        assert "shell=zsh author=joseph intent=inspect" in text
        assert "one" in text
        assert "output truncated; observed 10 bytes" in text


class FakeHistory:
    def __init__(self, events):
        self.events = events

    async def tail(self):
        for event in self.events:
            yield event


class FakeSemantic:
    def __init__(self, output: CommandOutput | None = None, error: Exception | None = None) -> None:
        self.result = output
        self.error = error

    async def output(self, history_id: str) -> CommandOutput | None:
        if self.error is not None:
            raise self.error
        return self.result


class FakeAtuin:
    def __init__(self, events, semantic: FakeSemantic) -> None:
        self.description = "/tmp/atuin.sock"
        self.history = FakeHistory(events)
        self.semantic = semantic

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        return None

    async def status(self):
        class Status:
            version = "18.19.0"
            protocol = 1
            pid = 123
            healthy = True

        return Status()


class CliRunTests(unittest.IsolatedAsyncioTestCase):
    def _ended(self) -> HistoryEnded:
        return HistoryEnded(
            id="id",
            timestamp=datetime.fromtimestamp(1.5, tz=UTC),
            timestamp_ns=1_500_000_000,
            command="pwd",
            cwd="/tmp",
            session="s",
            hostname="h",
            author=None,
            intent=None,
            shell="zsh",
            exit_code=0,
            duration_ns=10,
        )

    async def test_run_json_with_captured_output(self) -> None:
        semantic = FakeSemantic(
            CommandOutput(
                text="ok",
                total_bytes=2,
                total_lines=1,
                lines=(),
                truncated=False,
                observed_bytes=2,
            )
        )
        client = FakeAtuin([self._ended()], semantic)
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

    async def test_run_records_semantic_error_in_event(self) -> None:
        client = FakeAtuin([self._ended()], FakeSemantic(error=AtuinProtocolError("bad output")))
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
