"""Tests for ate_arch.comms — Communication analysis from JSONL transcripts."""

from __future__ import annotations

import json
from pathlib import Path

from ate_arch.comms import (
    CommunicationSummary,
    FileOperation,
    IndirectCollaboration,
    PeerMessage,
    RelayAnalysis,
    RelayEvent,
    TeammateMessage,
    analyze_relay_transparency,
    analyze_session,
    compute_relay_similarity,
    detect_indirect_collaboration,
    extract_file_operations,
    extract_peer_messages,
    extract_teammate_messages,
    infer_file_ops_from_messages,
    load_comms_summary,
    parse_jsonl_file,
    save_comms_summary,
)

# --- Model tests ---


class TestPeerMessage:
    def test_creation(self) -> None:
        msg = PeerMessage(
            sender="agent-1",
            recipient="agent-2",
            content_preview="Here are my findings about security.",
        )
        assert msg.sender == "agent-1"
        assert msg.recipient == "agent-2"
        assert msg.timestamp is None

    def test_with_timestamp(self) -> None:
        msg = PeerMessage(
            sender="agent-1",
            recipient="agent-2",
            content_preview="Test",
            timestamp="2026-01-15T10:30:00Z",
        )
        assert msg.timestamp == "2026-01-15T10:30:00Z"


class TestCommunicationSummary:
    def test_zero_messages(self) -> None:
        summary = CommunicationSummary(
            run_id="control-A-1",
            total_messages=0,
            peer_messages=[],
            unique_pairs=0,
        )
        assert summary.total_messages == 0
        assert summary.unique_pairs == 0

    def test_new_fields_default(self) -> None:
        """New Phase 6 fields default correctly."""
        summary = CommunicationSummary(
            run_id="control-A-1",
            total_messages=0,
            peer_messages=[],
            unique_pairs=0,
        )
        assert summary.file_collaborations == []
        assert summary.has_indirect_collaboration is False
        assert summary.relay_analysis is None


# --- parse_jsonl_file tests ---


class TestParseJsonlFile:
    def test_valid_jsonl(self, tmp_path: Path) -> None:
        """Parse a valid JSONL file with multiple entries."""
        jsonl = tmp_path / "transcript.jsonl"
        lines = [
            json.dumps({"type": "message", "content": "hello"}),
            json.dumps({"type": "tool_call", "name": "Bash"}),
            json.dumps({"type": "message", "content": "world"}),
        ]
        jsonl.write_text("\n".join(lines))
        entries = parse_jsonl_file(jsonl)
        assert len(entries) == 3
        assert entries[0]["type"] == "message"
        assert entries[1]["name"] == "Bash"

    def test_empty_file(self, tmp_path: Path) -> None:
        """Empty file returns empty list."""
        jsonl = tmp_path / "empty.jsonl"
        jsonl.write_text("")
        entries = parse_jsonl_file(jsonl)
        assert entries == []

    def test_skips_malformed_lines(self, tmp_path: Path) -> None:
        """Malformed lines are skipped, valid lines are kept."""
        jsonl = tmp_path / "mixed.jsonl"
        lines = [
            json.dumps({"type": "message"}),
            "this is not json",
            json.dumps({"type": "tool_call"}),
        ]
        jsonl.write_text("\n".join(lines))
        entries = parse_jsonl_file(jsonl)
        assert len(entries) == 2

    def test_blank_lines_skipped(self, tmp_path: Path) -> None:
        """Blank lines in JSONL are ignored."""
        jsonl = tmp_path / "blanks.jsonl"
        lines = [
            json.dumps({"type": "message"}),
            "",
            "  ",
            json.dumps({"type": "tool_call"}),
        ]
        jsonl.write_text("\n".join(lines))
        entries = parse_jsonl_file(jsonl)
        assert len(entries) == 2


# --- extract_peer_messages tests ---


class TestExtractPeerMessages:
    def test_nested_send_message(self) -> None:
        """SendMessage nested in assistant message content is extracted."""
        entries = [
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "SendMessage",
                            "input": {
                                "recipient": "agent-2",
                                "content": "I found that security requires AES-256.",
                            },
                        },
                    ],
                },
            },
        ]
        messages = extract_peer_messages(entries)
        assert len(messages) == 1
        assert messages[0].recipient == "agent-2"
        assert "AES-256" in messages[0].content_preview

    def test_nested_message_peer(self) -> None:
        """message_peer nested in assistant message content is extracted."""
        entries = [
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "message_peer",
                            "input": {
                                "recipient": "agent-1",
                                "message": "GDPR data residency required.",
                            },
                        },
                    ],
                },
            },
        ]
        messages = extract_peer_messages(entries)
        assert len(messages) == 1
        assert messages[0].recipient == "agent-1"
        assert "GDPR" in messages[0].content_preview

    def test_flat_tool_use_still_works(self) -> None:
        """Backward compat: flat tool_use entries are still extracted."""
        entries = [
            {
                "type": "tool_use",
                "name": "SendMessage",
                "input": {
                    "recipient": "agent-2",
                    "content": "Flat format message",
                },
            },
        ]
        messages = extract_peer_messages(entries)
        assert len(messages) == 1
        assert messages[0].recipient == "agent-2"

    def test_non_peer_tool_calls_filtered(self) -> None:
        """Non-communication tool calls are not extracted."""
        entries = [
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}},
                        {"type": "tool_use", "name": "Read", "input": {"path": "f.txt"}},
                    ],
                },
            },
        ]
        messages = extract_peer_messages(entries)
        assert messages == []

    def test_content_preview_truncated(self) -> None:
        """Content preview is truncated to 200 chars."""
        long_content = "x" * 500
        entries = [
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "SendMessage",
                            "input": {"recipient": "agent-2", "content": long_content},
                        },
                    ],
                },
            },
        ]
        messages = extract_peer_messages(entries)
        assert len(messages[0].content_preview) == 200

    def test_multiple_messages_across_entries(self) -> None:
        """Multiple peer messages across entries are all extracted."""
        entries = [
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "SendMessage",
                            "input": {"recipient": "agent-2", "content": "First"},
                        },
                        {
                            "type": "tool_use",
                            "name": "Bash",
                            "input": {"command": "echo hi"},
                        },
                    ],
                },
            },
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "SendMessage",
                            "input": {"recipient": "agent-1", "content": "Reply"},
                        },
                    ],
                },
            },
        ]
        messages = extract_peer_messages(entries)
        assert len(messages) == 2

    def test_entries_without_tool_use_ignored(self) -> None:
        """Entries with no tool_use content blocks are skipped."""
        entries = [
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "Thinking..."}],
                },
            },
            {"type": "user", "message": {"role": "user", "content": "hello"}},
        ]
        messages = extract_peer_messages(entries)
        assert messages == []

    def test_mixed_nested_and_string_content(self) -> None:
        """Entries where message.content is a string (not list) are handled."""
        entries = [
            {
                "type": "assistant",
                "message": {"role": "assistant", "content": "Just text, no tools"},
            },
        ]
        messages = extract_peer_messages(entries)
        assert messages == []


# --- analyze_session tests ---


class TestAnalyzeSession:
    def test_zero_communication(self, tmp_path: Path) -> None:
        """Session with no peer messages."""
        jsonl = tmp_path / "transcript.jsonl"
        lines = [
            json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "role": "assistant",
                        "content": [
                            {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}},
                        ],
                    },
                }
            ),
            json.dumps({"type": "user", "message": {"role": "user", "content": "hello"}}),
        ]
        jsonl.write_text("\n".join(lines))

        summary = analyze_session("control-A-1", jsonl)
        assert summary.run_id == "control-A-1"
        assert summary.total_messages == 0
        assert summary.peer_messages == []
        assert summary.unique_pairs == 0

    def test_multiple_peer_messages(self, tmp_path: Path) -> None:
        """Session with multiple peer messages from different pairs."""
        jsonl = tmp_path / "transcript.jsonl"

        def _msg(recipient: str, content: str) -> str:
            return json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "tool_use",
                                "name": "SendMessage",
                                "input": {"recipient": recipient, "content": content},
                            },
                        ],
                    },
                }
            )

        lines = [
            _msg("agent-2", "From agent 1"),
            _msg("agent-1", "Reply from agent 2"),
            _msg("agent-2", "Follow-up from agent 1"),
        ]
        jsonl.write_text("\n".join(lines))

        summary = analyze_session("treatment-A-1", jsonl)
        assert summary.total_messages == 3
        assert len(summary.peer_messages) == 3
        assert summary.unique_pairs == 2  # ->agent-2, ->agent-1

    def test_unique_pairs_counting(self, tmp_path: Path) -> None:
        """Unique pairs counts distinct sender->recipient combinations."""
        jsonl = tmp_path / "transcript.jsonl"

        def _msg(recipient: str, content: str) -> str:
            return json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "tool_use",
                                "name": "SendMessage",
                                "input": {"recipient": recipient, "content": content},
                            },
                        ],
                    },
                }
            )

        lines = [_msg("agent-2", "msg1"), _msg("agent-2", "msg2")]
        jsonl.write_text("\n".join(lines))

        summary = analyze_session("treatment-B-1", jsonl)
        assert summary.total_messages == 2
        # Both to same recipient from same (unknown) sender = 1 unique pair
        assert summary.unique_pairs == 1


# --- FileOperation model tests ---


class TestFileOperation:
    def test_creation(self) -> None:
        op = FileOperation(
            agent_id="coordinator",
            operation="Read",
            file_path="architecture.md",
        )
        assert op.agent_id == "coordinator"
        assert op.operation == "Read"
        assert op.file_path == "architecture.md"
        assert op.timestamp is None

    def test_with_timestamp(self) -> None:
        op = FileOperation(
            agent_id="abc123",
            operation="Edit",
            file_path="architecture.md",
            timestamp="2026-02-23T08:15:00Z",
        )
        assert op.timestamp == "2026-02-23T08:15:00Z"


# --- IndirectCollaboration model tests ---


class TestIndirectCollaboration:
    def test_single_agent_not_collaborative(self) -> None:
        ops = [
            FileOperation(
                agent_id="coordinator",
                operation="Write",
                file_path="arch.md",
            ),
            FileOperation(
                agent_id="coordinator",
                operation="Read",
                file_path="arch.md",
            ),
        ]
        collab = IndirectCollaboration(
            file_path="arch.md",
            operations=ops,
            agent_count=1,
            is_collaborative=False,
        )
        assert collab.agent_count == 1
        assert collab.is_collaborative is False

    def test_multi_agent_collaborative(self) -> None:
        ops = [
            FileOperation(
                agent_id="abc123",
                operation="Write",
                file_path="arch.md",
            ),
            FileOperation(
                agent_id="def456",
                operation="Read",
                file_path="arch.md",
            ),
        ]
        collab = IndirectCollaboration(
            file_path="arch.md",
            operations=ops,
            agent_count=2,
            is_collaborative=True,
        )
        assert collab.agent_count == 2
        assert collab.is_collaborative is True
        assert len(collab.operations) == 2


# --- RelayEvent model tests ---


class TestRelayEvent:
    def test_creation(self) -> None:
        event = RelayEvent(
            source_agent="agent-1",
            target_agent="agent-2",
            source_content="Agent 1 found GDPR requirements.",
            target_content="Agent 1 reports GDPR requirements.",
            similarity=0.85,
        )
        assert event.source_agent == "agent-1"
        assert event.target_agent == "agent-2"
        assert event.similarity == 0.85

    def test_similarity_range(self) -> None:
        """Similarity is a float in [0.0, 1.0]."""
        event = RelayEvent(
            source_agent="a1",
            target_agent="a2",
            source_content="x",
            target_content="x",
            similarity=1.0,
        )
        assert 0.0 <= event.similarity <= 1.0


# --- RelayAnalysis model tests ---


class TestRelayAnalysis:
    def test_empty(self) -> None:
        analysis = RelayAnalysis(
            relay_events=[],
            mean_similarity=0.0,
            relay_count=0,
        )
        assert analysis.relay_count == 0
        assert analysis.mean_similarity == 0.0

    def test_populated(self) -> None:
        events = [
            RelayEvent(
                source_agent="a1",
                target_agent="a2",
                source_content="report",
                target_content="relay",
                similarity=0.7,
            ),
            RelayEvent(
                source_agent="a2",
                target_agent="a1",
                source_content="findings",
                target_content="summary",
                similarity=0.5,
            ),
        ]
        analysis = RelayAnalysis(
            relay_events=events,
            mean_similarity=0.6,
            relay_count=2,
        )
        assert analysis.relay_count == 2
        assert analysis.mean_similarity == 0.6
        assert len(analysis.relay_events) == 2


# --- extract_file_operations tests ---


class TestExtractFileOperations:
    def test_coordinator_read(self) -> None:
        """Coordinator-level Read tool call is extracted."""
        entries = [
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Read",
                            "input": {"file_path": "/work/architecture.md"},
                        },
                    ],
                },
            },
        ]
        ops = extract_file_operations(entries)
        assert len(ops) == 1
        assert ops[0].agent_id == "coordinator"
        assert ops[0].operation == "Read"
        assert ops[0].file_path == "/work/architecture.md"

    def test_coordinator_write(self) -> None:
        """Coordinator-level Write tool call is extracted."""
        entries = [
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Write",
                            "input": {
                                "file_path": "/work/architecture.md",
                                "content": "# Architecture",
                            },
                        },
                    ],
                },
            },
        ]
        ops = extract_file_operations(entries)
        assert len(ops) == 1
        assert ops[0].operation == "Write"

    def test_coordinator_edit(self) -> None:
        """Coordinator-level Edit tool call is extracted."""
        entries = [
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Edit",
                            "input": {
                                "file_path": "/work/architecture.md",
                                "old_string": "old",
                                "new_string": "new",
                            },
                        },
                    ],
                },
            },
        ]
        ops = extract_file_operations(entries)
        assert len(ops) == 1
        assert ops[0].operation == "Edit"

    def test_subagent_via_progress_entry(self) -> None:
        """Subagent file operation from progress entry with agentId."""
        entries = [
            {
                "type": "progress",
                "data": {
                    "agentId": "abc123",
                    "message": {
                        "message": {
                            "role": "assistant",
                            "content": [
                                {
                                    "type": "tool_use",
                                    "name": "Read",
                                    "input": {"file_path": "/work/arch.md"},
                                },
                            ],
                        },
                    },
                },
            },
        ]
        ops = extract_file_operations(entries)
        assert len(ops) == 1
        assert ops[0].agent_id == "abc123"
        assert ops[0].operation == "Read"

    def test_progress_without_agent_id_defaults_coordinator(self) -> None:
        """Progress entry without agentId defaults to 'coordinator'."""
        entries = [
            {
                "type": "progress",
                "data": {
                    "message": {
                        "message": {
                            "role": "assistant",
                            "content": [
                                {
                                    "type": "tool_use",
                                    "name": "Write",
                                    "input": {"file_path": "/work/out.md"},
                                },
                            ],
                        },
                    },
                },
            },
        ]
        ops = extract_file_operations(entries)
        assert len(ops) == 1
        assert ops[0].agent_id == "coordinator"

    def test_non_file_tools_filtered(self) -> None:
        """Non-file tool calls (Bash, SendMessage, etc.) are not extracted."""
        entries = [
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}},
                        {
                            "type": "tool_use",
                            "name": "SendMessage",
                            "input": {"recipient": "a", "content": "hi"},
                        },
                    ],
                },
            },
        ]
        ops = extract_file_operations(entries)
        assert ops == []

    def test_target_files_filter(self) -> None:
        """target_files parameter filters by basename."""
        entries = [
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Read",
                            "input": {"file_path": "/work/architecture.md"},
                        },
                        {
                            "type": "tool_use",
                            "name": "Read",
                            "input": {"file_path": "/work/notes.md"},
                        },
                    ],
                },
            },
        ]
        ops = extract_file_operations(entries, target_files={"architecture.md"})
        assert len(ops) == 1
        assert "architecture.md" in ops[0].file_path

    def test_empty_entries(self) -> None:
        """Empty entries list returns empty operations list."""
        ops = extract_file_operations([])
        assert ops == []


# --- detect_indirect_collaboration tests ---


class TestDetectIndirectCollaboration:
    def test_single_agent(self) -> None:
        """Single agent on a file is not collaborative."""
        ops = [
            FileOperation(agent_id="coordinator", operation="Write", file_path="/a.md"),
            FileOperation(agent_id="coordinator", operation="Read", file_path="/a.md"),
        ]
        collabs = detect_indirect_collaboration(ops)
        assert len(collabs) == 1
        assert collabs[0].is_collaborative is False
        assert collabs[0].agent_count == 1

    def test_two_agents(self) -> None:
        """Two agents on a file is collaborative."""
        ops = [
            FileOperation(agent_id="abc", operation="Write", file_path="/a.md"),
            FileOperation(agent_id="def", operation="Read", file_path="/a.md"),
        ]
        collabs = detect_indirect_collaboration(ops)
        assert len(collabs) == 1
        assert collabs[0].is_collaborative is True
        assert collabs[0].agent_count == 2

    def test_multiple_files(self) -> None:
        """Each file gets its own IndirectCollaboration entry."""
        ops = [
            FileOperation(agent_id="abc", operation="Write", file_path="/a.md"),
            FileOperation(agent_id="def", operation="Read", file_path="/a.md"),
            FileOperation(agent_id="abc", operation="Write", file_path="/b.md"),
        ]
        collabs = detect_indirect_collaboration(ops)
        assert len(collabs) == 2
        paths = {c.file_path for c in collabs}
        assert paths == {"/a.md", "/b.md"}

    def test_empty(self) -> None:
        """Empty operations list returns empty."""
        collabs = detect_indirect_collaboration([])
        assert collabs == []

    def test_coordinator_plus_subagent(self) -> None:
        """Coordinator + subagent on same file is collaborative."""
        ops = [
            FileOperation(agent_id="coordinator", operation="Write", file_path="/a.md"),
            FileOperation(agent_id="abc123", operation="Read", file_path="/a.md"),
            FileOperation(agent_id="abc123", operation="Edit", file_path="/a.md"),
        ]
        collabs = detect_indirect_collaboration(ops)
        assert len(collabs) == 1
        assert collabs[0].is_collaborative is True
        assert collabs[0].agent_count == 2
        assert len(collabs[0].operations) == 3


# --- infer_file_ops_from_messages tests ---


class TestInferFileOpsFromMessages:
    def test_teammate_draft_detected(self) -> None:
        """Teammate mentioning 'draft complete' infers a Write."""
        entries = [
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": (
                        '<teammate-message teammate_id="agent-2" '
                        'color="green" '
                        'summary="Architecture.md draft complete">\n'
                        '{"type":"idle_notification","from":"agent-2",'
                        '"summary":"Architecture.md draft complete"}\n'
                        "</teammate-message>"
                    ),
                },
                "timestamp": "2026-02-23T08:21:00Z",
            },
        ]
        ops = infer_file_ops_from_messages(entries)
        assert len(ops) == 1
        assert ops[0].agent_id == "agent-2"
        assert ops[0].operation == "Write"
        assert "architecture.md" in ops[0].file_path.lower()

    def test_teammate_augmented_detected(self) -> None:
        """Teammate mentioning 'augmented' infers an Edit."""
        entries = [
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": (
                        '<teammate-message teammate_id="agent-1" '
                        'color="blue" '
                        'summary="Augmented architecture.md">\n'
                        '{"type":"idle_notification","from":"agent-1",'
                        '"summary":"Augmented architecture.md"}\n'
                        "</teammate-message>"
                    ),
                },
                "timestamp": "2026-02-23T08:24:00Z",
            },
        ]
        ops = infer_file_ops_from_messages(entries)
        assert len(ops) == 1
        assert ops[0].agent_id == "agent-1"
        assert ops[0].operation == "Edit"

    def test_teammate_review_detected(self) -> None:
        """Teammate mentioning 'review' infers a Read."""
        entries = [
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": (
                        '<teammate-message teammate_id="agent-2" '
                        'color="green" '
                        'summary="Reviewed architecture.md, all good">\n'
                        '{"type":"idle_notification","from":"agent-2",'
                        '"summary":"Reviewed architecture.md"}\n'
                        "</teammate-message>"
                    ),
                },
                "timestamp": "2026-02-23T08:25:00Z",
            },
        ]
        ops = infer_file_ops_from_messages(entries)
        assert len(ops) == 1
        assert ops[0].agent_id == "agent-2"
        assert ops[0].operation == "Read"

    def test_sendmessage_agent_wrote_detected(self) -> None:
        """Coordinator SendMessage 'Agent 2 has written' infers Write."""
        entries = [
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "SendMessage",
                            "input": {
                                "recipient": "agent-1",
                                "content": (
                                    "Agent 2 has already written architecture.md. Read it first."
                                ),
                            },
                        },
                    ],
                },
                "timestamp": "2026-02-23T08:22:00Z",
            },
        ]
        ops = infer_file_ops_from_messages(entries)
        assert len(ops) >= 1
        write_ops = [o for o in ops if o.operation == "Write"]
        assert len(write_ops) == 1
        assert write_ops[0].agent_id == "agent-2"

    def test_sendmessage_agent_augmented_detected(self) -> None:
        """Coordinator SendMessage 'Agent 1 has augmented' infers Edit."""
        entries = [
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "SendMessage",
                            "input": {
                                "recipient": "agent-2",
                                "content": ("Agent 1 has augmented your architecture.md draft."),
                            },
                        },
                    ],
                },
                "timestamp": "2026-02-23T08:25:30Z",
            },
        ]
        ops = infer_file_ops_from_messages(entries)
        assert len(ops) >= 1
        edit_ops = [o for o in ops if o.operation == "Edit"]
        assert len(edit_ops) == 1
        assert edit_ops[0].agent_id == "agent-1"

    def test_no_file_mentions_empty(self) -> None:
        """Messages without file operation keywords return empty."""
        entries = [
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": (
                        '<teammate-message teammate_id="agent-1" '
                        'color="blue" '
                        'summary="Completed stakeholder interviews">\n'
                        '{"type":"idle_notification","from":"agent-1",'
                        '"summary":"Completed stakeholder interviews"}\n'
                        "</teammate-message>"
                    ),
                },
                "timestamp": "2026-02-23T08:10:00Z",
            },
        ]
        ops = infer_file_ops_from_messages(entries)
        assert ops == []

    def test_shutdown_messages_ignored(self) -> None:
        """Shutdown teammate-messages are not parsed for file ops."""
        entries = [
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": (
                        '<teammate-message teammate_id="agent-1" '
                        'color="blue">\n'
                        '{"type":"shutdown_approved","from":"agent-1"}\n'
                        "</teammate-message>"
                    ),
                },
            },
        ]
        ops = infer_file_ops_from_messages(entries)
        assert ops == []

    def test_full_treatment_c1_pattern(self) -> None:
        """Full treatment-C-1 pattern: write → edit → review."""
        entries = [
            # agent-2 writes
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": (
                        '<teammate-message teammate_id="agent-2" '
                        'color="green" '
                        'summary="Architecture.md draft complete">\n'
                        '{"type":"idle_notification","from":"agent-2",'
                        '"summary":"Architecture.md draft complete"}\n'
                        "</teammate-message>"
                    ),
                },
                "timestamp": "2026-02-23T08:21:00Z",
            },
            # Coordinator tells agent-1 to read and edit
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "SendMessage",
                            "input": {
                                "recipient": "agent-1",
                                "content": (
                                    "Agent 2 has already written architecture.md. Read and augment."
                                ),
                            },
                        },
                    ],
                },
                "timestamp": "2026-02-23T08:22:00Z",
            },
            # agent-1 augments
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": (
                        '<teammate-message teammate_id="agent-1" '
                        'color="blue" '
                        'summary="Augmented architecture.md">\n'
                        '{"type":"idle_notification","from":"agent-1",'
                        '"summary":"Augmented architecture.md"}\n'
                        "</teammate-message>"
                    ),
                },
                "timestamp": "2026-02-23T08:24:00Z",
            },
            # agent-2 reviews
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": (
                        '<teammate-message teammate_id="agent-2" '
                        'color="green" '
                        'summary="Reviewed architecture.md, final">\n'
                        '{"type":"idle_notification","from":"agent-2",'
                        '"summary":"Reviewed architecture.md"}\n'
                        "</teammate-message>"
                    ),
                },
                "timestamp": "2026-02-23T08:25:00Z",
            },
        ]
        ops = infer_file_ops_from_messages(entries)
        # agent-2 Write, agent-2 Write (from SendMessage), agent-1 Edit
        # (from SendMessage), agent-1 Edit, agent-2 Read
        agents = {o.agent_id for o in ops}
        assert "agent-1" in agents
        assert "agent-2" in agents

        # Feed into detect_indirect_collaboration
        collabs = detect_indirect_collaboration(ops)
        collab_files = [c for c in collabs if c.is_collaborative]
        assert len(collab_files) >= 1


# --- TeammateMessage model tests ---


class TestTeammateMessage:
    def test_creation(self) -> None:
        msg = TeammateMessage(
            agent_id="agent-1",
            content="Found GDPR requirements and AES-256 encryption.",
            timestamp="2026-02-23T08:15:00Z",
        )
        assert msg.agent_id == "agent-1"
        assert "GDPR" in msg.content
        assert msg.timestamp == "2026-02-23T08:15:00Z"

    def test_defaults(self) -> None:
        msg = TeammateMessage(agent_id="agent-2", content="test")
        assert msg.timestamp is None


# --- extract_teammate_messages tests ---


class TestExtractTeammateMessages:
    def test_idle_with_summary(self) -> None:
        """Teammate idle_notification with summary is extracted."""
        entries = [
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": (
                        '<teammate-message teammate_id="agent-1" color="blue" '
                        'summary="Found GDPR and AES-256 requirements">\n'
                        '{"type":"idle_notification","from":"agent-1",'
                        '"timestamp":"2026-02-23T08:15:00Z","idleReason":"available",'
                        '"summary":"[to agent-1] Found GDPR and AES-256 requirements"}\n'
                        "</teammate-message>"
                    ),
                },
                "timestamp": "2026-02-23T08:15:00Z",
            },
        ]
        msgs = extract_teammate_messages(entries)
        assert len(msgs) == 1
        assert msgs[0].agent_id == "agent-1"
        assert "GDPR" in msgs[0].content

    def test_no_teammate_messages(self) -> None:
        """Non-teammate entries return empty list."""
        entries = [
            {
                "type": "assistant",
                "message": {"role": "assistant", "content": "text"},
            },
        ]
        msgs = extract_teammate_messages(entries)
        assert msgs == []

    def test_multiple_agents(self) -> None:
        """Teammate messages from different agents."""
        entries = [
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": (
                        '<teammate-message teammate_id="agent-1" color="blue" '
                        'summary="Agent 1 report">\n'
                        '{"type":"idle_notification","from":"agent-1",'
                        '"summary":"Agent 1 report"}\n'
                        "</teammate-message>"
                    ),
                },
                "timestamp": "2026-02-23T08:10:00Z",
            },
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": (
                        '<teammate-message teammate_id="agent-2" color="green" '
                        'summary="Agent 2 report">\n'
                        '{"type":"idle_notification","from":"agent-2",'
                        '"summary":"Agent 2 report"}\n'
                        "</teammate-message>"
                    ),
                },
                "timestamp": "2026-02-23T08:12:00Z",
            },
        ]
        msgs = extract_teammate_messages(entries)
        assert len(msgs) == 2
        agents = {m.agent_id for m in msgs}
        assert agents == {"agent-1", "agent-2"}

    def test_shutdown_filtered(self) -> None:
        """Shutdown/terminated messages are filtered out."""
        entries = [
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": (
                        '<teammate-message teammate_id="agent-1" color="blue">\n'
                        '{"type":"shutdown_approved","from":"agent-1"}\n'
                        "</teammate-message>"
                    ),
                },
                "timestamp": "2026-02-23T08:20:00Z",
            },
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": (
                        '<teammate-message teammate_id="agent-1" color="blue">\n'
                        '{"type":"teammate_terminated","message":"agent-1 has shut down."}\n'
                        "</teammate-message>"
                    ),
                },
                "timestamp": "2026-02-23T08:21:00Z",
            },
        ]
        msgs = extract_teammate_messages(entries)
        assert msgs == []

    def test_string_content_only(self) -> None:
        """Only string message.content is parsed (list content is ignored)."""
        entries = [
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": [{"type": "tool_result", "content": "something"}],
                },
            },
        ]
        msgs = extract_teammate_messages(entries)
        assert msgs == []


# --- compute_relay_similarity tests ---


class TestComputeRelaySimilarity:
    def test_identical(self) -> None:
        """Identical strings have similarity 1.0."""
        sim = compute_relay_similarity("hello world", "hello world")
        assert sim == 1.0

    def test_completely_different(self) -> None:
        """Completely different strings have low similarity."""
        sim = compute_relay_similarity("aaaaaaa", "zzzzzzz")
        assert sim < 0.2

    def test_partial_overlap(self) -> None:
        """Partially overlapping strings have mid-range similarity."""
        sim = compute_relay_similarity(
            "The agent found GDPR compliance requirements and AES-256 encryption.",
            "Agent reports GDPR compliance and AES-256 encryption needed.",
        )
        assert 0.3 < sim < 0.9


# --- analyze_relay_transparency tests ---


class TestAnalyzeRelayTransparency:
    def test_treatment_with_relay(self) -> None:
        """Temporally adjacent agent-X→lead + lead→agent-Y pair produces relay."""
        entries = [
            # Agent 1 reports to lead via teammate-message
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": (
                        '<teammate-message teammate_id="agent-1" color="blue" '
                        'summary="Found GDPR data residency and AES-256 encryption">\n'
                        '{"type":"idle_notification","from":"agent-1",'
                        '"summary":"Found GDPR data residency and AES-256 encryption"}\n'
                        "</teammate-message>"
                    ),
                },
                "timestamp": "2026-02-23T08:10:00Z",
            },
            # Lead relays to agent 2 via SendMessage
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "SendMessage",
                            "input": {
                                "recipient": "agent-2",
                                "content": (
                                    "Agent 1 found GDPR data residency "
                                    "and AES-256 encryption requirements. "
                                    "Please verify with your stakeholders."
                                ),
                            },
                        },
                    ],
                },
                "timestamp": "2026-02-23T08:10:30Z",
            },
        ]
        peer_msgs = [
            PeerMessage(
                sender="",
                recipient="agent-2",
                content_preview=(
                    "Agent 1 found GDPR data residency "
                    "and AES-256 encryption requirements. "
                    "Please verify with your stakeholders."
                ),
            ),
        ]
        analysis = analyze_relay_transparency(entries, peer_msgs)
        assert analysis is not None
        assert analysis.relay_count == 1
        assert analysis.relay_events[0].source_agent == "agent-1"
        assert analysis.relay_events[0].target_agent == "agent-2"
        assert 0.0 < analysis.mean_similarity <= 1.0

    def test_same_agent_not_relay(self) -> None:
        """Agent X→lead followed by lead→agent X is NOT a relay (X==Y)."""
        entries = [
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": (
                        '<teammate-message teammate_id="agent-1" color="blue" '
                        'summary="Completed all interviews with security stakeholders">\n'
                        '{"type":"idle_notification","from":"agent-1",'
                        '"summary":"Completed all interviews with security stakeholders"}\n'
                        "</teammate-message>"
                    ),
                },
                "timestamp": "2026-02-23T08:10:00Z",
            },
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "SendMessage",
                            "input": {
                                "recipient": "agent-1",
                                "content": "Great work. Now write the architecture document.",
                            },
                        },
                    ],
                },
                "timestamp": "2026-02-23T08:10:30Z",
            },
        ]
        peer_msgs = [
            PeerMessage(
                sender="",
                recipient="agent-1",
                content_preview="Great work. Now write the architecture document.",
            ),
        ]
        analysis = analyze_relay_transparency(entries, peer_msgs)
        # Should not produce a relay since source_agent == target_agent
        assert analysis is not None
        assert analysis.relay_count == 0

    def test_shutdown_messages_filtered(self) -> None:
        """Shutdown messages don't produce relays."""
        entries = [
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": (
                        '<teammate-message teammate_id="agent-1" color="blue" '
                        'summary="Done with all tasks">\n'
                        '{"type":"idle_notification","from":"agent-1",'
                        '"summary":"Done"}\n'
                        "</teammate-message>"
                    ),
                },
                "timestamp": "2026-02-23T08:20:00Z",
            },
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "SendMessage",
                            "input": {
                                "recipient": "agent-2",
                                "content": "Shutting down now.",
                            },
                        },
                    ],
                },
                "timestamp": "2026-02-23T08:20:30Z",
            },
        ]
        peer_msgs = [
            PeerMessage(
                sender="",
                recipient="agent-2",
                content_preview="Shutting down now.",
            ),
        ]
        analysis = analyze_relay_transparency(entries, peer_msgs)
        assert analysis is not None
        assert analysis.relay_count == 0

    def test_control_run_returns_none(self) -> None:
        """Control run with no SendMessages returns None."""
        entries = [
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}},
                    ],
                },
            },
        ]
        analysis = analyze_relay_transparency(entries, [])
        assert analysis is None


# --- Updated analyze_session tests ---


class TestAnalyzeSessionPhase6:
    def test_populates_file_collaborations(self, tmp_path: Path) -> None:
        """analyze_session populates file_collaborations from file ops."""
        jsonl = tmp_path / "transcript.jsonl"
        lines = [
            json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "tool_use",
                                "name": "Write",
                                "input": {"file_path": "/work/architecture.md"},
                            },
                        ],
                    },
                }
            ),
        ]
        jsonl.write_text("\n".join(lines))

        summary = analyze_session("control-A-2", jsonl)
        assert len(summary.file_collaborations) >= 1
        assert summary.has_indirect_collaboration is False  # Single agent

    def test_populates_relay_for_treatment(self, tmp_path: Path) -> None:
        """analyze_session populates relay_analysis when SendMessages present."""
        jsonl = tmp_path / "transcript.jsonl"
        lines = [
            # Agent 1 reports to lead
            json.dumps(
                {
                    "type": "user",
                    "message": {
                        "role": "user",
                        "content": (
                            '<teammate-message teammate_id="agent-1" color="blue" '
                            'summary="Discovered GDPR compliance and data residency needs">\n'
                            '{"type":"idle_notification","from":"agent-1",'
                            '"summary":"Discovered GDPR compliance and data residency needs"}\n'
                            "</teammate-message>"
                        ),
                    },
                    "timestamp": "2026-02-23T08:10:00Z",
                }
            ),
            # Lead relays to agent 2
            json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "tool_use",
                                "name": "SendMessage",
                                "input": {
                                    "recipient": "agent-2",
                                    "content": (
                                        "Agent 1 discovered GDPR compliance "
                                        "requirements and data residency needs. "
                                        "Please investigate with your stakeholders."
                                    ),
                                },
                            },
                        ],
                    },
                    "timestamp": "2026-02-23T08:10:30Z",
                }
            ),
        ]
        jsonl.write_text("\n".join(lines))

        summary = analyze_session("treatment-A-2", jsonl)
        assert summary.relay_analysis is not None
        assert summary.relay_analysis.relay_count >= 1

    def test_control_no_relay(self, tmp_path: Path) -> None:
        """Control run has no relay analysis (no SendMessages)."""
        jsonl = tmp_path / "transcript.jsonl"
        lines = [
            json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "role": "assistant",
                        "content": [
                            {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}},
                        ],
                    },
                }
            ),
        ]
        jsonl.write_text("\n".join(lines))

        summary = analyze_session("control-A-2", jsonl)
        assert summary.relay_analysis is None


# --- Comms persistence tests ---


class TestCommsPersistence:
    def test_save(self, tmp_path: Path) -> None:
        """save_comms_summary creates a JSON file."""
        summary = CommunicationSummary(
            run_id="control-A-1",
            total_messages=0,
            peer_messages=[],
            unique_pairs=0,
        )
        path = save_comms_summary(summary, tmp_path)
        assert path.exists()
        assert path.name == "control-A-1_comms.json"

    def test_round_trip(self, tmp_path: Path) -> None:
        """Save + load round-trips correctly."""
        summary = CommunicationSummary(
            run_id="treatment-C-1",
            total_messages=2,
            peer_messages=[
                PeerMessage(
                    sender="",
                    recipient="agent-2",
                    content_preview="hello",
                ),
            ],
            unique_pairs=1,
            has_indirect_collaboration=True,
            file_collaborations=[
                IndirectCollaboration(
                    file_path="/a.md",
                    operations=[
                        FileOperation(
                            agent_id="coord",
                            operation="Write",
                            file_path="/a.md",
                        ),
                    ],
                    agent_count=1,
                    is_collaborative=False,
                ),
            ],
        )
        save_comms_summary(summary, tmp_path)
        loaded = load_comms_summary("treatment-C-1", tmp_path)
        assert loaded.run_id == "treatment-C-1"
        assert loaded.total_messages == 2
        assert loaded.has_indirect_collaboration is True
        assert len(loaded.file_collaborations) == 1

    def test_load_nonexistent_raises(self, tmp_path: Path) -> None:
        """Loading a nonexistent comms file raises FileNotFoundError."""
        import pytest

        with pytest.raises(FileNotFoundError):
            load_comms_summary("nonexistent-run", tmp_path)
