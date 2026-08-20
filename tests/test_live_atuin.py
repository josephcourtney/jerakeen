from __future__ import annotations

import os
import unittest
from uuid import UUID

import pytest

from jerakeen import FilterMode, connect


@pytest.mark.integration
@unittest.skipUnless(
    os.environ.get("CATUIN_LIVE_TEST") == "1",
    "set CATUIN_LIVE_TEST=1 to exercise an installed Atuin daemon",
)
class LiveAtuinTests(unittest.IsolatedAsyncioTestCase):
    async def test_live_daemon_status_and_search_contract(self) -> None:
        """Exercise a real local daemon without mutating user history."""

        async with connect(rpc_timeout=30.0) as atuin:
            status = await atuin.status()
            assert status.healthy
            assert status.version == atuin.version
            assert status.protocol == atuin.protocol
            assert atuin.compatibility.compatible

            result = await atuin.search.query("", filter_mode=FilterMode.GLOBAL)
            assert all(isinstance(history_id, UUID) for history_id in result.ids)
            if result.ids:
                await atuin.semantic.output(str(result.ids[0]))
