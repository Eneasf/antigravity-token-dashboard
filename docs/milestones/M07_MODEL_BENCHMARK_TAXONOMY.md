# Milestone Slice M07: Multi-Model Benchmark Taxonomy & Subagent Discovery

- **Status**: Completed
- **Date**: 2026-09-06
- **Branch**: feat/telemetry-vault-archive (originating from feat/decouple-subscription-and-overage-credits)
- **Key Evidence**: Grounded via empirical 2-turn Async Sliding Window Log Rate Limiter task across 14 model configurations.

---

## 1. Deliverables & Summary

1. **Standardized 2-Turn Coding Benchmark**:
   - Evaluated 14 model configurations in Google Antigravity across Gemini Flash (3.8, 3.7, 3.6 across High, Medium, Low reasoning tiers), Gemini 3.1 Pro (High, Low), Claude 3.7/3.5 Sonnet &amp; Claude 3 Opus Thinking, GPT OSS Medium, and subagent-routed Gemini Flash Lite.
2. **Discovery of Internal Model ID 1050 (Gemini Flash Lite)**:
   - Proved that while Antigravity omits flash-lite from the primary conversation UI picker, subagents spawned via Model: "flash_lite" map deterministically to **Internal Model ID 1050**.
3. **Multi-Agent Orchestrator Topology**:
   - Mapped orchestrator (b596cf7f - Gemini 3.8 Flash High 1318) to subagent (68481b2d - Gemini Flash Lite 1050), proving subagent tool invocation (invoke_subagent), state tracking, and direct zero-thinking code execution.
4. **All-Time Benchmark Records Established**:
   - **Lowest Cost**: Gemini Flash Lite (1050) at **$0.0029 (£0.0023)** across 2 turns (dethroning 3.6 Flash Low at $0.0050).
   - **Highest Context Cache Hit**: Gemini Flash Lite (1050) at **84.6%** on Turn 2 (surpassing Claude Opus at 80.5%).
   - **Lowest Output Footprint**: 1,637 total output tokens with 0 thinking overhead.
   - **Fastest TTFT**: 0.557s Time-to-First-Token.
5. **Pricing Matrix & Artifacts**:
   - Updated config/pricing.json registering Model 1050.
   - Published complete ledger in docs/MODEL_BENCHMARKS.md.

---

## 2. Verification Command & Proof

```bash
python3 -m unittest discover -s tests
```

**Output**:
```text
Ran 30 tests in 0.695s
OK
```
