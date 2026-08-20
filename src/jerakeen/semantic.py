from __future__ import annotations

from collections.abc import AsyncIterable, Iterable
from typing import TYPE_CHECKING

from jerakeen._proto import semantic_pb2
from jerakeen._rpc import call
from jerakeen.models import CommandCapture, CommandOutput, OutputLine

if TYPE_CHECKING:
    from jerakeen._interfaces import SemanticStub


def _output_range(value: slice | tuple[int, int]) -> semantic_pb2.OutputRange:
    if isinstance(value, tuple):
        start, end = value
    else:
        if value.step not in {None, 1}:
            msg = "output range slices do not support a step"
            raise ValueError(msg)
        if value.start is None or value.stop is None:
            msg = "output range slices require both start and stop"
            raise ValueError(msg)
        start, end = value.start, value.stop
    return semantic_pb2.OutputRange(start=start, end=end)


def _capture_to_proto(capture: CommandCapture) -> semantic_pb2.CommandCapture:
    message = semantic_pb2.CommandCapture(
        prompt=capture.prompt,
        command=capture.command,
        output=capture.output,
        output_truncated=capture.output_truncated,
        output_observed_bytes=capture.output_observed_bytes,
    )
    if capture.exit_code is not None:
        message.exit_code = capture.exit_code
    if capture.history_id is not None:
        message.history_id = capture.history_id
    if capture.session_id is not None:
        message.session_id = capture.session_id
    return message


class SemanticClient:
    """Pythonic wrapper around Atuin's Semantic gRPC service."""

    def __init__(self, stub: SemanticStub) -> None:
        self._stub = stub

    async def output(
        self,
        history_id: str,
        *,
        ranges: Iterable[slice | tuple[int, int]] = (),
    ) -> CommandOutput | None:
        reply = await call(
            self._stub.CommandOutput(
                semantic_pb2.CommandOutputRequest(
                    history_id=history_id,
                    ranges=[_output_range(value) for value in ranges],
                )
            )
        )
        if not reply.found:
            return None

        lines = tuple(
            OutputLine(line_number=line.line_number, content=line.content) for line in reply.lines
        )
        text = reply.output or "\n".join(line.content for line in lines)

        return CommandOutput(
            text=text,
            total_bytes=reply.total_bytes,
            total_lines=reply.total_lines,
            lines=lines,
            truncated=reply.output_truncated,
            observed_bytes=reply.output_observed_bytes,
        )

    async def record_commands(
        self,
        captures: Iterable[CommandCapture] | AsyncIterable[CommandCapture],
    ) -> int:
        async def requests() -> AsyncIterable[semantic_pb2.CommandCapture]:
            if isinstance(captures, AsyncIterable):
                async for capture in captures:
                    yield _capture_to_proto(capture)
            else:
                for capture in captures:
                    yield _capture_to_proto(capture)

        reply = await call(self._stub.RecordCommands(requests()))
        return reply.accepted
