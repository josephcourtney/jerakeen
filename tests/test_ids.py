from __future__ import annotations

from uuid import UUID

import pytest

from jerakeen._ids import history_id_from_proto, history_id_to_proto, record_id_from_proto
from jerakeen._proto import common_pb2
from jerakeen.exceptions import AtuinProtocolError


def test_history_id_roundtrip() -> None:
    expected = UUID("00112233-4455-6677-8899-aabbccddeeff")
    wire = history_id_to_proto(expected)
    assert bytes(wire.uuid.value) == expected.bytes
    assert history_id_from_proto(wire) == expected
    assert history_id_to_proto(str(expected)) == wire


def test_record_id_decodes_uuid() -> None:
    expected = UUID("ffeeddcc-bbaa-9988-7766-554433221100")
    wire = common_pb2.RecordId(uuid=common_pb2.Uuid(value=expected.bytes))
    assert record_id_from_proto(wire) == expected


def test_missing_history_uuid_is_protocol_error() -> None:
    with pytest.raises(AtuinProtocolError, match="did not contain a UUID"):
        history_id_from_proto(common_pb2.HistoryId())


def test_missing_record_uuid_is_protocol_error() -> None:
    with pytest.raises(AtuinProtocolError, match="did not contain a UUID"):
        record_id_from_proto(common_pb2.RecordId())


@pytest.mark.parametrize("size", [0, 1, 15, 17, 32])
def test_malformed_uuid_length_is_protocol_error(size: int) -> None:
    value = common_pb2.HistoryId(uuid=common_pb2.Uuid(value=b"x" * size))
    with pytest.raises(AtuinProtocolError, match=f"{size} UUID bytes; expected 16"):
        history_id_from_proto(value)
