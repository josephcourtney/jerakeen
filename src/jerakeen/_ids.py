from __future__ import annotations

from uuid import UUID

from jerakeen._proto import common_pb2
from jerakeen.exceptions import AtuinProtocolError


def _uuid_from_message(value: common_pb2.Uuid, *, source: str) -> UUID:
    raw = bytes(value.value)
    if len(raw) != 16:
        msg = f"{source} contained {len(raw)} UUID bytes; expected 16"
        raise AtuinProtocolError(msg)
    return UUID(bytes=raw)


def history_id_to_proto(value: UUID | str) -> common_pb2.HistoryId:
    identifier = value if isinstance(value, UUID) else UUID(value)
    return common_pb2.HistoryId(uuid=common_pb2.Uuid(value=identifier.bytes))


def history_id_from_proto(value: common_pb2.HistoryId, *, source: str = "history id") -> UUID:
    if not value.HasField("uuid"):
        msg = f"{source} did not contain a UUID"
        raise AtuinProtocolError(msg)
    return _uuid_from_message(value.uuid, source=source)


def record_id_from_proto(value: common_pb2.RecordId, *, source: str = "record id") -> UUID:
    if not value.HasField("uuid"):
        msg = f"{source} did not contain a UUID"
        raise AtuinProtocolError(msg)
    return _uuid_from_message(value.uuid, source=source)
