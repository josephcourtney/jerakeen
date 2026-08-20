from __future__ import annotations

import contextlib
import io
import unittest
from unittest.mock import AsyncMock, patch

import pytest

from jerakeen import cli
from jerakeen.exceptions import AtuinConnectionError


class CliTests(unittest.TestCase):
    def test_parse_args(self) -> None:
        with patch(
            "sys.argv",
            [
                "jerakeen",
                "--socket",
                "/tmp/atuin.sock",
                "--json",
                "--output",
                "--connect-timeout",
                "2.5",
            ],
        ):
            args = cli.parse_args()
        assert args.socket == "/tmp/atuin.sock"
        assert args.tcp is None
        assert args.json
        assert args.output
        assert args.connect_timeout == pytest.approx(2.5)

    def test_parse_args_rejects_socket_and_tcp_together(self) -> None:
        with (
            patch("sys.argv", ["jerakeen", "--socket", "/tmp/a", "--tcp", "127.0.0.1:1"]),
            contextlib.redirect_stderr(io.StringIO()),
            pytest.raises(SystemExit),
        ):
            cli.parse_args()

    def test_main_invokes_async_run(self) -> None:
        runner = AsyncMock()
        with (
            patch("sys.argv", ["jerakeen", "--tcp", "127.0.0.1:9999", "--json"]),
            patch("jerakeen.cli.run", runner),
        ):
            cli.main()
        runner.assert_awaited_once_with(
            socket=None,
            tcp="127.0.0.1:9999",
            output=False,
            json_output=True,
            connect_timeout=5.0,
        )

    def test_main_prints_atuin_error_and_exits_one(self) -> None:
        runner = AsyncMock(side_effect=AtuinConnectionError("daemon unavailable"))
        stderr = io.StringIO()
        with (
            patch("sys.argv", ["jerakeen"]),
            patch("jerakeen.cli.run", runner),
            contextlib.redirect_stderr(stderr),
            pytest.raises(SystemExit) as caught,
        ):
            cli.main()
        assert caught.value.code == 1
        assert "daemon unavailable" in stderr.getvalue()

    def test_main_swallows_keyboard_interrupt(self) -> None:
        runner = AsyncMock(side_effect=KeyboardInterrupt)
        with (
            patch("sys.argv", ["jerakeen"]),
            patch("jerakeen.cli.run", runner),
        ):
            assert cli.main() is None


if __name__ == "__main__":
    unittest.main()
