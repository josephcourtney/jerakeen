from __future__ import annotations

import json
import sys
from typing import NotRequired, TypedDict

from jerakeen.client import Atuin
from jerakeen.exceptions import AtuinError
from jerakeen.models import CommandOutput, HistoryEnded, HistoryEventRecord

NANO_TO_MICRO = 1_000
NANO_TO_MILLI = 1_000_000
NANO_TO_UNUM = 1_000_000_000


class CapturedOutputDict(TypedDict):
    output: str
    total_bytes: int
    total_lines: int
    output_truncated: bool
    output_observed_bytes: int


class EventDict(TypedDict):
    event: str
    timestamp: str
    timestamp_ns: int
    id: str
    command: str
    cwd: str
    session: str
    hostname: str
    author: str | None
    intent: str | None
    shell: str | None
    exit: int | None
    duration_ns: int | None
    captured_output: NotRequired[CapturedOutputDict]
    captured_output_error: NotRequired[str]


def format_duration(ns: int) -> str:
    if ns <= 0:
        return "-"
    if ns < NANO_TO_MICRO:
        return f"{ns}ns"
    if ns < NANO_TO_MILLI:
        return f"{ns / NANO_TO_MICRO:.1f}us"
    if ns < NANO_TO_UNUM:
        return f"{ns / NANO_TO_MILLI:.1f}ms"
    return f"{ns / NANO_TO_UNUM:.3f}s"


def _captured_output_to_dict(output: CommandOutput) -> CapturedOutputDict:
    return {
        "output": output.text,
        "total_bytes": output.total_bytes,
        "total_lines": output.total_lines,
        "output_truncated": output.truncated,
        "output_observed_bytes": output.observed_bytes,
    }


def event_to_dict(event: HistoryEventRecord) -> EventDict:
    ended = isinstance(event, HistoryEnded)
    return {
        "event": "ended" if ended else "started",
        "timestamp": event.timestamp.astimezone().isoformat(timespec="milliseconds"),
        "timestamp_ns": event.timestamp_ns,
        "id": event.id,
        "command": event.command,
        "cwd": event.cwd,
        "session": event.session,
        "hostname": event.hostname,
        "author": event.author,
        "intent": event.intent,
        "shell": event.shell,
        "exit": event.exit_code if ended else None,
        "duration_ns": event.duration_ns if ended else None,
    }


def print_human(event: EventDict, *, include_output: bool) -> None:
    state = event["event"].upper()
    time_part = event["timestamp"].split("T", 1)[-1]
    suffix = ""
    if event["event"] == "ended":
        suffix = f" exit={event['exit']} duration={format_duration(event['duration_ns'] or 0)}"

    meta: list[str] = []
    if event["shell"]:
        meta.append(f"shell={event['shell']}")
    if event["author"]:
        meta.append(f"author={event['author']}")
    if event["intent"]:
        meta.append(f"intent={event['intent']}")
    meta_part = f" [{' '.join(meta)}]" if meta else ""

    print(
        f"{time_part}  {state:<7} {event['cwd']}  $ {event['command']}{suffix}{meta_part}",
        flush=True,
    )

    captured = event.get("captured_output")
    if include_output and captured:
        print("    -- captured output --")
        for line in captured["output"].splitlines():
            print(f"    {line}")
        if captured["output_truncated"]:
            print(f"    [output truncated; observed {captured['output_observed_bytes']} bytes]")
        print("    ---------------------", flush=True)


async def run(
    *,
    socket: str | None,
    tcp: str | None,
    output: bool,
    json_output: bool,
    connect_timeout: float,
) -> None:
    async with await Atuin.connect(
        socket=socket,
        tcp=tcp,
        timeout=connect_timeout,
    ) as atuin:
        status = await atuin.status()
        if not json_output:
            print(
                f"connected: {atuin.description} "
                f"(atuin={status.version}, protocol={status.protocol}, "
                f"pid={status.pid}, healthy={status.healthy})",
                file=sys.stderr,
            )
            print("streaming History/TailHistory; Ctrl-C to stop", file=sys.stderr)

        async for history_event in atuin.history.tail():
            event = event_to_dict(history_event)
            if output and isinstance(history_event, HistoryEnded):
                try:
                    captured = await atuin.semantic.output(history_event.id)
                    if captured is not None:
                        event["captured_output"] = _captured_output_to_dict(captured)
                except AtuinError as exc:
                    event["captured_output_error"] = str(exc)

            if json_output:
                print(json.dumps(event, ensure_ascii=False), flush=True)
            else:
                print_human(event, include_output=output)
