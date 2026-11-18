#!/usr/bin/env python3
"""
Unit & Integration Tests for Milestone 88: Dashboard Executive Cockpit & Mac Menu Bar Parity.

Verifies:
1. compute_current_session schema parity with macOS AntigravityBar menu bar status model.
2. 2D context drift & severity logic across epochs and token ratios.
3. False-alarm session truncation elimination on Now tab (quarantined to audit drawer).
4. Executive Hero Card DOM elements and data rendering.
5. Dense telemetry drawer wrapping preserving all legacy DOM anchors.
6. JS budget compliance (<800 lines per ADR-066).
"""

import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

from scripts.export_dashboard import compute_current_session
from antigravity_telemetry import load_model_census

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestExecutiveSessionParity(unittest.TestCase):
    """Verifies compute_current_session matches macOS menu bar status model exactly."""

    def setUp(self):
        self.census = load_model_census()

    def test_empty_conversations_returns_none(self):
        """When conversations is empty, compute_current_session returns None."""
        payload = {"conversations": []}
        sess = compute_current_session(payload, self.census)
        self.assertIsNone(sess)

    def test_schema_keys_parity(self):
        """compute_current_session output must contain all canonical schema keys."""
        payload = {
            "summary": {"active_project": "Dashboard Repo", "active_branch": "feat/m88"},
            "conversations": [
                {
                    "convo_id": "test-session-123",
                    "title": "Interactive Session",
                    "last_turn_ts": "2026-10-02T12:00:00Z",
                    "total_input_tokens": 50000,
                    "turn_count": 5,
                    "peak_prompt_depth": 50000,
                    "models_used": ["1016"],
                    "agent_name": "worker",
                }
            ],
        }
        sess = compute_current_session(payload, self.census)
        self.assertIsNotNone(sess)
        expected_keys = {
            "id",
            "title",
            "convo_id",
            "agent_name",
            "is_subagent",
            "subagent_role",
            "branch",
            "workspace",
            "tokens",
            "threshold",
            "nominal_threshold",
            "compaction_threshold",
            "compaction_count",
            "compaction_epoch",
            "severity",
            "drift_risk",
            "drift_message",
            "headroom_to_warning",
            "headroom_to_compaction",
            "is_current",
        }
        self.assertTrue(expected_keys.issubset(sess.keys()), f"Missing keys: {expected_keys - sess.keys()}")
        self.assertEqual(sess["convo_id"], "test-session-123")
        self.assertEqual(sess["severity"], "safe")
        self.assertTrue(sess["is_current"])

    def test_subagent_conversations_filtered_from_primary(self):
        """Subagents must be excluded when selecting the primary active session."""
        payload = {
            "summary": {"active_project": "Dashboard Repo", "active_branch": "main"},
            "conversations": [
                {
                    "convo_id": "subagent-1",
                    "title": "Subagent Session",
                    "last_turn_ts": "2026-10-02T13:00:00Z",
                    "total_input_tokens": 10000,
                    "turn_count": 2,
                    "is_subagent": True,
                    "agent_name": "subagent",
                },
                {
                    "convo_id": "user-convo-1",
                    "title": "User Interactive Session",
                    "last_turn_ts": "2026-10-02T12:00:00Z",
                    "total_input_tokens": 40000,
                    "turn_count": 4,
                    "is_subagent": False,
                    "agent_name": "default",
                },
            ],
        }
        sess = compute_current_session(payload, self.census)
        self.assertIsNotNone(sess)
        self.assertEqual(sess["convo_id"], "user-convo-1")

    def test_2d_severity_and_drift_ratings(self):
        """Verify 2D drift and severity mapping across epochs and token ratios."""
        def make_payload(tokens, epoch=1, comp_count=0):
            return {
                "summary": {},
                "conversations": [
                    {
                        "convo_id": "convo-1",
                        "last_turn_ts": "2026-10-02T12:00:00Z",
                        "total_input_tokens": tokens,
                        "turn_count": 10,
                        "peak_prompt_depth": tokens,
                        "compaction_epoch": epoch,
                        "compaction_count": comp_count,
                        "models_used": ["1016"],  # 1,000,000 threshold
                    }
                ],
            }

        # Safe (<75% of 80k = <60k and epoch 1)
        s1 = compute_current_session(make_payload(40000, epoch=1), self.census)
        self.assertEqual(s1["severity"], "safe")
        self.assertEqual(s1["drift_risk"], "safe")

        # Warning near compaction (>=75% of 80k = >=60k)
        s2 = compute_current_session(make_payload(65000, epoch=1), self.census)
        self.assertEqual(s2["severity"], "warning")
        self.assertEqual(s2["drift_risk"], "caution")

        # Warning epoch 2
        s3 = compute_current_session(make_payload(40000, epoch=2, comp_count=1), self.census)
        self.assertEqual(s3["severity"], "warning")
        self.assertEqual(s3["drift_risk"], "caution")

        # Critical imminent (>=90% of 80k = >=72k)
        s4 = compute_current_session(make_payload(75000, epoch=1), self.census)
        self.assertEqual(s4["severity"], "critical")
        self.assertEqual(s4["drift_risk"], "warning")

        # Critical epoch >= 3
        s5 = compute_current_session(make_payload(40000, epoch=3, comp_count=2), self.census)
        self.assertEqual(s5["severity"], "critical")
        self.assertEqual(s5["drift_risk"], "critical")


class TestDegradedSessionFalseAlarmIsolation(unittest.TestCase):
    """Verifies false alarm elimination via Node.js execution with mock DOM."""

    def test_historical_degraded_does_not_trigger_now_warning(self):
        """Historical session at convos[0] exceeding 80% threshold must NOT trigger Now warning banner."""
        js_code = """
global.window = global;
global.window.addEventListener = () => {};
global.escapeHtml = (s) => s;
global.formatNumber = (n) => String(n);
global.formatCompactNumber = (n) => String(n);
const elements = {};
global.document = {
  addEventListener: () => {},
  getElementById: (id) => {
    if (!elements[id]) {
      elements[id] = { style: {}, classList: { add: ()=>{}, remove: ()=>{} }, setAttribute: ()=>{} };
    }
    return elements[id];
  }
};
const fs = require('fs');
eval(fs.readFileSync('dashboard/js/core-utils.js', 'utf8'));
eval(fs.readFileSync('dashboard/js/sessions-filters.js', 'utf8'));
eval(fs.readFileSync('dashboard/js/now-burst.js', 'utf8'));
eval(fs.readFileSync('dashboard/js/now.js', 'utf8'));
eval(fs.readFileSync('dashboard/js/sessions.js', 'utf8'));

// Historical session has 950,000 tokens (well over 80% of 1M threshold)
const convos = [
  {
    convo_id: 'historical-degraded-1',
    title: 'Completed Audit Session',
    last_turn_ts: new Date().toISOString(),
    total_input_tokens: 950000,
    turn_count: 30,
    peak_prompt_depth: 950000,
    models_used: ['1016']
  }
];

// Active live current session is healthy (15k tokens, safe)
const liveCurrentSession = {
  id: 'active-session-live',
  convo_id: 'active-session-live',
  title: 'Active Fast Session',
  tokens: 15000,
  threshold: 200000,
  severity: 'safe',
  compaction_epoch: 1
};

checkDegradedSessions(convos, liveCurrentSession);

const nowContainer = elements['now-degraded-warning-container'];
const result = {
  nowDisplay: nowContainer ? nowContainer.style.display : null,
  degradedCount: window.__lastDegradedSessions ? window.__lastDegradedSessions.length : 0,
  currentSessionSeverity: window.__lastCurrentSession ? window.__lastCurrentSession.severity : null
};
console.log(JSON.stringify(result));
"""
        res = subprocess.run(["node", "-e", js_code], cwd=REPO_ROOT, capture_output=True, text=True, check=True)
        data = json.loads(res.stdout.strip())
        self.assertEqual(data["nowDisplay"], "none", "Now warning container must be hidden when active session is safe")
        self.assertEqual(data["degradedCount"], 1, "Historical session should still be quarantined to audit list")
        self.assertEqual(data["currentSessionSeverity"], "safe")

    def test_active_critical_session_triggers_warning(self):
        """Active live session that is critical MUST trigger Now warning banner."""
        js_code = """
global.window = global;
global.window.addEventListener = () => {};
global.escapeHtml = (s) => s;
global.formatNumber = (n) => String(n);
global.formatCompactNumber = (n) => String(n);
const elements = {};
global.document = {
  addEventListener: () => {},
  getElementById: (id) => {
    if (!elements[id]) {
      elements[id] = { style: {}, classList: { add: ()=>{}, remove: ()=>{} }, setAttribute: ()=>{} };
    }
    return elements[id];
  }
};
const fs = require('fs');
eval(fs.readFileSync('dashboard/js/core-utils.js', 'utf8'));
eval(fs.readFileSync('dashboard/js/sessions-filters.js', 'utf8'));
eval(fs.readFileSync('dashboard/js/now-burst.js', 'utf8'));
eval(fs.readFileSync('dashboard/js/now.js', 'utf8'));
eval(fs.readFileSync('dashboard/js/sessions.js', 'utf8'));

const convos = [];
const liveCurrentSession = {
  id: 'critical-live-session',
  convo_id: 'critical-live-session',
  title: 'Critical Live Session',
  tokens: 195000,
  threshold: 200000,
  severity: 'critical',
  compaction_epoch: 3,
  drift_message: 'Epoch 3 Drift: Turn 1 evicted'
};

checkDegradedSessions(convos, liveCurrentSession);

const nowContainer = elements['now-degraded-warning-container'];
const result = {
  nowDisplay: nowContainer ? nowContainer.style.display : null,
  currentSessionSeverity: window.__lastCurrentSession ? window.__lastCurrentSession.severity : null
};
console.log(JSON.stringify(result));
"""
        res = subprocess.run(["node", "-e", js_code], cwd=REPO_ROOT, capture_output=True, text=True, check=True)
        data = json.loads(res.stdout.strip())
        self.assertEqual(data["nowDisplay"], "block", "Now warning container must be visible when active session is critical")
        self.assertEqual(data["currentSessionSeverity"], "critical")

    def test_active_degraded_session_not_duplicated_in_historical_list(self):
        """Active session that is degraded must not be duplicated into historical offenders list."""
        js_code = """
global.window = global;
global.window.addEventListener = () => {};
global.escapeHtml = (s) => s;
global.formatNumber = (n) => String(n);
global.formatCompactNumber = (n) => String(n);
const elements = {};
global.document = {
  addEventListener: () => {},
  getElementById: (id) => {
    if (!elements[id]) {
      elements[id] = { style: {}, classList: { add: ()=>{}, remove: ()=>{} }, setAttribute: ()=>{} };
    }
    return elements[id];
  }
};
const fs = require('fs');
eval(fs.readFileSync('dashboard/js/core-utils.js', 'utf8'));
eval(fs.readFileSync('dashboard/js/sessions-filters.js', 'utf8'));
eval(fs.readFileSync('dashboard/js/now-burst.js', 'utf8'));
eval(fs.readFileSync('dashboard/js/now.js', 'utf8'));
eval(fs.readFileSync('dashboard/js/sessions.js', 'utf8'));

// Convos contains both the active session (degraded) and a completed historical session (degraded)
const convos = [
  {
    convo_id: 'active-session-live',
    title: 'Active Session Degraded',
    last_turn_ts: new Date().toISOString(),
    total_input_tokens: 180000,
    turn_count: 25,
    peak_prompt_depth: 180000,
    models_used: ['1035']
  },
  {
    convo_id: 'historical-session-old',
    title: 'Historical Degraded Convo',
    last_turn_ts: new Date(Date.now() - 3600000).toISOString(),
    total_input_tokens: 850000,
    turn_count: 40,
    peak_prompt_depth: 850000,
    models_used: ['1016']
  }
];

const liveCurrentSession = {
  id: 'active-session-live',
  convo_id: 'active-session-live',
  title: 'Active Session Degraded',
  tokens: 180000,
  threshold: 200000,
  severity: 'warning',
  compaction_epoch: 1
};

checkDegradedSessions(convos, liveCurrentSession);

const allDegraded = window.__lastDegradedSessions || [];
const activeSess = window.__lastCurrentSession;
const historicalFiltered = allDegraded.filter(s => !s.is_current && (!activeSess || s.convo_id !== activeSess.convo_id));

const result = {
  totalDegradedInRegistry: allDegraded.length,
  historicalFilteredCount: historicalFiltered.length,
  historicalIds: historicalFiltered.map(s => s.convo_id),
  activeIsCurrent: allDegraded.find(s => s.convo_id === 'active-session-live') ? allDegraded.find(s => s.convo_id === 'active-session-live').is_current : null
};
console.log(JSON.stringify(result));
"""
        res = subprocess.run(["node", "-e", js_code], cwd=REPO_ROOT, capture_output=True, text=True, check=True)
        data = json.loads(res.stdout.strip())
        self.assertEqual(data["totalDegradedInRegistry"], 2)
        self.assertEqual(data["historicalFilteredCount"], 1, "Only historical session should be in filtered historical list")
        self.assertEqual(data["historicalIds"], ["historical-session-old"])
        self.assertTrue(data["activeIsCurrent"], "Active session should have is_current = True")


class TestExecutiveHeroCardDomAndRenderers(unittest.TestCase):
    """Verifies Executive Hero Card DOM anchors, legacy ID retention, and JS renderers."""

    def setUp(self):
        self.index_html = (REPO_ROOT / "dashboard" / "index.html").read_text(encoding="utf-8")

    def test_executive_hero_dom_elements_present(self):
        """All executive hero DOM elements must exist in index.html."""
        required_exec_ids = [
            "executive-hero-card",
            "exec-plan-name",
            "exec-status-badge",
            "exec-status-text",
            "exec-weekly-pct",
            "exec-weekly-bar",
            "exec-weekly-countdown",
            "exec-weekly-verdict",
            "exec-5h-pct",
            "exec-5h-bar",
            "exec-5h-tokens",
            "exec-5h-forecast",
            "exec-velocity-strip",
            "exec-beacon-dot",
            "exec-burn-rate",
            "exec-delta-val",
            "exec-active-model",
            "exec-active-cache",
            "exec-burst-headroom",
            "exec-claude-status",
            "exec-credit-balance",
            "exec-active-context",
        ]
        for elem_id in required_exec_ids:
            self.assertIn(f'id="{elem_id}"', self.index_html, f"Missing executive DOM ID: {elem_id}")

    def test_legacy_runway_dom_elements_retained_in_drawer(self):
        """All legacy runway elements must remain present inside the collapsible drawer."""
        legacy_ids = [
            "dense-telemetry-drawer",
            "runway-dual-bar",
            "runway-consumed-pct",
            "runway-bar-fill",
            "runway-ceiling-marker",
            "runway-time-needle",
            "runway-time-legend",
            "runway-bvi-val",
            "runway-daily-target",
            "runway-exhaustion-val",
            "runway-burst-footer",
        ]
        for elem_id in legacy_ids:
            self.assertIn(f'id="{elem_id}"', self.index_html, f"Legacy ID must be retained: {elem_id}")

        # Verify dense-telemetry-drawer wraps runway-dual-bar
        drawer_pos = self.index_html.find('id="dense-telemetry-drawer"')
        bar_pos = self.index_html.find('id="runway-dual-bar"')
        self.assertNotEqual(drawer_pos, -1)
        self.assertNotEqual(bar_pos, -1)
        self.assertLess(drawer_pos, bar_pos, "dense-telemetry-drawer must wrap runway-dual-bar")

    def test_executive_hero_rendering_in_node(self):
        """renderExecutiveHero and updateExecutiveHeroTicker correctly populate DOM."""
        js_code = """
global.window = global;
global.window.addEventListener = () => {};
global.escapeHtml = (s) => s;
global.formatNumber = (n) => String(n);
global.formatCompactNumber = (n) => String(n);
const elements = {};
global.document = {
  addEventListener: () => {},
  getElementById: (id) => {
    if (!elements[id]) {
      elements[id] = { style: {}, classList: { add: ()=>{}, remove: ()=>{} }, setAttribute: ()=>{} };
    }
    return elements[id];
  }
};
const fs = require('fs');
eval(fs.readFileSync('dashboard/js/core-utils.js', 'utf8'));
eval(fs.readFileSync('dashboard/js/now-burst.js', 'utf8'));
eval(fs.readFileSync('dashboard/js/now.js', 'utf8'));

const payload = {
  summary: {
    tier_display: 'Google AI Ultra (5x)',
    credit_bank_remaining_gbp: 13.05,
    credit_bank_remaining_usd: 16.50
  },
  quotas: {
    rolling_5h: { total_processed_tokens: 12000, turn_count: 4, remaining_pct: 95.0, burst_headroom: 190000000 },
    providers: {
      gemini: {
        weekly: { remaining_pct: 82.5, weekly_reset_utc: '2026-10-07T09:02:00Z', human_remaining: '4d 19h remaining' },
        five_hour: { remaining_pct: 95.0 },
        runway: { status_sub: '+19.5% pacing buffer (Sustainable)' }
      },
      claude_gpt: {
        weekly: { remaining_pct: 100.0 }
      }
    }
  },
  current_session: {
    workspace: 'Antigravity Workspace',
    branch: 'feat/test',
    severity: 'safe'
  }
};

renderExecutiveHero(payload);

updateExecutiveHeroTicker({
  is_streaming: true,
  burn_rate_tok_per_min: 15400,
  last_turn_tokens: 2800,
  last_turn_model: 'Gemini 3.8 Flash (High)',
  last_turn_cache_pct: 94.7,
  gemini_5h_remaining_pct: 95.0
});

const out = {
  plan: elements['exec-plan-name'].textContent,
  statusBadge: elements['exec-status-badge'].className,
  statusText: elements['exec-status-text'].textContent,
  weeklyPct: elements['exec-weekly-pct'].textContent,
  fiveHourPct: elements['exec-5h-pct'].textContent,
  claudeStatus: elements['exec-claude-status'].textContent,
  creditBalance: elements['exec-credit-balance'].textContent,
  activeContext: elements['exec-active-context'].textContent,
  burnRate: elements['exec-burn-rate'].textContent,
  delta: elements['exec-delta-val'].textContent,
  model: elements['exec-active-model'].textContent,
  cache: elements['exec-active-cache'].textContent,
  beacon: elements['exec-beacon-dot'].className
};
console.log(JSON.stringify(out));
"""
        res = subprocess.run(["node", "-e", js_code], cwd=REPO_ROOT, capture_output=True, text=True, check=True)
        data = json.loads(res.stdout.strip())
        self.assertEqual(data["plan"], "Google AI Ultra (5x)")
        self.assertEqual(data["statusBadge"], "exec-status-badge safe")
        self.assertEqual(data["statusText"], "SAFE")
        self.assertEqual(data["weeklyPct"], "82.5%")
        self.assertEqual(data["fiveHourPct"], "95.0%")
        self.assertIn("100% remaining", data["claudeStatus"])
        self.assertEqual(data["creditBalance"], "£13.05")
        self.assertEqual(data["activeContext"], "Antigravity Workspace (feat/test)")
        self.assertEqual(data["burnRate"], "15.4k/m")
        self.assertEqual(data["delta"], "▲ +2.8k")
        self.assertEqual(data["model"], "Gemini 3.8 Flash (High)")
        self.assertEqual(data["cache"], "94.7% cache")
        self.assertIn("streaming", data["beacon"])

    def test_currency_toggle_updates_exec_credit_balance(self):
        """Currency toggle updates #exec-credit-balance between GBP and USD."""
        js_code = """
global.window = global;
global.window.addEventListener = () => {};
global.escapeHtml = (s) => s;
global.formatNumber = (n) => String(n);
global.formatCompactNumber = (n) => String(n);
const elements = {};
global.document = {
  addEventListener: () => {},
  getElementById: (id) => {
    if (!elements[id]) {
      elements[id] = { style: {}, classList: { add: ()=>{}, remove: ()=>{} }, setAttribute: ()=>{} };
    }
    return elements[id];
  }
};
const fs = require('fs');
eval(fs.readFileSync('dashboard/js/core-utils.js', 'utf8'));
eval(fs.readFileSync('dashboard/js/now-burst.js', 'utf8'));
eval(fs.readFileSync('dashboard/js/core.js', 'utf8'));

global.globalDashboardData = {
  summary: {
    usd_to_gbp_fx_rate: 0.79,
    credit_bank_remaining_usd: 16.50,
    credit_bank_remaining_gbp: 13.05
  },
  quotas: {},
  conversations: []
};

// Test GBP
global.activeCurrency = 'GBP';
updateCurrencyViews();
const gbpVal = elements['exec-credit-balance'] ? elements['exec-credit-balance'].textContent : null;

// Test USD
global.activeCurrency = 'USD';
updateCurrencyViews();
const usdVal = elements['exec-credit-balance'] ? elements['exec-credit-balance'].textContent : null;

console.log(JSON.stringify({ gbpVal, usdVal }));
"""
        res = subprocess.run(["node", "-e", js_code], cwd=REPO_ROOT, capture_output=True, text=True, check=True)
        data = json.loads(res.stdout.strip())
        self.assertEqual(data["gbpVal"], "£13.05")
        self.assertEqual(data["usdVal"], "$16.50")


class TestJsBudgetsAndIntegrity(unittest.TestCase):
    """Verifies that all modified JS scripts remain strictly under 800 lines (ADR-066)."""

    def test_script_line_budgets(self):
        js_dir = REPO_ROOT / "dashboard" / "js"
        for js_file in js_dir.glob("*.js"):
            lines = len(js_file.read_text(encoding="utf-8").splitlines())
            self.assertLess(
                lines,
                800,
                f"{js_file.name} has {lines} lines, exceeding the 800-line budget rule (ADR-066)",
            )

    def test_zero_inline_onclick(self):
        """Zero occurrences of inline onclick= in index.html and JS files."""
        index_html = (REPO_ROOT / "dashboard" / "index.html").read_text(encoding="utf-8")
        self.assertEqual(len(re.findall(r"onclick=", index_html)), 0)

        for js_file in (REPO_ROOT / "dashboard" / "js").glob("*.js"):
            content = js_file.read_text(encoding="utf-8")
            self.assertEqual(
                len(re.findall(r"onclick=", content)),
                0,
                f"Found inline onclick in {js_file.name}",
            )


if __name__ == "__main__":
    unittest.main()
