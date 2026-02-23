"""Communication analysis from JSONL transcripts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

# Tool names that indicate peer-to-peer communication
_PEER_TOOL_NAMES = {"SendMessage", "message_peer"}

# Max length for content preview
_PREVIEW_MAX = 200


class PeerMessage(BaseModel):
    """A single inter-agent message extracted from a transcript."""

    sender: str
    recipient: str
    content_preview: str
    timestamp: str | None = None


class CommunicationSummary(BaseModel):
    """Summary of inter-agent communication in a session."""

    run_id: str
    total_messages: int
    peer_messages: list[PeerMessage]
    unique_pairs: int


def parse_jsonl_file(path: Path) -> list[dict[str, Any]]:
    """Read a JSONL file, returning list of parsed dicts. Skips malformed lines."""
    entries: list[dict[str, Any]] = []
    text = path.read_text()
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def _iter_tool_uses(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Yield tool_use blocks from transcript entries.

    Handles two formats:
    - Nested: {"type": "assistant", "message": {"content": [{"type": "tool_use", ...}]}}
    - Flat (legacy/test): {"type": "tool_use", "name": "...", "input": {...}}
    """
    tool_uses: list[dict[str, Any]] = []
    for entry in entries:
        # Flat format
        if entry.get("type") == "tool_use":
            tool_uses.append(entry)
            continue
        # Nested format — dig into message.content[]
        message = entry.get("message", {})
        content = message.get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                tool_uses.append(block)
    return tool_uses


def extract_peer_messages(entries: list[dict[str, Any]]) -> list[PeerMessage]:
    """Extract peer-to-peer messages from transcript entries."""
    messages: list[PeerMessage] = []

    for tool_use in _iter_tool_uses(entries):
        name = tool_use.get("name", "")
        if name not in _PEER_TOOL_NAMES:
            continue

        tool_input = tool_use.get("input", {})
        recipient = tool_input.get("recipient", "")
        # SendMessage uses "content", message_peer uses "message"
        content = tool_input.get("content") or tool_input.get("message", "")

        # Truncate preview
        preview = content[:_PREVIEW_MAX] if content else ""

        # Sender is not always available — use empty string
        sender = tool_use.get("sender", "")

        messages.append(
            PeerMessage(
                sender=sender,
                recipient=recipient,
                content_preview=preview,
                timestamp=tool_use.get("timestamp"),
            )
        )

    return messages


def analyze_session(run_id: str, transcript_path: Path) -> CommunicationSummary:
    """Analyze a session transcript for inter-agent communication."""
    entries = parse_jsonl_file(transcript_path)
    peer_messages = extract_peer_messages(entries)

    # Count unique sender→recipient pairs
    pairs = {(m.sender, m.recipient) for m in peer_messages}

    return CommunicationSummary(
        run_id=run_id,
        total_messages=len(peer_messages),
        peer_messages=peer_messages,
        unique_pairs=len(pairs),
    )
