from __future__ import annotations

import unittest
from typing import TYPE_CHECKING

import pytest

from jerakeen._proto import semantic_pb2
from jerakeen.models import CommandCapture
from jerakeen.semantic import SemanticClient, _capture_to_proto, _output_range

if TYPE_CHECKING:
    from collections.abc import AsyncIterable


class FakeSemanticStub:
    def __init__(self) -> None:
        self.command_output_request: semantic_pb2.CommandOutputRequest | None = None
        self.command_output_reply = semantic_pb2.CommandOutputReply()
        self.recorded: list[semantic_pb2.CommandCapture] = []

    async def CommandOutput(
        self, request: semantic_pb2.CommandOutputRequest, *, timeout: float | None = None
    ) -> semantic_pb2.CommandOutputReply:
        self.command_output_request = request
        return self.command_output_reply

    async def RecordCommands(
        self, requests: AsyncIterable[semantic_pb2.CommandCapture], *, timeout: float | None = None
    ) -> semantic_pb2.RecordCommandsReply:
        async for request in requests:
            self.recorded.append(request)
        return semantic_pb2.RecordCommandsReply(accepted=len(self.recorded))


class SemanticTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.stub = FakeSemanticStub()
        self.client = SemanticClient(self.stub)

    async def test_output_reconstructs_text_from_lines_for_atuin_18_19(self) -> None:
        self.stub.command_output_reply = semantic_pb2.CommandOutputReply(
            found=True,
            output="",
            total_bytes=999,
            total_lines=50,
            lines=[
                semantic_pb2.OutputLine(line_number=2, content="line 2"),
                semantic_pb2.OutputLine(line_number=3, content="line 3"),
            ],
            output_truncated=True,
            output_observed_bytes=1234,
        )

        output = await self.client.output(
            "history-id",
            ranges=[(0, 10), slice(20, 30), slice(40, 50, 1)],
        )
        assert output is not None
        assert output.text == "line 2\nline 3"
        assert output.total_bytes == 999
        assert output.total_lines == 50
        assert [(line.line_number, line.content) for line in output.lines] == [
            (2, "line 2"),
            (3, "line 3"),
        ]
        assert output.truncated
        assert output.observed_bytes == 1234

        request = self.stub.command_output_request
        assert request is not None
        assert request.history_id == "history-id"
        assert [(value.start, value.end) for value in request.ranges] == [
            (0, 10),
            (20, 30),
            (40, 50),
        ]

    async def test_output_preserves_nonempty_output_field_for_compatibility(self) -> None:
        self.stub.command_output_reply = semantic_pb2.CommandOutputReply(
            found=True,
            output="legacy output",
            total_bytes=13,
            total_lines=1,
            lines=[semantic_pb2.OutputLine(line_number=1, content="line representation")],
        )

        output = await self.client.output("history-id")

        assert output is not None
        assert output.text == "legacy output"
        assert [(line.line_number, line.content) for line in output.lines] == [
            (1, "line representation")
        ]

    async def test_output_not_found_returns_none(self) -> None:
        self.stub.command_output_reply = semantic_pb2.CommandOutputReply(found=False)
        assert await self.client.output("missing") is None
        request = self.stub.command_output_request
        assert request is not None
        assert request.history_id == "missing"
        assert list(request.ranges) == []

    def test_output_range_tuple(self) -> None:
        message = _output_range((-5, 10))
        assert message.start == -5
        assert message.end == 10

    def test_output_range_rejects_slice_step(self) -> None:
        with pytest.raises(ValueError, match="do not support a step"):
            _output_range(slice(0, 10, 2))

    def test_output_range_requires_slice_bounds(self) -> None:
        for value in (slice(None, 10), slice(0, None)):
            with (
                self.subTest(value=value),
                pytest.raises(ValueError, match="require both start and stop"),
            ):
                _output_range(value)

    def test_capture_to_proto_preserves_all_optional_fields(self) -> None:
        message = _capture_to_proto(
            CommandCapture(
                prompt="$ ",
                command="pwd",
                output="/tmp",
                exit_code=7,
                history_id="history-id",
                session_id="session-id",
                output_truncated=True,
                output_observed_bytes=12345,
            )
        )
        assert message.prompt == "$ "
        assert message.command == "pwd"
        assert message.output == "/tmp"
        assert message.HasField("exit_code")
        assert message.exit_code == 7
        assert message.HasField("history_id")
        assert message.history_id == "history-id"
        assert message.HasField("session_id")
        assert message.session_id == "session-id"
        assert message.output_truncated
        assert message.output_observed_bytes == 12345

    def test_capture_to_proto_leaves_optional_fields_unset(self) -> None:
        message = _capture_to_proto(CommandCapture(prompt=">", command="pwd", output=""))
        assert not message.HasField("exit_code")
        assert not message.HasField("history_id")
        assert not message.HasField("session_id")

    async def test_record_commands_accepts_sync_iterable(self) -> None:
        accepted = await self.client.record_commands([
            CommandCapture(prompt=">", command="one", output="1"),
            CommandCapture(prompt=">", command="two", output="2", exit_code=0),
        ])
        assert accepted == 2
        assert [capture.command for capture in self.stub.recorded] == ["one", "two"]
        assert self.stub.recorded[1].HasField("exit_code")

    async def test_record_commands_accepts_async_iterable(self) -> None:
        async def captures():
            yield CommandCapture(prompt=">", command="one", output="1")
            yield CommandCapture(prompt=">", command="two", output="2")

        accepted = await self.client.record_commands(captures())
        assert accepted == 2
        assert [capture.command for capture in self.stub.recorded] == ["one", "two"]


if __name__ == "__main__":
    unittest.main()
