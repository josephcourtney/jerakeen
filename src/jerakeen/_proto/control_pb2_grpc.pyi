from collections.abc import AsyncIterable, Awaitable
import grpc
from . import control_pb2

class ControlStub:
    def __init__(self, channel: grpc.aio.Channel) -> None: ...
    def SendEvent(self, request: control_pb2.SendEventRequest) -> Awaitable[control_pb2.SendEventResponse]: ...
