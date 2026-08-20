from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import grpc
import pytest

from jerakeen._rpc import call
from jerakeen._transport import (
    ATUIN_AUTHORITY,
    create_channel,
    discover_target,
    unix_socket_candidates,
)
from jerakeen.client import Atuin
from jerakeen.exceptions import (
    AtuinConnectionError,
    AtuinNotFoundError,
    AtuinProtocolError,
    AtuinRpcError,
    AtuinTimeoutError,
    AtuinUnsupportedError,
    from_grpc_error,
)


def aio_error(code: grpc.StatusCode, details: str | None = "details") -> grpc.aio.AioRpcError:
    return grpc.aio.AioRpcError(
        code,
        grpc.aio.Metadata(),
        grpc.aio.Metadata(),
        details=details,
    )


class RpcTests(unittest.IsolatedAsyncioTestCase):
    def test_specific_grpc_error_mappings(self) -> None:
        expected = {
            grpc.StatusCode.DEADLINE_EXCEEDED: AtuinTimeoutError,
            grpc.StatusCode.NOT_FOUND: AtuinNotFoundError,
            grpc.StatusCode.UNIMPLEMENTED: AtuinUnsupportedError,
            grpc.StatusCode.UNAVAILABLE: AtuinConnectionError,
            grpc.StatusCode.INTERNAL: AtuinProtocolError,
        }
        for code, error_type in expected.items():
            with self.subTest(code=code):
                error = from_grpc_error(aio_error(code, "boom"))
                assert isinstance(error, error_type)
                assert str(error) == "boom"

    def test_generic_grpc_error_mapping_preserves_status(self) -> None:
        error = from_grpc_error(aio_error(grpc.StatusCode.PERMISSION_DENIED, "nope"))
        assert isinstance(error, AtuinRpcError)
        assert isinstance(error, AtuinRpcError)
        assert error.code == grpc.StatusCode.PERMISSION_DENIED
        assert error.details == "nope"
        assert str(error) == "PERMISSION_DENIED: nope"

    def test_grpc_error_without_details_uses_code_name(self) -> None:
        error = from_grpc_error(aio_error(grpc.StatusCode.NOT_FOUND, None))
        assert isinstance(error, AtuinNotFoundError)
        assert str(error) == "NOT_FOUND"

    async def test_call_returns_successful_result(self) -> None:
        async def success() -> int:
            return 42

        assert await call(success()) == 42

    async def test_call_translates_aio_rpc_error(self) -> None:
        async def failure() -> int:
            raise aio_error(grpc.StatusCode.UNAVAILABLE, "daemon gone")

        with pytest.raises(AtuinConnectionError, match="daemon gone"):
            await call(failure())


class TransportTests(unittest.IsolatedAsyncioTestCase):
    def test_unix_socket_candidates_respect_environment(self) -> None:
        with (
            patch.dict(
                "jerakeen._transport.os.environ",
                {
                    "TMPDIR": "/private/tmp",
                    "XDG_RUNTIME_DIR": "/run/user/123",
                    "XDG_DATA_HOME": "/data/home",
                },
                clear=True,
            ),
            patch("jerakeen._transport.os.getuid", return_value=123),
        ):
            assert unix_socket_candidates() == [
                Path("/private/tmp/atuin-123/atuin.sock"),
                Path("/run/user/123/atuin.sock"),
                Path("/data/home/atuin/atuin.sock"),
            ]

    def test_unix_socket_candidates_fall_back_to_home_data_dir(self) -> None:
        with (
            patch.dict("jerakeen._transport.os.environ", {"TMPDIR": "/tmp"}, clear=True),
            patch("jerakeen._transport.os.getuid", return_value=7),
            patch.object(Path, "home", return_value=Path("/home/tester")),
        ):
            assert unix_socket_candidates() == [
                Path("/tmp/atuin-7/atuin.sock"),
                Path("/home/tester/.local/share/atuin/atuin.sock"),
            ]

    def test_discover_target_prefers_explicit_tcp(self) -> None:
        assert discover_target("/ignored.sock", "127.0.0.1:9999") == (
            "127.0.0.1:9999",
            "127.0.0.1:9999",
        )

    def test_discover_target_explicit_unix_socket(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "atuin.sock"
            target, description = discover_target(path, None)
            assert target == f"unix://{path.resolve()}"
            assert description == str(path.resolve())

    def test_discover_target_windows_default(self) -> None:
        with patch("jerakeen._transport.os.name", "nt"):
            assert discover_target(None, None) == ("127.0.0.1:8889", "127.0.0.1:8889")

    def test_discover_target_uses_existing_candidate(self) -> None:
        candidate = Path("/tmp/test-atuin.sock")
        with (
            patch("jerakeen._transport.os.name", "posix"),
            patch("jerakeen._transport.unix_socket_candidates", return_value=[candidate]),
            patch.object(Path, "exists", return_value=True),
        ):
            assert discover_target(None, None) == (f"unix://{candidate}", str(candidate))

    def test_discover_target_reports_checked_candidates(self) -> None:
        candidates = [Path("/a.sock"), Path("/b.sock")]
        with (
            patch("jerakeen._transport.os.name", "posix"),
            patch("jerakeen._transport.unix_socket_candidates", return_value=candidates),
            patch.object(Path, "exists", return_value=False),
        ):
            with pytest.raises(FileNotFoundError, match="/a.sock") as caught:
                discover_target(None, None)
            assert "/b.sock" in str(caught.value)

    def test_create_channel_sets_atuin_authority(self) -> None:
        sentinel = Mock(spec=grpc.aio.Channel)
        with patch("jerakeen._transport.grpc.aio.insecure_channel", return_value=sentinel) as create:
            result = create_channel("unix:///tmp/atuin.sock")
        assert result is sentinel
        create.assert_called_once_with(
            "unix:///tmp/atuin.sock",
            options=(("grpc.default_authority", ATUIN_AUTHORITY),),
        )

    async def test_atuin_connect_timeout_closes_channel(self) -> None:
        channel = Mock()
        channel.close = AsyncMock()

        async def never_ready() -> None:
            await asyncio.Future()

        channel.channel_ready = never_ready
        with (
            patch("jerakeen.client.discover_target", return_value=("target", "description")),
            patch("jerakeen.client.create_channel", return_value=channel),
            pytest.raises(AtuinConnectionError, match="timed out"),
        ):
            await Atuin.connect(timeout=0.001)
        channel.close.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
