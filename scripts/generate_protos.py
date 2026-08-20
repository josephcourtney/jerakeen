from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path

from grpc_tools import protoc

ROOT = Path(__file__).resolve().parents[1]
PROTO_DIR = ROOT / "proto" / "atuin"
OUT_DIR = ROOT / "src" / "jerakeen" / "_proto"
PROTO_NAMES = ("control", "history", "search", "semantic")
PROTOS = [PROTO_DIR / f"{name}.proto" for name in PROTO_NAMES]


def _fix_package_imports() -> None:
    """Make grpc_tools output use package-relative pb2 imports."""

    pattern = re.compile(r"^import (\w+_pb2) as (\w+__pb2)$", re.MULTILINE)
    for path in OUT_DIR.glob("*_pb2_grpc.py"):
        text = path.read_text(encoding="utf-8")
        text = pattern.sub(r"from . import \1 as \2", text)
        path.write_text(text, encoding="utf-8")

def _add_descriptor_typing() -> None:
    """Expose the module-level DESCRIPTOR in generated protobuf type stubs."""

    for path in OUT_DIR.glob("*_pb2.pyi"):
        text = path.read_text(encoding="utf-8")
        import_line = "from google.protobuf import descriptor as _descriptor\n"
        if import_line not in text:
            text = import_line + text
        marker = "DESCRIPTOR: _descriptor.FileDescriptor\n\n"
        if marker not in text:
            # Put DESCRIPTOR after imports and before generated declarations.
            lines = text.splitlines()
            index = 0
            while index < len(lines) and (
                lines[index].startswith("from ")
                or lines[index].startswith("import ")
                or not lines[index]
            ):
                index += 1
            lines[index:index] = ["", "DESCRIPTOR: _descriptor.FileDescriptor", ""]
            text = "\n".join(lines) + "\n"
        path.write_text(text, encoding="utf-8")


def _generate_grpc_type_stubs() -> None:
    """Generate lightweight async-client .pyi files for gRPC stubs."""

    sys.path.insert(0, str(OUT_DIR))
    try:
        for name in PROTO_NAMES:
            module = importlib.import_module(f"{name}_pb2")
            lines = [
                "from collections.abc import AsyncIterable, Awaitable",
                "import grpc",
                f"from . import {name}_pb2",
                "",
            ]
            for service in module.DESCRIPTOR.services_by_name.values():
                lines.append(f"class {service.name}Stub:")
                lines.append("    def __init__(self, channel: grpc.aio.Channel) -> None: ...")
                for method in service.methods:
                    input_type = f"{name}_pb2.{method.input_type.name}"
                    output_type = f"{name}_pb2.{method.output_type.name}"
                    if method.client_streaming:
                        arg = f"request_iterator: AsyncIterable[{input_type}]"
                    else:
                        arg = f"request: {input_type}"
                    if method.server_streaming:
                        result = f"AsyncIterable[{output_type}]"
                    else:
                        result = f"Awaitable[{output_type}]"
                    lines.append(
                        f"    def {method.name}(self, {arg}, *, "
                        f"timeout: float | None = ...) -> {result}: ..."
                    )
                lines.append("")
            (OUT_DIR / f"{name}_pb2_grpc.pyi").write_text(
                "\n".join(lines), encoding="utf-8"
            )
    finally:
        sys.path.pop(0)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "__init__.py").touch()
    rc = protoc.main(
        [
            "grpc_tools.protoc",
            f"-I{PROTO_DIR}",
            f"--python_out={OUT_DIR}",
            f"--pyi_out={OUT_DIR}",
            f"--grpc_python_out={OUT_DIR}",
            *(str(proto) for proto in PROTOS),
        ]
    )
    if rc != 0:
        return rc

    _fix_package_imports()
    _add_descriptor_typing()
    _generate_grpc_type_stubs()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

