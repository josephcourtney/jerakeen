from __future__ import annotations

from pathlib import Path

from google.protobuf.descriptor import FieldDescriptor

from jerakeen._proto import common_pb2, history_pb2, search_pb2

ROOT = Path(__file__).parents[1]


def rpc_shapes(service):
    return {method.name: (method.client_streaming, method.server_streaming) for method in service.methods}


def test_protocol_source_and_generated_file_sets_are_exact() -> None:
    assert {path.name for path in (ROOT / "proto" / "atuin").glob("*.proto")} == {
        "common.proto",
        "history.proto",
        "search.proto",
    }
    assert {
        path.name for path in (ROOT / "src" / "jerakeen" / "_proto").iterdir() if path.name != "__pycache__"
    } == {
        "__init__.py",
        "common_pb2.py",
        "common_pb2.pyi",
        "history_pb2.py",
        "history_pb2.pyi",
        "history_pb2_grpc.py",
        "history_pb2_grpc.pyi",
        "search_pb2.py",
        "search_pb2.pyi",
        "search_pb2_grpc.py",
        "search_pb2_grpc.pyi",
    }


def test_common_uuid_and_range_contract() -> None:
    messages = common_pb2.DESCRIPTOR.message_types_by_name
    assert set(messages) == {
        "Uuid",
        "HistoryId",
        "RecordId",
        "PyStyleIdxRange",
        "UnsignedIdxRange",
        "HighlightedText",
    }
    assert [(field.name, field.number) for field in messages["Uuid"].fields] == [("value", 1)]
    assert [(field.name, field.number) for field in messages["HistoryId"].fields] == [("uuid", 1)]
    assert [(field.name, field.number) for field in messages["RecordId"].fields] == [("uuid", 1)]
    assert [(field.name, field.number) for field in messages["PyStyleIdxRange"].fields] == [
        ("start", 1),
        ("end", 2),
    ]


def test_history_service_and_protocol3_shapes() -> None:
    service = history_pb2.DESCRIPTOR.services_by_name["History"]
    assert rpc_shapes(service) == {
        "StartHistory": (False, False),
        "EndHistory": (False, False),
        "CancelHistory": (False, False),
        "DeleteHistory": (True, False),
        "RebuildHistory": (False, False),
        "TailHistory": (False, True),
        "Status": (False, False),
        "Shutdown": (False, False),
        "RegisterCommandOutput": (False, False),
        "GetCommandOutput": (False, False),
    }

    messages = history_pb2.DESCRIPTOR.message_types_by_name
    start = messages["StartHistoryRequest"].fields_by_name
    assert start["timestamp"].type == FieldDescriptor.TYPE_INT64
    assert start["author_kind"].number == 9

    end = messages["EndHistoryRequest"].fields_by_name
    assert end["id"].message_type.full_name == "common.HistoryId"
    assert end["duration"].message_type.full_name == "google.protobuf.Duration"

    end_reply = messages["EndHistoryReply"].fields_by_name
    assert end_reply["record_id"].message_type.full_name == "common.RecordId"
    assert end_reply["record_idx"].number == 2

    tail = messages["TailHistoryReply"].oneofs_by_name["event"]
    assert {field.name for field in tail.fields} == {"started", "ended", "cancelled", "lagged"}

    output_request = messages["GetCommandOutputRequest"].fields_by_name
    assert output_request["id"].message_type.full_name == "common.HistoryId"
    assert output_request["line_ranges"].message_type.full_name == "common.PyStyleIdxRange"

    output_reply = messages["GetCommandOutputResponse"].fields_by_name
    assert output_reply["chunks"].message_type.full_name == "history.OutputChunk"
    assert output_reply["meta"].message_type.full_name == "history.CommandCaptureMeta"
    assert output_reply["truncated"].number == 5


def test_search_service_includes_captured_output_search() -> None:
    service = search_pb2.DESCRIPTOR.services_by_name["Search"]
    assert rpc_shapes(service) == {
        "Search": (True, True),
        "PrepareIndex": (False, False),
        "SearchCommandOutput": (False, True),
    }
    assert set(search_pb2.DESCRIPTOR.enum_types_by_name["FilterMode"].values_by_name) == {
        "GLOBAL",
        "HOST",
        "SESSION",
        "DIRECTORY",
        "WORKSPACE",
        "SESSION_PRELOAD",
    }
    match = search_pb2.DESCRIPTOR.message_types_by_name["OutputSearchMatch"].fields_by_name
    assert match["history_id"].message_type.full_name == "common.HistoryId"
    assert match["lines"].message_type.full_name == "search.OutputSearchLine"
    assert match["score"].number == 4
