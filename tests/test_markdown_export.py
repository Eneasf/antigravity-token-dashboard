"""
Unit tests for byte-deterministic Markdown standup digest export (Milestone 28).

Validates:
- generate_markdown_digest produces byte-identical output given identical payload (ADR-004).
- Key telemetry metrics (tokens, caching, avoided cost, AI credits, quotas, models) are accurately formatted.
- export_dashboard.py --markdown CLI execution outputs clean Markdown to stdout.
"""

from pathlib import Path
import subprocess
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.export_dashboard import generate_markdown_digest


class TestMarkdownExport(unittest.TestCase):
    """Test suite for Markdown standup digest generation and byte-determinism."""

    def setUp(self):
        self.sample_payload = {
            "summary": {
                "subscription_tier": "ultra_5x",
                "subscription_tier_name": "Google AI Ultra (20 TB - 5x AI Usage)",
                "monthly_subscription_price_gbp": 79.99,
                "monthly_subscription_price_usd": 99.99,
                "subscription_status": "SAFE_IN_QUOTA",
                "total_processed_tokens": 1250000,
                "total_input_tokens": 1000000,
                "total_output_tokens": 250000,
                "total_cached_tokens": 850000,
                "cache_hit_ratio_pct": 85.0,
                "total_imputed_value_gbp": 42.50,
                "total_imputed_value_usd": 53.80,
                "total_ai_credits_burned": 1179,
                "total_credit_burn_gbp": 11.31,
                "total_credit_burn_usd": 11.79,
                "by_model": {
                    "1318": {
                        "name": "Gemini 3.8 Flash (High)",
                        "total_processed_tokens": 800000,
                        "turn_count": 120,
                        "estimated_cost_gbp": 18.20,
                    },
                    "1016": {
                        "name": "Gemini 3.1 Pro (High)",
                        "total_processed_tokens": 350000,
                        "turn_count": 30,
                        "estimated_cost_gbp": 21.10,
                    },
                    "1026": {
                        "name": "Claude Opus 4.6 (Thinking)",
                        "total_processed_tokens": 100000,
                        "turn_count": 10,
                        "estimated_cost_gbp": 3.20,
                    },
                },
            },
            "quotas": {
                "credit_bank": {
                    "remaining_credits": 3821,
                },
                "weekly_cycle": {
                    "reset_display": "Thursday, 17 Sep 2026, 18:00 UTC",
                },
                "providers": {
                    "gemini": {
                        "five_hour": {"used_pct": 14.5},
                        "weekly": {
                            "used_pct": 28.2,
                            "reset_display": "Thursday, 17 Sep 2026, 18:00 UTC",
                        },
                        "runway": {"burn_velocity_index": 0.85},
                    },
                    "claude_gpt": {
                        "five_hour": {"used_pct": 5.0},
                        "weekly": {"used_pct": 12.0},
                    },
                },
            },
        }

    def test_byte_determinism_invariant(self):
        """Digest generation must produce byte-identical strings on repeated executions (ADR-004)."""
        digest1 = generate_markdown_digest(self.sample_payload)
        digest2 = generate_markdown_digest(self.sample_payload)
        self.assertEqual(digest1, digest2)
        self.assertEqual(digest1.encode("utf-8"), digest2.encode("utf-8"))

    def test_metrics_accuracy(self):
        """Digest accurately presents token throughput, financial values, and headroom."""
        digest = generate_markdown_digest(self.sample_payload)
        self.assertIn("1,250,000 tokens", digest)
        self.assertIn("85.0% hit ratio", digest)
        self.assertIn("£42.50 ($53.80)", digest)
        self.assertIn("1,179 credits", digest)
        self.assertIn("3,821 credits remaining", digest)
        self.assertIn("Gemini 5-Hour Burst**: 14.5% used (85.5% remaining)", digest)
        self.assertIn("Gemini Weekly Runway**: 28.2% used (71.8% remaining)", digest)
        self.assertIn("Claude/GPT 5-Hour Burst**: 5.0% used (95.0% remaining)", digest)
        self.assertIn("Claude/GPT Weekly**: 12.0% used (88.0% remaining)", digest)
        self.assertIn("Gemini 3.8 Flash (High)", digest)
        self.assertIn("Gemini 3.1 Pro (High)", digest)
        self.assertIn("Claude Opus 4.6 (Thinking)", digest)

    def test_cli_markdown_invocation(self):
        """Running scripts/export_dashboard.py --markdown via subprocess outputs markdown to stdout."""
        cmd = [
            sys.executable,
            str(REPO_ROOT / "scripts" / "export_dashboard.py"),
            "--markdown",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("### 📊 Antigravity Telemetry Standup Digest", proc.stdout)
        self.assertIn("Token Throughput & Cache Efficiency", proc.stdout)
        self.assertIn("Economic Value & AI Credit Ledger", proc.stdout)


if __name__ == "__main__":
    unittest.main()
