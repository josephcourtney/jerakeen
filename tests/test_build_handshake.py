from __future__ import annotations

import unittest

import grpc

from jerakeen._transport import BUILD_HEADER, BuildInterceptor, BuildMetadata


def test_metadata_is_absent_before_handshake() -> None:
    state = BuildMetadata()
    original = grpc.aio.ClientCallDetails("/history.History/Status", 5, None, None, None)
    assert state.details(original) is original


def test_metadata_is_added_after_handshake() -> None:
    state = BuildMetadata()
    state.value = "18.24.1"
    original = grpc.aio.ClientCallDetails(
        "/history.History/GetCommandOutput", 5, (("existing", "yes"),), None, None
    )
    updated = state.details(original)
    assert updated.metadata is not None
    assert tuple(updated.metadata) == (("existing", "yes"), (BUILD_HEADER, "18.24.1"))
    assert updated.timeout == original.timeout


def test_existing_build_header_is_replaced() -> None:
    state = BuildMetadata()
    state.value = "18.24.1"
    original = grpc.aio.ClientCallDetails(
        "/history.History/GetCommandOutput", None, ((BUILD_HEADER, "wrong"), ("existing", "yes")), None, None
    )
    updated = state.details(original)
    assert updated.metadata is not None
    assert tuple(updated.metadata) == (("existing", "yes"), (BUILD_HEADER, "18.24.1"))


class InterceptorTests(unittest.IsolatedAsyncioTestCase):
    async def test_all_rpc_shapes_receive_build_header(self) -> None:
        state = BuildMetadata()
        state.value = "18.24.1"
        interceptor = BuildInterceptor(state)
        details = grpc.aio.ClientCallDetails("/test.Service/Call", None, None, None, None)

        async def continuation(call_details, request):
            return call_details

        for method in (
            "intercept_unary_unary",
            "intercept_unary_stream",
            "intercept_stream_unary",
            "intercept_stream_stream",
        ):
            with self.subTest(method=method):
                result = await getattr(interceptor, method)(continuation, details, object())
                assert result.metadata is not None
                assert tuple(result.metadata) == ((BUILD_HEADER, "18.24.1"),)
