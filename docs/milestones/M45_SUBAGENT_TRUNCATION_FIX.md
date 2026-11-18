# Milestone 45: Subagent Tracking Truncation Fix

## Objective
Fix a data corruption bug in the Python Vault ingestion pipeline where deep agent swarms with numerous tool calls hit upstream SQLite string character limits, silently truncating `invoke_subagent` UUIDs and severing the swarm lineage graph.

## Technical Execution
- **Lossless Transcript Fallback**: Patched `src/vault.py`'s `sync_conversations_to_vault` to natively locate and read the un-truncated `transcript_full.jsonl` from the Antigravity system logs when available. This entirely bypasses the upstream SQLite truncation limits.
- **Topological DB Repair**: Safely executed manual `UPDATE` commands on `antigravity_vault.db` to restore the missing `parent_convo_id` for two historically orphaned subagents, mathematically verifying via `test_swarms.py` that the total subagent count across the dashboard is correctly recovered.
- **Deduplication Resilience**: Hardened `src/swarm.py` with a `seen` Set to prevent duplicate UUIDs from double-counting agents when spanning both truncated database extracts and fallback logs.
