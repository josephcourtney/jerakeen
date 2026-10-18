from __future__ import annotations

from pathlib import Path

import pytest

from jerakeen.compatibility import SUPPORTED_PROTOCOLS, VENDORED_ATUIN_VERSION, assess_compatibility
from jerakeen.exceptions import AtuinCompatibilityError
from jerakeen.models import DaemonStatus


def status(version: str, protocol: int | None = None) -> DaemonStatus:
    return DaemonStatus(healthy=True, version=version, pid=1, protocol=protocol)


def test_vendored_build_metadata_matches_snapshot() -> None:
    vendored_file = Path(__file__).parents[1] / "proto" / "atuin" / "VERSION"
    assert vendored_file.read_text(encoding="utf-8").strip() == VENDORED_ATUIN_VERSION
    assert VENDORED_ATUIN_VERSION == "18.24.1"
    assert SUPPORTED_PROTOCOLS == ()
    compatibility = assess_compatibility(status("18.24.1"))
    assert compatibility.compatible
    compatibility.require()


@pytest.mark.parametrize(
    ("version", "protocol"),
    [("18.23.0", 3), ("18.24.0", 5), ("18.24.0", None), ("18.24.2", None), ("18.24.1", 5)],
)
def test_old_or_mismatched_daemons_are_rejected(version: str, protocol: int | None) -> None:
    compatibility = assess_compatibility(status(version, protocol))
    assert not compatibility.compatible
    with pytest.raises(AtuinCompatibilityError, match="incompatible"):
        compatibility.require()
