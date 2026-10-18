from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from jerakeen.exceptions import AtuinCompatibilityError

if TYPE_CHECKING:
    from jerakeen.models import DaemonStatus

VENDORED_ATUIN_VERSION = "18.24.1"
# Numeric daemon protocol identifiers were removed in Atuin 18.24.1.
SUPPORTED_PROTOCOLS: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class Compatibility:
    """Compatibility with the exact vendored Atuin build and proto snapshot."""

    daemon_version: str
    daemon_protocol: int | None
    vendored_version: str = VENDORED_ATUIN_VERSION
    supported_protocols: tuple[int, ...] = SUPPORTED_PROTOCOLS

    @property
    def compatible(self) -> bool:
        return self.daemon_version == self.vendored_version and self.daemon_protocol is None

    def require(self) -> None:
        if not self.compatible:
            raise AtuinCompatibilityError(
                f"Atuin daemon version {self.daemon_version!r} is incompatible with "
                f"Jerakeen's {self.vendored_version!r} wire snapshot"
            )


def assess_compatibility(status: DaemonStatus) -> Compatibility:
    return Compatibility(
        daemon_version=status.version,
        daemon_protocol=status.protocol,
    )
