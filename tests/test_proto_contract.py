from __future__ import annotations

import unittest

from jerakeen._proto import control_pb2, history_pb2, search_pb2, semantic_pb2


class ProtoContractTests(unittest.TestCase):
    def test_history_messages_and_rpc_shapes(self) -> None:
        assert set(history_pb2.DESCRIPTOR.message_types_by_name) == {
            "StartHistoryRequest",
            "EndHistoryRequest",
            "CancelHistoryRequest",
            "StartHistoryReply",
            "EndHistoryReply",
            "CancelHistoryReply",
            "StatusRequest",
            "StatusReply",
            "ShutdownRequest",
            "ShutdownReply",
            "TailHistoryRequest",
            "HistoryEntry",
            "TailHistoryReply",
        }
        service = history_pb2.DESCRIPTOR.services_by_name["History"]
        assert {
            method.name: (method.client_streaming, method.server_streaming) for method in service.methods
        } == {
            "StartHistory": (False, False),
            "EndHistory": (False, False),
            "CancelHistory": (False, False),
            "TailHistory": (False, True),
            "Status": (False, False),
            "Shutdown": (False, False),
        }
        history_kinds = history_pb2.DESCRIPTOR.enum_types_by_name["HistoryEventKind"]
        assert set(history_kinds.values_by_name) == {
            "HISTORY_EVENT_KIND_UNSPECIFIED",
            "HISTORY_EVENT_KIND_STARTED",
            "HISTORY_EVENT_KIND_ENDED",
        }

    def test_semantic_messages_and_rpc_shapes(self) -> None:
        assert set(semantic_pb2.DESCRIPTOR.message_types_by_name) == {
            "CommandCapture",
            "RecordCommandsReply",
            "CommandOutputRequest",
            "OutputRange",
            "OutputLine",
            "CommandOutputReply",
        }
        service = semantic_pb2.DESCRIPTOR.services_by_name["Semantic"]
        assert {
            method.name: (method.client_streaming, method.server_streaming) for method in service.methods
        } == {"RecordCommands": (True, False), "CommandOutput": (False, False)}

    def test_search_messages_and_rpc_shapes(self) -> None:
        assert set(search_pb2.DESCRIPTOR.message_types_by_name) == {
            "SearchContext",
            "SearchRequest",
            "SearchResponse",
            "PrepareIndexRequest",
            "PrepareIndexResponse",
        }
        service = search_pb2.DESCRIPTOR.services_by_name["Search"]
        assert {
            method.name: (method.client_streaming, method.server_streaming) for method in service.methods
        } == {"Search": (True, True), "PrepareIndex": (False, False)}
        assert set(search_pb2.DESCRIPTOR.enum_types_by_name["FilterMode"].values_by_name) == {
            "GLOBAL",
            "HOST",
            "SESSION",
            "DIRECTORY",
            "WORKSPACE",
            "SESSION_PRELOAD",
        }

    def test_control_messages_rpc_and_oneof(self) -> None:
        assert set(control_pb2.DESCRIPTOR.message_types_by_name) == {
            "SendEventRequest",
            "SendEventResponse",
            "HistoryPrunedEvent",
            "HistoryRebuiltEvent",
            "HistoryDeletedEvent",
            "ForceSyncEvent",
            "SettingsReloadedEvent",
            "ShutdownEvent",
        }
        service = control_pb2.DESCRIPTOR.services_by_name["Control"]
        assert {
            method.name: (method.client_streaming, method.server_streaming) for method in service.methods
        } == {"SendEvent": (False, False)}
        event = control_pb2.DESCRIPTOR.message_types_by_name["SendEventRequest"].oneofs_by_name["event"]
        assert {field.name for field in event.fields} == {
            "history_pruned",
            "history_deleted",
            "force_sync",
            "settings_reloaded",
            "shutdown",
            "history_rebuilt",
        }


class ProtoFieldContractTests(unittest.TestCase):
    def assert_fields(self, module, expected: dict[str, list[tuple[str, int]]]) -> None:
        actual = {
            name: [(field.name, field.number) for field in message.fields]
            for name, message in module.DESCRIPTOR.message_types_by_name.items()
        }
        assert actual == expected

    def test_every_history_message_field(self) -> None:
        self.assert_fields(
            history_pb2,
            {
                "StartHistoryRequest": [
                    ("timestamp", 1),
                    ("command", 2),
                    ("cwd", 3),
                    ("session", 4),
                    ("hostname", 5),
                    ("author", 6),
                    ("intent", 7),
                    ("shell", 8),
                ],
                "EndHistoryRequest": [("id", 1), ("exit", 2), ("duration", 3)],
                "CancelHistoryRequest": [("id", 1)],
                "StartHistoryReply": [("id", 1), ("version", 2), ("protocol", 3)],
                "EndHistoryReply": [("id", 1), ("idx", 2), ("version", 3), ("protocol", 4)],
                "CancelHistoryReply": [("version", 1), ("protocol", 2)],
                "StatusRequest": [],
                "StatusReply": [("healthy", 1), ("version", 2), ("pid", 3), ("protocol", 4)],
                "ShutdownRequest": [],
                "ShutdownReply": [("accepted", 1)],
                "TailHistoryRequest": [],
                "HistoryEntry": [
                    ("timestamp", 1),
                    ("id", 2),
                    ("command", 3),
                    ("cwd", 4),
                    ("session", 5),
                    ("hostname", 6),
                    ("author", 7),
                    ("intent", 8),
                    ("exit", 9),
                    ("duration", 10),
                    ("shell", 11),
                ],
                "TailHistoryReply": [("kind", 1), ("history", 2)],
            },
        )

    def test_every_semantic_message_field(self) -> None:
        self.assert_fields(
            semantic_pb2,
            {
                "CommandCapture": [
                    ("prompt", 1),
                    ("command", 2),
                    ("output", 3),
                    ("exit_code", 4),
                    ("history_id", 5),
                    ("session_id", 6),
                    ("output_truncated", 7),
                    ("output_observed_bytes", 8),
                ],
                "RecordCommandsReply": [("accepted", 1)],
                "CommandOutputRequest": [("history_id", 1), ("ranges", 2)],
                "OutputRange": [("start", 1), ("end", 2)],
                "OutputLine": [("line_number", 1), ("content", 2)],
                "CommandOutputReply": [
                    ("found", 1),
                    ("output", 2),
                    ("total_bytes", 3),
                    ("total_lines", 4),
                    ("lines", 5),
                    ("output_truncated", 6),
                    ("output_observed_bytes", 7),
                ],
            },
        )

    def test_every_search_message_field(self) -> None:
        self.assert_fields(
            search_pb2,
            {
                "SearchContext": [
                    ("session_id", 1),
                    ("cwd", 2),
                    ("hostname", 3),
                    ("host_id", 4),
                    ("git_root", 5),
                ],
                "SearchRequest": [
                    ("query", 1),
                    ("query_id", 2),
                    ("filter_mode", 3),
                    ("context", 4),
                    ("shells", 5),
                ],
                "SearchResponse": [("query_id", 1), ("ids", 2)],
                "PrepareIndexRequest": [("shells", 1)],
                "PrepareIndexResponse": [],
            },
        )

    def test_every_control_message_field(self) -> None:
        self.assert_fields(
            control_pb2,
            {
                "SendEventRequest": [
                    ("history_pruned", 1),
                    ("history_deleted", 2),
                    ("force_sync", 3),
                    ("settings_reloaded", 4),
                    ("shutdown", 5),
                    ("history_rebuilt", 6),
                ],
                "SendEventResponse": [],
                "HistoryPrunedEvent": [],
                "HistoryRebuiltEvent": [],
                "HistoryDeletedEvent": [("ids", 1)],
                "ForceSyncEvent": [],
                "SettingsReloadedEvent": [],
                "ShutdownEvent": [],
            },
        )


if __name__ == "__main__":
    unittest.main()
