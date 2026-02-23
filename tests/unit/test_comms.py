"""Tests for ate_arch.comms — Communication analysis from JSONL transcripts."""

from __future__ import annotations

import json
from pathlib import Path

from ate_arch.comms import (
    CommunicationSummary,
    PeerMessage,
    analyze_session,
    extract_peer_messages,
    parse_jsonl_file,
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
    def test_send_message_with_peer_recipient(self) -> None:
        """SendMessage tool calls with peer recipients are extracted."""
        entries = [
            {
                "type": "tool_use",
                "name": "SendMessage",
                "input": {
                    "recipient": "agent-2",
                    "content": "I found that security requires AES-256 encryption.",
                },
            },
        ]
        messages = extract_peer_messages(entries)
        assert len(messages) == 1
        assert messages[0].recipient == "agent-2"
        assert "AES-256" in messages[0].content_preview

    def test_message_peer_tool(self) -> None:
        """message_peer tool calls are extracted."""
        entries = [
            {
                "type": "tool_use",
                "name": "message_peer",
                "input": {
                    "recipient": "agent-1",
                    "message": "Compliance requires GDPR data residency in EU region.",
                },
            },
        ]
        messages = extract_peer_messages(entries)
        assert len(messages) == 1
        assert messages[0].recipient == "agent-1"
        assert "GDPR" in messages[0].content_preview

    def test_non_peer_tool_calls_filtered(self) -> None:
        """Non-communication tool calls are not extracted."""
        entries = [
            {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}},
            {"type": "tool_use", "name": "Read", "input": {"path": "file.txt"}},
            {"type": "tool_use", "name": "Write", "input": {"path": "out.md"}},
            {
                "type": "tool_use",
                "name": "Task",
                "input": {"prompt": "Interview stakeholder"},
            },
        ]
        messages = extract_peer_messages(entries)
        assert messages == []

    def test_content_preview_truncated(self) -> None:
        """Content preview is truncated to 200 chars."""
        long_content = "x" * 500
        entries = [
            {
                "type": "tool_use",
                "name": "SendMessage",
                "input": {"recipient": "agent-2", "content": long_content},
            },
        ]
        messages = extract_peer_messages(entries)
        assert len(messages[0].content_preview) == 200

    def test_multiple_messages(self) -> None:
        """Multiple peer messages are all extracted."""
        entries = [
            {
                "type": "tool_use",
                "name": "SendMessage",
                "input": {"recipient": "agent-2", "content": "First message"},
            },
            {"type": "tool_use", "name": "Bash", "input": {"command": "echo hi"}},
            {
                "type": "tool_use",
                "name": "SendMessage",
                "input": {"recipient": "agent-1", "content": "Reply"},
            },
        ]
        messages = extract_peer_messages(entries)
        assert len(messages) == 2

    def test_entries_without_tool_use_type_ignored(self) -> None:
        """Entries that are not tool_use type are skipped."""
        entries = [
            {"type": "message", "role": "assistant", "content": "Thinking..."},
            {"type": "result", "output": "Done"},
        ]
        messages = extract_peer_messages(entries)
        assert messages == []


# --- analyze_session tests ---


class TestAnalyzeSession:
    def test_zero_communication(self, tmp_path: Path) -> None:
        """Session with no peer messages."""
        jsonl = tmp_path / "transcript.jsonl"
        lines = [
            json.dumps({"type": "tool_use", "name": "Bash", "input": {"command": "ls"}}),
            json.dumps({"type": "message", "role": "user", "content": "hello"}),
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
        lines = [
            json.dumps(
                {
                    "type": "tool_use",
                    "name": "SendMessage",
                    "input": {"recipient": "agent-2", "content": "From agent 1"},
                }
            ),
            json.dumps(
                {
                    "type": "tool_use",
                    "name": "SendMessage",
                    "input": {"recipient": "agent-1", "content": "Reply from agent 2"},
                }
            ),
            json.dumps(
                {
                    "type": "tool_use",
                    "name": "SendMessage",
                    "input": {"recipient": "agent-2", "content": "Follow-up from agent 1"},
                }
            ),
        ]
        jsonl.write_text("\n".join(lines))

        summary = analyze_session("treatment-A-1", jsonl)
        assert summary.total_messages == 3
        assert len(summary.peer_messages) == 3
        assert summary.unique_pairs == 2  # agent-?->agent-2, agent-?->agent-1

    def test_unique_pairs_counting(self, tmp_path: Path) -> None:
        """Unique pairs counts distinct sender→recipient combinations."""
        jsonl = tmp_path / "transcript.jsonl"
        lines = [
            json.dumps(
                {
                    "type": "tool_use",
                    "name": "SendMessage",
                    "input": {"recipient": "agent-2", "content": "msg1"},
                }
            ),
            json.dumps(
                {
                    "type": "tool_use",
                    "name": "SendMessage",
                    "input": {"recipient": "agent-2", "content": "msg2"},
                }
            ),
        ]
        jsonl.write_text("\n".join(lines))

        summary = analyze_session("treatment-B-1", jsonl)
        assert summary.total_messages == 2
        # Both to same recipient from same (unknown) sender = 1 unique pair
        assert summary.unique_pairs == 1
