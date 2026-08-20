from __future__ import annotations

from pathlib import Path

import pytest

from jerakeen.compatibility import SUPPORTED_PROTOCOLS, VENDORED_ATUIN_VERSION, assess_compatibility
from jerakeen.exceptions import AtuinCompatibilityError
from jerakeen.models import DaemonStatus


def status(protocol: int) -> DaemonStatus:
    return DaemonStatus(healthy=True, version="18.19.0", pid=1, protocol=protocol)


def test_vendored_protocol_metadata_matches_snapshot() -> None:
    vendored_file = Path(__file__).parents[1] / "proto" / "atuin" / "VERSION"
    assert vendored_file.read_text(encoding="utf-8").strip() == VENDORED_ATUIN_VERSION
    assert VENDORED_ATUIN_VERSION == "18.19.0"
    assert SUPPORTED_PROTOCOLS == (1,)
    compatibility = assess_compatibility(status(1))
    assert compatibility.compatible
    compatibility.require()


def test_incompatible_protocol_is_explicit() -> None:
    compatibility = assess_compatibility(status(2))
    assert not compatibility.compatible
    with pytest.raises(AtuinCompatibilityError, match="protocol 2"):
        compatibility.require()
