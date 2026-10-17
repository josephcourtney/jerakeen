from __future__ import annotations

import grpc
import pytest

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
    assert tuple(updated.metadata) == (("existing", "yes"), (BUILD_HEADER, "18.24.1"))
    assert updated.timeout == original.timeout


def test_existing_build_header_is_replaced() -> None:
    state = BuildMetadata()
    state.value = "18.24.1"
    original = grpc.aio.ClientCallDetails(
        "/history.History/GetCommandOutput", None,
        ((BUILD_HEADER, "wrong"), ("existing", "yes")), None, None
    )
    assert tuple(state.details(original).metadata) == (
        ("existing", "yes"), (BUILD_HEADER, "18.24.1")
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method",
    [
        "intercept_unary_unary",
        "intercept_unary_stream",
        "intercept_stream_unary",
        "intercept_stream_stream",
    ],
)
async def test_all_rpc_shapes_receive_build_header(method: str) -> None:
    state = BuildMetadata()
    state.value = "18.24.1"
    interceptor = BuildInterceptor(state)
    details = grpc.aio.ClientCallDetails("/test.Service/Call", None, None, None, None)
    seen = []

    async def continuation(call_details, request):
        seen.append(call_details)
        return "accepted"

    result = await getattr(interceptor, method)(continuation, details, object())
    assert result == "accepted"
    assert tuple(seen[0].metadata) == ((BUILD_HEADER, "18.24.1"),)
