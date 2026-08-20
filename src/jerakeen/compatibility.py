from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from jerakeen.exceptions import AtuinCompatibilityError

if TYPE_CHECKING:
    from jerakeen.models import DaemonStatus

VENDORED_ATUIN_VERSION = "18.19.0"
SUPPORTED_PROTOCOLS = (1,)


@dataclass(frozen=True, slots=True)
class Compatibility:
    """Compatibility assessment for the connected Atuin daemon."""

    daemon_version: str
    daemon_protocol: int
    vendored_version: str = VENDORED_ATUIN_VERSION
    supported_protocols: tuple[int, ...] = SUPPORTED_PROTOCOLS

    @property
    def compatible(self) -> bool:
        return self.daemon_protocol in self.supported_protocols

    def require(self) -> None:
        if not self.compatible:
            raise AtuinCompatibilityError(self.daemon_protocol, self.supported_protocols)


def assess_compatibility(status: DaemonStatus) -> Compatibility:
    """Assess a daemon status against the protocol supported by this build."""

    return Compatibility(
        daemon_version=status.version,
        daemon_protocol=status.protocol,
    )
