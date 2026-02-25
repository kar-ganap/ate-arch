"""Communication analysis from JSONL transcripts."""

from __future__ import annotations

import json
import re
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


class FileOperation(BaseModel):
    """A file I/O operation from a transcript."""

    agent_id: str
    operation: str  # "Read", "Write", "Edit"
    file_path: str
    timestamp: str | None = None


class IndirectCollaboration(BaseModel):
    """Collaboration summary for a single shared file."""

    file_path: str
    operations: list[FileOperation]
    agent_count: int
    is_collaborative: bool  # agent_count > 1


class TeammateMessage(BaseModel):
    """An agent→lead message extracted from a <teammate-message> entry."""

    agent_id: str
    content: str
    timestamp: str | None = None


class RelayEvent(BaseModel):
    """A single information relay through the lead."""

    source_agent: str
    target_agent: str
    source_content: str
    target_content: str
    similarity: float  # 0.0 = complete rewrite, 1.0 = verbatim relay


class RelayAnalysis(BaseModel):
    """Summary of lead relay behavior for a run."""

    relay_events: list[RelayEvent]
    mean_similarity: float
    relay_count: int


class CommunicationSummary(BaseModel):
    """Summary of inter-agent communication in a session."""

    run_id: str
    total_messages: int
    peer_messages: list[PeerMessage]
    unique_pairs: int
    file_collaborations: list[IndirectCollaboration] = []
    has_indirect_collaboration: bool = False
    relay_analysis: RelayAnalysis | None = None


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


# Tool names that indicate file I/O operations
_FILE_TOOL_NAMES = {"Read", "Write", "Edit"}


def _iter_file_tool_uses(
    entries: list[dict[str, Any]],
) -> list[tuple[str, dict[str, Any]]]:
    """Extract (agent_id, tool_use_block) pairs for file I/O tools.

    Handles:
    - Coordinator-level: type=assistant → message.content[] → tool_use
    - Subagent-level: type=progress → data.message.message.content[] → tool_use
    """
    results: list[tuple[str, dict[str, Any]]] = []
    for entry in entries:
        entry_type = entry.get("type", "")

        if entry_type == "assistant":
            message = entry.get("message", {})
            content = message.get("content", [])
            if not isinstance(content, list):
                continue
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    if block.get("name") in _FILE_TOOL_NAMES:
                        results.append(("coordinator", block))

        elif entry_type == "progress":
            data = entry.get("data", {})
            agent_id = data.get("agentId", "coordinator")
            # Subagent messages nest deeper: data.message.message.content[]
            msg_wrapper = data.get("message", {})
            inner_msg = msg_wrapper.get("message", {})
            content = inner_msg.get("content", [])
            if not isinstance(content, list):
                continue
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    if block.get("name") in _FILE_TOOL_NAMES:
                        results.append((agent_id, block))

    return results


def extract_file_operations(
    entries: list[dict[str, Any]],
    *,
    target_files: set[str] | None = None,
) -> list[FileOperation]:
    """Extract file I/O operations from transcript entries."""
    operations: list[FileOperation] = []

    for agent_id, tool_use in _iter_file_tool_uses(entries):
        tool_input = tool_use.get("input", {})
        file_path = tool_input.get("file_path", "")
        if not file_path:
            continue

        # Apply target_files filter (by basename)
        if target_files is not None:
            basename = Path(file_path).name
            if basename not in target_files:
                continue

        operations.append(
            FileOperation(
                agent_id=agent_id,
                operation=tool_use["name"],
                file_path=file_path,
                timestamp=tool_use.get("timestamp"),
            )
        )

    return operations


def detect_indirect_collaboration(
    file_ops: list[FileOperation],
) -> list[IndirectCollaboration]:
    """Group file operations by path and detect multi-agent collaboration."""
    from collections import defaultdict

    by_file: dict[str, list[FileOperation]] = defaultdict(list)
    for op in file_ops:
        by_file[op.file_path].append(op)

    collaborations: list[IndirectCollaboration] = []
    for file_path, ops in sorted(by_file.items()):
        agents = {op.agent_id for op in ops}
        collaborations.append(
            IndirectCollaboration(
                file_path=file_path,
                operations=ops,
                agent_count=len(agents),
                is_collaborative=len(agents) > 1,
            )
        )

    return collaborations


# --- Heuristic file op inference from messages ---

# Keywords that indicate file write/create
_WRITE_KEYWORDS = {"draft complete", "written", "wrote", "created", "drafted"}
# Keywords that indicate file edit/augment
_EDIT_KEYWORDS = {"augmented", "edited", "updated", "modified", "added to"}
# Keywords that indicate file read/review
_READ_KEYWORDS = {"reviewed", "read", "verified", "checked", "approved"}

# Regex to extract agent reference from coordinator SendMessage content
# Matches "Agent 1 has written", "Agent 2 has augmented", etc.
_AGENT_REF_RE = re.compile(
    r"[Aa]gent[ -](\d+)\s+has\s+(?:already\s+)?(\w+)",
)


def _classify_file_op(text: str) -> str | None:
    """Classify text as a file operation type, or None if not file-related."""
    lower = text.lower()
    if "architecture" not in lower:
        return None
    for kw in _WRITE_KEYWORDS:
        if kw in lower:
            return "Write"
    for kw in _EDIT_KEYWORDS:
        if kw in lower:
            return "Edit"
    for kw in _READ_KEYWORDS:
        if kw in lower:
            return "Read"
    return None


def infer_file_ops_from_messages(
    entries: list[dict[str, Any]],
) -> list[FileOperation]:
    """Infer file operations from teammate-messages and SendMessages.

    Heuristic: parse message content for keywords indicating file
    operations on architecture.md, with agent attribution from
    teammate_id or agent references in coordinator messages.
    """
    operations: list[FileOperation] = []

    for entry in entries:
        entry_type = entry.get("type", "")
        timestamp = entry.get("timestamp")

        # Source 1: teammate-messages (agent→lead)
        if entry_type == "user":
            message = entry.get("message", {})
            content = message.get("content", "")
            if not isinstance(content, str):
                continue
            if "<teammate-message" not in content:
                continue

            match = _TEAMMATE_RE.search(content)
            if not match:
                continue

            agent_id = match.group(1)

            # Extract summary from inner JSON or XML attribute
            inner_start = content.find(">") + 1
            inner_end = content.find("</teammate-message>")
            if inner_end < 0:
                continue
            inner_text = content[inner_start:inner_end].strip()

            try:
                inner_json = json.loads(inner_text)
                if inner_json.get("type") in _SKIP_TEAMMATE_TYPES:
                    continue
                summary = inner_json.get("summary", "") or ""
            except json.JSONDecodeError:
                summary = inner_text[:_PREVIEW_MAX]

            if not summary:
                summary = match.group(2) or ""

            op_type = _classify_file_op(summary)
            if op_type:
                operations.append(
                    FileOperation(
                        agent_id=agent_id,
                        operation=op_type,
                        file_path="architecture.md",
                        timestamp=timestamp,
                    )
                )

        # Source 2: SendMessage (coordinator referencing agent actions)
        elif entry_type == "assistant":
            message = entry.get("message", {})
            msg_content = message.get("content", [])
            if not isinstance(msg_content, list):
                continue
            for block in msg_content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") != "tool_use":
                    continue
                if block.get("name") not in _PEER_TOOL_NAMES:
                    continue

                tool_input = block.get("input", {})
                send_content = tool_input.get("content") or tool_input.get("message", "")
                if not send_content:
                    continue

                # Look for "Agent N has written/augmented/..."
                agent_match = _AGENT_REF_RE.search(send_content)
                if not agent_match:
                    continue

                ref_agent = f"agent-{agent_match.group(1)}"
                verb = agent_match.group(2).lower()

                # Classify the verb
                op_type = None
                if verb in {"written", "wrote", "drafted", "created"}:
                    op_type = "Write"
                elif verb in {"augmented", "edited", "updated"}:
                    op_type = "Edit"
                elif verb in {"reviewed", "read", "verified"}:
                    op_type = "Read"

                if op_type and "architecture" in send_content.lower():
                    operations.append(
                        FileOperation(
                            agent_id=ref_agent,
                            operation=op_type,
                            file_path="architecture.md",
                            timestamp=timestamp,
                        )
                    )

    return operations


# Regex to extract teammate_id and summary from <teammate-message> XML
_TEAMMATE_RE = re.compile(
    r'<teammate-message\s+teammate_id="([^"]+)"[^>]*?'
    r'(?:summary="([^"]*)")?[^>]*>',
)

# Types we skip — these are not substantive agent→lead reports
_SKIP_TEAMMATE_TYPES = {"shutdown_approved", "teammate_terminated"}


def extract_teammate_messages(
    entries: list[dict[str, Any]],
) -> list[TeammateMessage]:
    """Extract agent→lead messages from <teammate-message> entries."""
    messages: list[TeammateMessage] = []

    for entry in entries:
        if entry.get("type") != "user":
            continue
        message = entry.get("message", {})
        content = message.get("content", "")
        if not isinstance(content, str):
            continue
        if "<teammate-message" not in content:
            continue

        # Parse XML attributes
        match = _TEAMMATE_RE.search(content)
        if not match:
            continue

        agent_id = match.group(1)

        # Try to parse the inner JSON to check type and get summary
        inner_start = content.find(">") + 1
        inner_end = content.find("</teammate-message>")
        if inner_end < 0:
            continue
        inner_text = content[inner_start:inner_end].strip()

        # Try JSON parse for structured messages
        try:
            inner_json = json.loads(inner_text)
            msg_type = inner_json.get("type", "")
            if msg_type in _SKIP_TEAMMATE_TYPES:
                continue
            # Use summary from JSON, fallback to XML attribute
            summary = inner_json.get("summary", "") or match.group(2) or ""
        except json.JSONDecodeError:
            # Raw markdown/text report — use the text itself
            summary = inner_text[:_PREVIEW_MAX]

        if not summary:
            # Fallback to XML summary attribute
            summary = match.group(2) or ""

        if not summary:
            continue

        messages.append(
            TeammateMessage(
                agent_id=agent_id,
                content=summary,
                timestamp=entry.get("timestamp"),
            )
        )

    return messages


def compute_relay_similarity(source: str, target: str) -> float:
    """Compute string similarity using difflib.SequenceMatcher."""
    import difflib

    return difflib.SequenceMatcher(None, source, target).ratio()


# Short/trivial messages that aren't substantive relays
_SHUTDOWN_PATTERNS = {
    "stop",
    "done",
    "you can stop",
    "shutdown",
    "finished",
    "complete",
    "shutting down",
    "shutting down now",
}


def _is_substantive(text: str) -> bool:
    """Check if a message is substantive (not a shutdown/ack)."""
    normalized = text.strip().lower().rstrip(".!?")
    return len(normalized) > 20 and normalized not in _SHUTDOWN_PATTERNS


def _build_chronological_events(
    entries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build chronological list of teammate→lead and lead→agent events.

    Each event is either:
      {"kind": "incoming", "agent_id": str, "content": str, "index": int}
      {"kind": "outgoing", "recipient": str, "content": str, "index": int}
    """
    events: list[dict[str, Any]] = []

    for i, entry in enumerate(entries):
        # Check for teammate-message (agent→lead)
        if entry.get("type") == "user":
            message = entry.get("message", {})
            content = message.get("content", "")
            if isinstance(content, str) and "<teammate-message" in content:
                match = _TEAMMATE_RE.search(content)
                if match:
                    agent_id = match.group(1)
                    # Extract summary
                    inner_start = content.find(">") + 1
                    inner_end = content.find("</teammate-message>")
                    if inner_end >= 0:
                        inner_text = content[inner_start:inner_end].strip()
                        try:
                            inner_json = json.loads(inner_text)
                            if inner_json.get("type") in _SKIP_TEAMMATE_TYPES:
                                continue
                            summary = inner_json.get("summary", "") or ""
                        except json.JSONDecodeError:
                            summary = inner_text[:_PREVIEW_MAX]
                        if summary and _is_substantive(summary):
                            events.append(
                                {
                                    "kind": "incoming",
                                    "agent_id": agent_id,
                                    "content": summary,
                                    "index": i,
                                }
                            )

        # Check for SendMessage (lead→agent)
        if entry.get("type") == "assistant":
            message = entry.get("message", {})
            msg_content = message.get("content", [])
            if not isinstance(msg_content, list):
                continue
            for block in msg_content:
                if (
                    isinstance(block, dict)
                    and block.get("type") == "tool_use"
                    and block.get("name") in _PEER_TOOL_NAMES
                ):
                    tool_input = block.get("input", {})
                    recipient = tool_input.get("recipient", "")
                    send_content = tool_input.get("content") or tool_input.get("message", "")
                    if send_content and _is_substantive(send_content):
                        events.append(
                            {
                                "kind": "outgoing",
                                "recipient": recipient,
                                "content": send_content[:_PREVIEW_MAX],
                                "index": i,
                            }
                        )

    return events


def analyze_relay_transparency(
    entries: list[dict[str, Any]],
    peer_messages: list[PeerMessage],
) -> RelayAnalysis | None:
    """Analyze how transparently the lead relays information between agents.

    Finds temporally adjacent pairs: (agent-X → lead) followed by
    (lead → agent-Y) where X ≠ Y. Computes similarity between the two.

    Returns None if no peer messages (control runs).
    """
    if not peer_messages:
        return None

    events = _build_chronological_events(entries)
    if not events:
        return RelayAnalysis(relay_events=[], mean_similarity=0.0, relay_count=0)

    # Find adjacent (incoming, outgoing) pairs with different agents
    relay_events: list[RelayEvent] = []
    i = 0
    while i < len(events) - 1:
        curr = events[i]
        nxt = events[i + 1]

        if (
            curr["kind"] == "incoming"
            and nxt["kind"] == "outgoing"
            and curr["agent_id"] != nxt["recipient"]
        ):
            similarity = compute_relay_similarity(
                curr["content"],
                nxt["content"],
            )
            relay_events.append(
                RelayEvent(
                    source_agent=curr["agent_id"],
                    target_agent=nxt["recipient"],
                    source_content=curr["content"][:_PREVIEW_MAX],
                    target_content=nxt["content"][:_PREVIEW_MAX],
                    similarity=similarity,
                )
            )
            i += 2  # Skip both events
        else:
            i += 1

    mean_sim = sum(e.similarity for e in relay_events) / len(relay_events) if relay_events else 0.0

    return RelayAnalysis(
        relay_events=relay_events,
        mean_similarity=round(mean_sim, 4),
        relay_count=len(relay_events),
    )


def analyze_session(run_id: str, transcript_path: Path) -> CommunicationSummary:
    """Analyze a session transcript for inter-agent communication."""
    entries = parse_jsonl_file(transcript_path)
    peer_messages = extract_peer_messages(entries)

    # Count unique sender→recipient pairs
    pairs = {(m.sender, m.recipient) for m in peer_messages}

    # Phase 6: indirect collaboration
    # Combine tool_use extraction with heuristic inference from messages
    file_ops = extract_file_operations(entries)
    inferred_ops = infer_file_ops_from_messages(entries)
    all_file_ops = file_ops + inferred_ops
    file_collabs = detect_indirect_collaboration(all_file_ops)
    has_indirect = any(c.is_collaborative for c in file_collabs)

    # Phase 6: relay transparency
    relay = analyze_relay_transparency(entries, peer_messages)

    return CommunicationSummary(
        run_id=run_id,
        total_messages=len(peer_messages),
        peer_messages=peer_messages,
        unique_pairs=len(pairs),
        file_collaborations=file_collabs,
        has_indirect_collaboration=has_indirect,
        relay_analysis=relay,
    )


# --- Persistence ---


def save_comms_summary(summary: CommunicationSummary, comms_dir: Path) -> Path:
    """Save communication summary to JSON."""
    comms_dir.mkdir(parents=True, exist_ok=True)
    path = comms_dir / f"{summary.run_id}_comms.json"
    path.write_text(summary.model_dump_json(indent=2))
    return path


def load_comms_summary(run_id: str, comms_dir: Path) -> CommunicationSummary:
    """Load communication summary from JSON."""
    path = comms_dir / f"{run_id}_comms.json"
    if not path.exists():
        msg = f"Comms summary not found: {path}"
        raise FileNotFoundError(msg)
    return CommunicationSummary.model_validate_json(path.read_text())
