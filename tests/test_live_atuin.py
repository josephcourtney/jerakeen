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
    async def test_live_daemon_protocol3_status_search_and_output_contract(self) -> None:
        """Exercise a real local Atuin 18.23 daemon without mutating user history."""

        async with connect(rpc_timeout=30.0) as atuin:
            status = await atuin.status()
            assert status.healthy
            assert status.version == atuin.version
            assert status.protocol == atuin.protocol == 3
            assert atuin.compatibility.compatible

            result = await atuin.search.query("", filter_mode=FilterMode.GLOBAL)
            assert all(isinstance(history_id, UUID) for history_id in result.ids)
            if result.ids:
                output = await atuin.history.output(result.ids[0])
                if output is not None:
                    assert output.total_bytes >= 0
                    assert output.total_lines >= 0
                    assert output.meta.observed_bytes >= 0
