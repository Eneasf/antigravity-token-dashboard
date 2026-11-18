#!/usr/bin/env python3
"""
build_ci_fixtures.py

Generates reproducible, anonymized offline Antigravity telemetry fixtures for CI and testing.
Creates:
- tests/fixtures/antigravity/conversations/*.db (Gemini & Claude turns, sanitized trajectory metadata)
- tests/fixtures/antigravity/annotations/*.pbtxt (Human-readable conversation titles)
- tests/fixtures/antigravity/agyhub_summaries_proto.pb (Workspace summary mapping)

Guarantees 100% zero PII, zero personal paths, and deterministic byte output.
"""

from pathlib import Path
import sqlite3

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "antigravity"


def encode_varint(val: int) -> bytes:
    """Encode unsigned integer to protobuf varint wire format."""
    res = bytearray()
    while True:
        towrite = val & 0x7F
        val >>= 7
        if val:
            res.append(towrite | 0x80)
        else:
            res.append(towrite)
            break
    return bytes(res)


def make_field(field_num: int, wire_type: int, payload: bytes) -> bytes:
    """Encode a protobuf tag and payload."""
    key = (field_num << 3) | wire_type
    return encode_varint(key) + payload


def build_step_metadata(
    seconds: int,
    nanos: int,
    model_id: int,
    uncached: int,
    total_out: int,
    cached: int,
    thinking: int,
    answer: int,
    response_id: str,
) -> bytes:
    """Build a sanitized steps.metadata protobuf blob."""
    ts_bytes = (
        make_field(1, 0, encode_varint(seconds)) +
        make_field(2, 0, encode_varint(nanos))
    )
    field_1 = make_field(1, 2, encode_varint(len(ts_bytes)) + ts_bytes)

    resp_bytes = response_id.encode("utf-8")
    usage_bytes = (
        make_field(1, 0, encode_varint(model_id)) +
        make_field(2, 0, encode_varint(uncached)) +
        make_field(3, 0, encode_varint(total_out)) +
        make_field(5, 0, encode_varint(cached)) +
        make_field(9, 0, encode_varint(thinking)) +
        make_field(10, 0, encode_varint(answer)) +
        make_field(11, 2, encode_varint(len(resp_bytes)) + resp_bytes)
    )
    field_9 = make_field(9, 2, encode_varint(len(usage_bytes)) + usage_bytes)
    return field_1 + field_9


def build_trajectory_metadata_blob(convo_id: str, ws_uri: str, git_branch: str) -> bytes:
    """Build a sanitized trajectory_metadata_blob data field."""
    ws_bytes = ws_uri.encode("utf-8")
    branch_bytes = git_branch.encode("utf-8")
    convo_bytes = convo_id.encode("utf-8")

    sub_1 = (
        make_field(1, 2, encode_varint(len(ws_bytes)) + ws_bytes) +
        make_field(4, 2, encode_varint(len(branch_bytes)) + branch_bytes)
    )
    field_1 = make_field(1, 2, encode_varint(len(sub_1)) + sub_1)
    field_6 = make_field(6, 2, encode_varint(len(convo_bytes)) + convo_bytes)
    return field_1 + field_6


def create_conversation_db(
    db_path: Path,
    convo_id: str,
    ws_uri: str,
    git_branch: str,
    turns_specs: list,
):
    """Create a single conversation SQLite database conforming to Antigravity schema."""
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    # Create steps table
    cur.execute(
        """
        CREATE TABLE steps (
            idx INTEGER PRIMARY KEY,
            step_type INTEGER,
            metadata BLOB
        )
        """
    )

    for idx, spec in enumerate(turns_specs, start=1):
        blob = build_step_metadata(**spec)
        cur.execute("INSERT INTO steps (idx, step_type, metadata) VALUES (?, 15, ?)", (idx, blob))

    # Create trajectory_metadata_blob table
    cur.execute(
        """
        CREATE TABLE trajectory_metadata_blob (
            id TEXT PRIMARY KEY,
            data BLOB
        )
        """
    )
    traj_blob = build_trajectory_metadata_blob(convo_id, ws_uri, git_branch)
    cur.execute("INSERT INTO trajectory_metadata_blob (id, data) VALUES ('main', ?)", (traj_blob,))

    conn.commit()
    conn.close()


def main():
    conv_dir = FIXTURE_DIR / "conversations"
    ann_dir = FIXTURE_DIR / "annotations"
    conv_dir.mkdir(parents=True, exist_ok=True)
    ann_dir.mkdir(parents=True, exist_ok=True)

    # 1. Conversation 1: Gemini Project Alpha (Models 1318 & 1050)
    cid_1 = "11111111-1111-1111-1111-111111111111"
    db_1 = conv_dir / f"{cid_1}.db"
    turns_1 = [
        {
            "seconds": 1788614400,  # 2026-09-13T12:00:00Z
            "nanos": 0,
            "model_id": 1318,       # Gemini 3.8 Flash High
            "uncached": 4000,
            "total_out": 500,
            "cached": 16000,
            "thinking": 350,
            "answer": 150,
            "response_id": "resp-alpha-001",
        },
        {
            "seconds": 1788614700,  # 2026-09-13T12:05:00Z
            "nanos": 0,
            "model_id": 1050,       # Gemini Flash Lite (Mechanical Subagent)
            "uncached": 1200,
            "total_out": 200,
            "cached": 4800,
            "thinking": 0,
            "answer": 200,
            "response_id": "resp-alpha-002",
        },
    ]
    create_conversation_db(
        db_1,
        cid_1,
        "file:///workspace/project-alpha",
        "main",
        turns_1,
    )
    (ann_dir / f"{cid_1}.pbtxt").write_text('title: "Project Alpha Architecture"\n', encoding="utf-8")

    # 2. Conversation 2: Claude Benchmark Beta (Model 1026 Opus)
    cid_2 = "22222222-2222-2222-2222-222222222222"
    db_2 = conv_dir / f"{cid_2}.db"
    turns_2 = [
        {
            "seconds": 1788618000,  # 2026-09-13T13:00:00Z
            "nanos": 0,
            "model_id": 1026,       # Claude Opus 4.6 (Thinking)
            "uncached": 6000,
            "total_out": 800,
            "cached": 45000,
            "thinking": 600,
            "answer": 200,
            "response_id": "resp-beta-001",
        },
    ]
    create_conversation_db(
        db_2,
        cid_2,
        "file:///workspace/project-beta",
        "feat/claude-audit",
        turns_2,
    )
    (ann_dir / f"{cid_2}.pbtxt").write_text('title: "Claude Performance Benchmarks"\n', encoding="utf-8")

    # 3. agyhub_summaries_proto.pb
    pb_file = FIXTURE_DIR / "agyhub_summaries_proto.pb"
    # Format matches regex: UUID followed by file:///...
    pb_bytes = (
        f"{cid_1}\x12\x1cfile:///workspace/project-alpha\n"
        f"{cid_2}\x1bfile:///workspace/project-beta\n"
    ).encode("utf-8")
    pb_file.write_bytes(pb_bytes)

    print(f"✓ Anonymized fixtures successfully generated in {FIXTURE_DIR}")


if __name__ == "__main__":
    main()
