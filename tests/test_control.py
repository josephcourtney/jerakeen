from __future__ import annotations

import unittest

from jerakeen._proto import control_pb2
from jerakeen.control import ControlClient


class FakeControlStub:
    def __init__(self) -> None:
        self.requests: list[control_pb2.SendEventRequest] = []

    async def SendEvent(
        self, request: control_pb2.SendEventRequest, *, timeout: float | None = None
    ) -> control_pb2.SendEventResponse:
        self.requests.append(request)
        return control_pb2.SendEventResponse()


class ControlTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.stub = FakeControlStub()
        self.client = ControlClient(self.stub)

    async def test_all_control_events(self) -> None:
        await self.client.force_sync()
        await self.client.reload_settings()
        await self.client.history_pruned()
        await self.client.history_deleted(["a", "b"])
        await self.client.history_rebuilt()
        await self.client.shutdown()

        assert [request.WhichOneof("event") for request in self.stub.requests] == [
            "force_sync",
            "settings_reloaded",
            "history_pruned",
            "history_deleted",
            "history_rebuilt",
            "shutdown",
        ]
        assert list(self.stub.requests[3].history_deleted.ids) == ["a", "b"]

    async def test_history_deleted_accepts_any_iterable(self) -> None:
        await self.client.history_deleted(value for value in ["one", "two"])
        assert list(self.stub.requests[0].history_deleted.ids) == ["one", "two"]


if __name__ == "__main__":
    unittest.main()
