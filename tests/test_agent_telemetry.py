"""
Tests for Agent Persona Telemetry & Workflow Attribution (M64 / Gate B1-B5).
Validates wire decoding of Field 4/10/17/5/8, vault migration and backfill,
and workflow role cost attribution across parent-child session hierarchies.
"""

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from typing import Union

from antigravity_telemetry.parser import extract_trajectory_metadata
from antigravity_telemetry.reader import read_single_conversation_metadata
from src.aggregator_attribution import compute_agent_workflow_attribution
from src.vault import (
    init_vault,
    sync_conversations_to_vault,
    backfill_vault_agent_metadata,
)


def _encode_varint(val: int) -> bytes:
    res = bytearray()
    while val > 0x7F:
        res.append((val & 0x7F) | 0x80)
        val >>= 7
    res.append(val & 0x7F)
    return bytes(res)


def _encode_field(field_number: int, val: Union[int, bytes, str]) -> bytes:
    if isinstance(val, int):
        tag = (field_number << 3) | 0
        return _encode_varint(tag) + _encode_varint(val)
    elif isinstance(val, (bytes, bytearray)):
        tag = (field_number << 3) | 2
        return _encode_varint(tag) + _encode_varint(len(val)) + bytes(val)
    elif isinstance(val, str):
        b = val.encode("utf-8")
        tag = (field_number << 3) | 2
        return _encode_varint(tag) + _encode_varint(len(b)) + b
    raise ValueError(f"Unsupported field value type: {type(val)}")


class TestAgentTelemetryExtraction(unittest.TestCase):
    """Tests for wire-format extraction of agent identity and subagent topology."""

    def test_empty_or_none_metadata_returns_defaults(self):
        res_none = extract_trajectory_metadata(None)
        self.assertEqual(res_none["agent_name"], "default")
        self.assertEqual(res_none["agent_description"], "")
        self.assertFalse(res_none["is_subagent"])
        self.assertEqual(res_none["parent_convo_id"], "")
        self.assertEqual(res_none["subagent_role"], "")

        res_empty = extract_trajectory_metadata(b"")
        self.assertEqual(res_empty["agent_name"], "default")
        self.assertEqual(res_empty["agent_description"], "")
        self.assertFalse(res_empty["is_subagent"])

    def test_field_4_agent_persona_decoding(self):
        # Field 4 subfields:
        # 1: agent_name (string)
        # 8: agent_description (string)
        f4_inner = _encode_field(1, "implementer") + _encode_field(8, "Delivers open backlog rows from HANDOVER.md")
        blob = _encode_field(4, f4_inner)

        meta = extract_trajectory_metadata(blob)
        self.assertEqual(meta["agent_name"], "implementer")
        self.assertEqual(meta["agent_description"], "Delivers open backlog rows from HANDOVER.md")
        self.assertFalse(meta["is_subagent"])

    def test_field_10_agent_config_uri_decoding(self):
        # Field 10 contains submessages with file URI or markdown paths
        inner_sub = _encode_field(17, "file:///Users/developer/.gemini/config/agents/auditor.md")
        f10_sub = _encode_field(1, inner_sub)
        blob = _encode_field(10, f10_sub)

        meta = extract_trajectory_metadata(blob)
        self.assertEqual(meta["agent_config_uri"], "file:///Users/developer/.gemini/config/agents/auditor.md")

    def test_subagent_wire_fields_decoding(self):
        # Field 17 = 1 (is_subagent)
        # Field 5 = parent conversation UUID
        # Field 8 subfields: 1 = subagent_type, 2 = subagent_role
        f8_inner = _encode_field(1, "verifier") + _encode_field(2, "Test & Gate Verifier")
        blob = (
            _encode_field(17, 1)
            + _encode_field(5, "1d813262-1dc6-4aa7-bb6f-dbff1da0930e")
            + _encode_field(8, f8_inner)
            + _encode_field(6, "child-convo-9999")
        )

        meta = extract_trajectory_metadata(blob)
        self.assertTrue(meta["is_subagent"])
        self.assertEqual(meta["parent_convo_id"], "1d813262-1dc6-4aa7-bb6f-dbff1da0930e")
        self.assertEqual(meta["subagent_type"], "verifier")
        self.assertEqual(meta["subagent_role"], "Test & Gate Verifier")
        self.assertEqual(meta["convo_id"], "child-convo-9999")

    def test_workspace_and_branch_with_agent(self):
        # Field 1: subfield 1 = workspace, subfield 4 = git branch
        # Field 4: agent persona "auditor"
        f1_inner = _encode_field(1, "/Users/developer/workspace/my-repo") + _encode_field(4, "feat/new-gate")
        f4_inner = _encode_field(1, "auditor") + _encode_field(8, "Codebase and visual auditor")
        blob = _encode_field(1, f1_inner) + _encode_field(4, f4_inner)

        meta = extract_trajectory_metadata(blob)
        self.assertEqual(meta["raw_workspace_uri"], "/Users/developer/workspace/my-repo")
        self.assertEqual(meta["git_branch"], "feat/new-gate")
        self.assertEqual(meta["agent_name"], "auditor")
        self.assertEqual(meta["agent_description"], "Codebase and visual auditor")


class TestVaultAgentMigration(unittest.TestCase):
    """Tests for vault schema migration, column idempotency, and backfill."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.vault_path = Path(self.temp_dir.name) / "test_vault.db"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_fresh_init_vault_creates_agent_columns(self):
        conn = init_vault(self.vault_path)
        cur = conn.cursor()
        cols = {row[1]: row[2] for row in cur.execute("PRAGMA table_info(conversations_archive)")}
        conn.close()

        self.assertIn("agent_name", cols)
        self.assertIn("agent_description", cols)
        self.assertIn("is_subagent", cols)
        self.assertIn("subagent_role", cols)

    def test_legacy_vault_migration_idempotency(self):
        # 1. Create a legacy table without agent columns
        conn = sqlite3.connect(self.vault_path)
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE conversations_archive (
                convo_id TEXT PRIMARY KEY,
                parent_convo_id TEXT,
                workspace_name TEXT,
                workspace_path TEXT,
                title TEXT,
                turn_count INTEGER DEFAULT 0,
                total_input_tokens INTEGER DEFAULT 0,
                total_output_tokens INTEGER DEFAULT 0,
                cached_tokens INTEGER DEFAULT 0,
                thinking_tokens INTEGER DEFAULT 0,
                estimated_cost_usd REAL DEFAULT 0.0,
                first_turn_ts TEXT,
                last_turn_ts TEXT,
                sync_ts TEXT,
                raw_metadata_blob BLOB
            )
            """
        )
        cur.execute(
            """
            INSERT INTO conversations_archive (convo_id, title, turn_count)
            VALUES ('legacy-1', 'Legacy Session', 5)
            """
        )
        conn.commit()
        conn.close()

        # 2. Run init_vault - should gracefully ALTER TABLE to add missing columns
        conn2 = init_vault(self.vault_path)
        cur2 = conn2.cursor()
        cols = {row[1] for row in cur2.execute("PRAGMA table_info(conversations_archive)")}
        self.assertIn("agent_name", cols)
        self.assertIn("is_subagent", cols)
        self.assertIn("subagent_role", cols)

        # 3. Check that existing row is preserved with defaults
        row = cur2.execute("SELECT convo_id, agent_name, is_subagent FROM conversations_archive WHERE convo_id = 'legacy-1'").fetchone()
        self.assertEqual(row[0], "legacy-1")
        self.assertEqual(row[1], "default")
        self.assertEqual(row[2], 0)
        conn2.close()

        # 4. Calling init_vault again is completely idempotent
        conn3 = init_vault(self.vault_path)
        conn3.close()

    def test_backfill_vault_agent_metadata(self):
        conn = init_vault(self.vault_path)
        cur = conn.cursor()

        # Build raw metadata blobs
        f4_impl = _encode_field(1, "implementer") + _encode_field(8, "Backlog worker")
        blob_impl = _encode_field(4, f4_impl)

        f8_child = _encode_field(1, "researcher") + _encode_field(2, "Codebase Explorer")
        blob_child = _encode_field(17, 1) + _encode_field(5, "parent-1") + _encode_field(8, f8_child)

        cur.execute(
            """
            INSERT INTO conversations_archive (convo_id, agent_name, is_subagent, raw_metadata_blob)
            VALUES 
                ('sess-impl', 'default', 0, ?),
                ('sess-child', 'default', 0, ?),
                ('sess-legacy', 'default', 0, NULL)
            """,
            (blob_impl, blob_child),
        )
        conn.commit()
        conn.close()

        # Run backfill
        updated = backfill_vault_agent_metadata(vault_path=self.vault_path)
        self.assertGreaterEqual(updated, 2)

        # Verify updated values
        conn = sqlite3.connect(self.vault_path)
        cur = conn.cursor()
        row_impl = cur.execute("SELECT agent_name, agent_description, is_subagent FROM conversations_archive WHERE convo_id = 'sess-impl'").fetchone()
        self.assertEqual(row_impl[0], "implementer")
        self.assertEqual(row_impl[1], "Backlog worker")
        self.assertEqual(row_impl[2], 0)

        row_child = cur.execute("SELECT agent_name, is_subagent, subagent_role FROM conversations_archive WHERE convo_id = 'sess-child'").fetchone()
        self.assertEqual(row_child[0], "default")
        self.assertEqual(row_child[1], 1)
        self.assertEqual(row_child[2], "Codebase Explorer")

        row_legacy = cur.execute("SELECT agent_name, is_subagent FROM conversations_archive WHERE convo_id = 'sess-legacy'").fetchone()
        self.assertEqual(row_legacy[0], "default")
        self.assertEqual(row_legacy[1], 0)
        conn.close()


class TestAgentWorkflowAttribution(unittest.TestCase):
    """Tests for workflow role cost attribution and hierarchical subagent rollups."""

    def test_empty_conversations(self):
        res = compute_agent_workflow_attribution([])
        self.assertEqual(res["total_sessions"], 0)
        self.assertEqual(res["main_sessions"], 0)
        self.assertEqual(res["subagent_sessions"], 0)
        self.assertIn("auditor", res["by_role"])
        self.assertEqual(res["by_role"]["auditor"]["conversation_count"], 0)

    def test_hierarchical_subagent_cost_rollup(self):
        pricing = {"currency": {"usd_to_gbp_fx_rate": 0.8}}
        conversations = [
            # Main Implementer session
            {
                "convo_id": "impl-root",
                "agent_name": "implementer",
                "is_subagent": False,
                "parent_convo_id": "",
                "turn_count": 10,
                "total_input_tokens": 10000,
                "total_output_tokens": 2000,
                "thinking_tokens": 500,
                "cached_tokens": 4000,
                "estimated_cost_usd": 0.10,
            },
            # Child subagent 1 spawned by Implementer
            {
                "convo_id": "impl-child-1",
                "agent_name": "default",
                "is_subagent": True,
                "parent_convo_id": "impl-root",
                "turn_count": 4,
                "total_input_tokens": 5000,
                "total_output_tokens": 1000,
                "thinking_tokens": 200,
                "cached_tokens": 2000,
                "estimated_cost_usd": 0.05,
            },
            # Main Auditor session
            {
                "convo_id": "audit-root",
                "agent_name": "auditor",
                "is_subagent": False,
                "parent_convo_id": "",
                "turn_count": 8,
                "total_input_tokens": 8000,
                "total_output_tokens": 1500,
                "thinking_tokens": 300,
                "cached_tokens": 3000,
                "estimated_cost_usd": 0.08,
            },
            # Standard General (default) session
            {
                "convo_id": "gen-1",
                "agent_name": "default",
                "is_subagent": False,
                "parent_convo_id": "",
                "turn_count": 2,
                "total_input_tokens": 2000,
                "total_output_tokens": 500,
                "thinking_tokens": 0,
                "cached_tokens": 500,
                "estimated_cost_usd": 0.02,
            },
        ]

        res = compute_agent_workflow_attribution(conversations, pricing_models=pricing)

        self.assertEqual(res["total_sessions"], 4)
        self.assertEqual(res["main_sessions"], 3)
        self.assertEqual(res["subagent_sessions"], 1)

        roles = res["by_role"]
        self.assertIn("implementer", roles)
        self.assertIn("auditor", roles)
        self.assertIn("default", roles)

        impl = roles["implementer"]
        self.assertEqual(impl["conversation_count"], 1)
        self.assertEqual(impl["subagent_count"], 1)
        # Direct: 12000 tokens, Subagents: 6000 tokens -> Total: 18000 tokens
        self.assertEqual(impl["direct_tokens"], 12000)
        self.assertEqual(impl["subagent_tokens"], 6000)
        self.assertEqual(impl["total_tokens"], 18000)
        # Direct cost: 0.10, Subagents: 0.05 -> Total: 0.15
        self.assertAlmostEqual(impl["direct_cost_usd"], 0.10, places=4)
        self.assertAlmostEqual(impl["subagent_cost_usd"], 0.05, places=4)
        self.assertAlmostEqual(impl["imputed_cost_usd"], 0.15, places=4)
        self.assertAlmostEqual(impl["imputed_cost_gbp"], 0.12, places=4)

        audit = roles["auditor"]
        self.assertEqual(audit["conversation_count"], 1)
        self.assertEqual(audit["subagent_count"], 0)
        self.assertEqual(audit["total_tokens"], 9500)
        self.assertAlmostEqual(audit["imputed_cost_usd"], 0.08, places=4)

        default_role = roles["default"]
        self.assertEqual(default_role["conversation_count"], 1)
        self.assertEqual(default_role["total_tokens"], 2500)
        self.assertAlmostEqual(default_role["imputed_cost_usd"], 0.02, places=4)

        # Portfolio grand totals
        # Total cost = 0.10 + 0.05 + 0.08 + 0.02 = 0.25 USD
        self.assertAlmostEqual(res["total_imputed_cost_usd"], 0.25, places=4)
        self.assertAlmostEqual(res["total_imputed_cost_gbp"], 0.20, places=4)
        self.assertEqual(res["total_tokens"], 18000 + 9500 + 2500)


if __name__ == "__main__":
    unittest.main()
