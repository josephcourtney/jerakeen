from __future__ import annotations

import json
import sys
from typing import NotRequired, TypedDict, cast

from jerakeen.client import Atuin
from jerakeen.exceptions import AtuinError
from jerakeen.models import (
    CommandOutput,
    HistoryCancelled,
    HistoryEnded,
    HistoryEvent,
    HistoryEventRecord,
    HistoryLagged,
)

NANO_TO_MICRO = 1_000
NANO_TO_MILLI = 1_000_000
NANO_TO_UNUM = 1_000_000_000


class CapturedOutputDict(TypedDict):
    output: str
    total_bytes: int
    total_lines: int
    output_truncated: bool
    output_observed_bytes: int
    terminal_width: int
    terminal_height: int


class EventDict(TypedDict):
    event: str
    timestamp: NotRequired[str]
    timestamp_ns: NotRequired[int]
    id: NotRequired[str]
    command: NotRequired[str]
    cwd: NotRequired[str]
    session: NotRequired[str]
    hostname: NotRequired[str]
    author: NotRequired[str | None]
    author_kind: NotRequired[str]
    intent: NotRequired[str | None]
    shell: NotRequired[str | None]
    exit: NotRequired[int | None]
    duration_ns: NotRequired[int | None]
    dropped: NotRequired[int]
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
        "output_observed_bytes": output.meta.observed_bytes,
        "terminal_width": output.meta.terminal_width,
        "terminal_height": output.meta.terminal_height,
    }


def event_to_dict(event: HistoryEventRecord) -> EventDict:
    if isinstance(event, HistoryLagged):
        return {"event": "lagged", "dropped": event.dropped}

    if isinstance(event, HistoryEnded):
        state = "ended"
        exit_code: int | None = event.exit_code
        duration_ns: int | None = event.duration_ns
    elif isinstance(event, HistoryCancelled):
        state = "cancelled"
        exit_code = None
        duration_ns = None
    else:
        state = "started"
        exit_code = None
        duration_ns = None

    history_event = cast("HistoryEvent", event)
    return {
        "event": state,
        "timestamp": history_event.timestamp.astimezone().isoformat(timespec="milliseconds"),
        "timestamp_ns": history_event.timestamp_ns,
        "id": str(history_event.id),
        "command": history_event.command,
        "cwd": history_event.cwd,
        "session": history_event.session,
        "hostname": history_event.hostname,
        "author": history_event.author,
        "author_kind": history_event.author_kind.value,
        "intent": history_event.intent,
        "shell": history_event.shell,
        "exit": exit_code,
        "duration_ns": duration_ns,
    }


def print_human(event: EventDict, *, include_output: bool) -> None:
    if event["event"] == "lagged":
        print(f"LAGGED  dropped={event['dropped']} events", flush=True)
        return

    state = event["event"].upper()
    time_part = event["timestamp"].split("T", 1)[-1]
    suffix = ""
    if event["event"] == "ended":
        suffix = f" exit={event['exit']} duration={format_duration(event['duration_ns'] or 0)}"

    meta: list[str] = []
    if event.get("shell"):
        meta.append(f"shell={event['shell']}")
    if event.get("author"):
        meta.append(f"author={event['author']}")
    if event.get("author_kind") and event["author_kind"] != "unspecified":
        meta.append(f"author_kind={event['author_kind']}")
    if event.get("intent"):
        meta.append(f"intent={event['intent']}")
    meta_part = f" [{' '.join(meta)}]" if meta else ""

    print(
        f"{time_part}  {state:<9} {event['cwd']}  $ {event['command']}{suffix}{meta_part}",
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
    rpc_timeout: float = 5.0,
) -> None:
    async with await Atuin.connect(
        socket=socket,
        tcp=tcp,
        timeout=connect_timeout,
        rpc_timeout=rpc_timeout,
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
                    captured = await atuin.history.output(history_event.id)
                    if captured is not None:
                        event["captured_output"] = _captured_output_to_dict(captured)
                except AtuinError as exc:
                    event["captured_output_error"] = str(exc)

            if json_output:
                print(json.dumps(event, ensure_ascii=False), flush=True)
            else:
                print_human(event, include_output=output)
