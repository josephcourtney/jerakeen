from __future__ import annotations

import argparse
import asyncio
import sys

from jerakeen._cli_output import run
from jerakeen.exceptions import AtuinError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dump live activity from Atuin's local gRPC daemon.")
    endpoint = parser.add_mutually_exclusive_group()
    endpoint.add_argument(
        "--socket",
        help="Unix socket path. Useful when daemon.socket_path is customized.",
    )
    endpoint.add_argument(
        "--tcp",
        help="TCP target, e.g. 127.0.0.1:8889 (mainly for Windows).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit one JSON object per event.",
    )
    parser.add_argument(
        "--output",
        action="store_true",
        help="On END events, query Semantic.CommandOutput for captured output.",
    )
    parser.add_argument(
        "--connect-timeout",
        type=float,
        default=5.0,
        help="Seconds to wait for the daemon connection (default: 5).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        asyncio.run(
            run(
                socket=args.socket,
                tcp=args.tcp,
                output=args.output,
                json_output=args.json,
                connect_timeout=args.connect_timeout,
            )
        )
    except KeyboardInterrupt:
        pass
    except (AtuinError, FileNotFoundError) as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
