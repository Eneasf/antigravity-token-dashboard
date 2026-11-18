"""
Automated Acceptance Gate Runner & Side-Effect Validator (ADR-047 / Milestone 48.1).

Parses active gates in VDONE.md (§A Always-on and §B Current milestone),
validates that every CHECK command is strictly side-effect-free,
and evaluates EXPECT assertions against command returncode, stdout, and wall time.
"""

from pathlib import Path
import os
import re
import subprocess
import sys
import time
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent

ALLOWED_PREFIXES = (
    "python3 -c",
    "python3 -m unittest",
    "python3 -W",
    "grep",
    "test",
    "diff",
    "wc",
    "node",
)

FORBIDDEN_COMMANDS = (
    "setup_service",
    "setup_menubar",
    "build_menubar",
    "watch_telemetry.py",
    "launchctl",
    "git ",
    "publish_to_public",
    "setup_github",
    "capture_showcase",
)

GATE_PATTERN = re.compile(r"^([AB]\d+)\s+(.+?)\s+CHECK\s+(.+?)\s+EXPECT\s+(.+)$")


def parse_vdone_gates(vdone_path: Path):
    """
    Parses VDONE.md and extracts all gate tuples (gate_id, desc, cmd, expect).
    Only scans sections:
      ## A. Always-on gates
      ## B. Current milestone gates
    """
    if not vdone_path.exists():
        return []

    lines = vdone_path.read_text(encoding="utf-8").splitlines()
    gates = []
    current_section = None

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## A.") or "Always-on gates" in stripped:
            current_section = "A"
            continue
        elif stripped.startswith("## B.") or "Current milestone gates" in stripped:
            current_section = "B"
            continue
        elif stripped.startswith("## "):
            current_section = None
            continue

        if current_section in ("A", "B"):
            cleaned = stripped.lstrip("-* \t")
            m = GATE_PATTERN.match(cleaned)
            if m:
                gate_id, desc, cmd, expect = m.groups()
                gates.append((gate_id.strip(), desc.strip(), cmd.strip(), expect.strip()))

    return gates


def is_command_permitted(cmd: str) -> bool:
    """Check whether a command is permitted and free of side-effecting operations."""
    # Strip environment variable prefix (e.g. SKIP_PLAYWRIGHT=1)
    core_cmd = cmd.strip()
    while re.match(r"^[A-Z0-9_]+=[^\s]+\s+", core_cmd):
        core_cmd = re.sub(r"^[A-Z0-9_]+=[^\s]+\s+", "", core_cmd)

    # Validate against allowed command prefixes
    if not any(core_cmd.startswith(p) for p in ALLOWED_PREFIXES):
        return False

    # For python commands, verify no forbidden scripts or side-effecting ops are executed
    if core_cmd.startswith("python3"):
        for forbidden in FORBIDDEN_COMMANDS:
            if forbidden.strip() == "git":
                # Allow read-only git queries (describe, tag, rev-parse, log, show), reject mutating operations
                if re.search(r"\bgit\s+(?:commit|push|checkout|branch|merge|rebase|reset|tag\s+-[ad]|rm)\b", core_cmd):
                    return False
                if re.search(r"['\"]git['\"]\s*,\s*['\"](?:commit|push|checkout|branch|merge|rebase|reset|rm)\b", core_cmd):
                    return False
            elif re.search(r"\b" + re.escape(forbidden.strip()), core_cmd):
                return False
        if "export_dashboard" in core_cmd and "test_export_dashboard" not in core_cmd and "--output-dir" not in core_cmd and "--dry-run" not in core_cmd:
            return False

    return True


def evaluate_expect(gate_id: str, cmd: str, expect: str, proc: subprocess.CompletedProcess, duration: float, test_case: unittest.TestCase):
    """
    Evaluates EXPECT assertions against process execution results.
    Supported forms:
      - 'OK'
      - 'exit code 0' (or 'exit 0')
      - '0'
      - '> N'
      - '< N'
      - '== N'
      - '< N lines'
      - '< N s' (wall time)
    Multiple comma-separated clauses are evaluated sequentially.
    Fails with 'unrecognised EXPECT' if a clause does not match any known form.
    """
    clauses = [c.strip() for c in expect.split(",") if c.strip()]
    if not clauses:
        test_case.fail(f"Gate {gate_id} has empty unrecognised EXPECT")

    stdout = proc.stdout.strip()

    for clause in clauses:
        if clause == "OK":
            test_case.assertEqual(
                proc.returncode,
                0,
                f"Gate {gate_id} expected OK (exit code 0), got {proc.returncode}.\n"
                f"Command: {cmd}\nStdout: {proc.stdout}\nStderr: {proc.stderr}",
            )
        elif clause in ("exit code 0", "exit 0"):
            test_case.assertEqual(
                proc.returncode,
                0,
                f"Gate {gate_id} expected exit code 0, got {proc.returncode}.\n"
                f"Command: {cmd}\nStdout: {proc.stdout}\nStderr: {proc.stderr}",
            )
        elif clause == "0":
            num_match = re.search(r"\b(\d+)\b", stdout)
            if num_match:
                val = int(num_match.group(1))
                test_case.assertEqual(
                    val,
                    0,
                    f"Gate {gate_id} expected 0, got {val}.\n"
                    f"Command: {cmd}\nStdout: {proc.stdout}\nStderr: {proc.stderr}",
                )
            else:
                test_case.assertEqual(
                    proc.returncode,
                    0,
                    f"Gate {gate_id} expected 0 (exit code 0), got {proc.returncode}.\n"
                    f"Command: {cmd}\nStdout: {proc.stdout}\nStderr: {proc.stderr}",
                )
        elif re.match(r"^>\s*(\d+)$", clause):
            expected_n = int(re.match(r"^>\s*(\d+)$", clause).group(1))
            num_match = re.search(r"(\d+)", stdout)
            test_case.assertIsNotNone(
                num_match,
                f"Gate {gate_id} expected > {expected_n}, but stdout had no number.\n"
                f"Command: {cmd}\nStdout: {proc.stdout}",
            )
            val = int(num_match.group(1))
            test_case.assertGreater(
                val,
                expected_n,
                f"Gate {gate_id} expected > {expected_n}, got {val}.\n"
                f"Command: {cmd}\nStdout: {proc.stdout}",
            )
        elif re.match(r"^<\s*(\d+)\s+lines$", clause):
            expected_lines = int(re.match(r"^<\s*(\d+)\s+lines$", clause).group(1))
            num_match = re.search(r"(\d+)", stdout)
            test_case.assertIsNotNone(
                num_match,
                f"Gate {gate_id} expected < {expected_lines} lines, but stdout had no line count.\n"
                f"Command: {cmd}\nStdout: {proc.stdout}",
            )
            val = int(num_match.group(1))
            test_case.assertLess(
                val,
                expected_lines,
                f"Gate {gate_id} expected < {expected_lines} lines, got {val}.\n"
                f"Command: {cmd}\nStdout: {proc.stdout}",
            )
        elif re.match(r"^<\s*(\d+(?:\.\d+)?)\s*s$", clause):
            expected_sec = float(re.match(r"^<\s*(\d+(?:\.\d+)?)\s*s$", clause).group(1))
            test_case.assertLess(
                duration,
                expected_sec,
                f"Gate {gate_id} expected < {expected_sec} s wall time, took {duration:.2f} s.\n"
                f"Command: {cmd}",
            )
        elif re.match(r"^<\s*(\d+)$", clause):
            expected_n = int(re.match(r"^<\s*(\d+)$", clause).group(1))
            num_match = re.search(r"(\d+)", stdout)
            test_case.assertIsNotNone(
                num_match,
                f"Gate {gate_id} expected < {expected_n}, but stdout had no number.\n"
                f"Command: {cmd}\nStdout: {proc.stdout}",
            )
            val = int(num_match.group(1))
            test_case.assertLess(
                val,
                expected_n,
                f"Gate {gate_id} expected < {expected_n}, got {val}.\n"
                f"Command: {cmd}\nStdout: {proc.stdout}",
            )
        elif re.match(r"^==\s*(\d+)$", clause):
            expected_n = int(re.match(r"^==\s*(\d+)$", clause).group(1))
            num_match = re.search(r"(\d+)", stdout)
            test_case.assertIsNotNone(
                num_match,
                f"Gate {gate_id} expected == {expected_n}, but stdout had no number.\n"
                f"Command: {cmd}\nStdout: {proc.stdout}",
            )
            val = int(num_match.group(1))
            test_case.assertEqual(
                val,
                expected_n,
                f"Gate {gate_id} expected == {expected_n}, got {val}.\n"
                f"Command: {cmd}\nStdout: {proc.stdout}",
            )
        elif clause in stdout:
            test_case.assertEqual(
                proc.returncode,
                0,
                f"Gate {gate_id} expected exit code 0 matching '{clause}' in stdout, got {proc.returncode}.\n"
                f"Command: {cmd}\nStdout: {proc.stdout}\nStderr: {proc.stderr}",
            )
        else:
            test_case.fail(f"Gate {gate_id} failed with unrecognised EXPECT: '{clause}'")


class TestVdoneGates(unittest.TestCase):
    """Parses and executes active VDONE acceptance gates."""

    @classmethod
    def setUpClass(cls):
        cls.vdone_path = REPO_ROOT / "VDONE.md"
        cls.gates = parse_vdone_gates(cls.vdone_path)

    def test_vdone_gates_execution(self):
        """Validates command safety and executes all active VDONE gates."""
        if os.environ.get("_IN_VDONE_GATE_RUNNER") == "1":
            # Prevent recursive invocation if invoked by another gate check
            return

        if not self.gates:
            self.skipTest("No active §A or §B gates found in VDONE.md.")

        env = {**os.environ, "_IN_VDONE_GATE_RUNNER": "1"}
        executed_runs = {}

        for gate_id, desc, cmd, expect in self.gates:
            with self.subTest(gate=gate_id, description=desc):
                # Validate command safety
                if not is_command_permitted(cmd):
                    self.fail(f"Side-effecting or unpermitted command in {gate_id}: {cmd}")

                # Avoid running self recursively in subprocess
                if "tests.test_vdone_gates" in cmd:
                    continue

                norm_cmd = " ".join(cmd.split())
                is_full_suite = "unittest discover" in norm_cmd

                # Skip Gate A1 / recursive full test discovery when running inside unittest runner
                is_in_unittest = (
                    "unittest" in sys.argv[0]
                    or any("unittest" in arg or "discover" in arg for arg in sys.argv)
                    or "test_vdone_gates" in sys.argv[0]
                )
                if (gate_id == "A1" or is_full_suite) and is_in_unittest:
                    continue

                # If full test discovery suite already ran within this pass, reuse result to avoid quadratic test recursion
                cached_key = None
                if is_full_suite and any("unittest discover" in k for k in executed_runs):
                    cached_key = [k for k in executed_runs if "unittest discover" in k][0]
                elif norm_cmd in executed_runs:
                    cached_key = norm_cmd

                if cached_key is not None:
                    proc, duration = executed_runs[cached_key]
                else:
                    # Determine timeout from expect clause if present, default to 60s
                    gate_timeout = 60
                    sec_match = re.search(r"<\s*(\d+(?:\.\d+)?)\s*s", expect)
                    if sec_match:
                        gate_timeout = max(60, int(float(sec_match.group(1))) + 5)

                    t0 = time.monotonic()
                    proc = subprocess.run(
                        cmd,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=gate_timeout,
                        cwd=REPO_ROOT,
                        env=env,
                    )
                    duration = time.monotonic() - t0
                    executed_runs[norm_cmd] = (proc, duration)

                evaluate_expect(gate_id, cmd, expect, proc, duration, self)

    def test_unpermitted_commands_rejected(self):
        """Unpermitted or side-effecting commands must be rejected."""
        bad_commands = [
            ("B90", "Bad export", "python3 scripts/export_dashboard.py"),
            ("B91", "Bad daemon", "python3 scripts/setup_service.py restart"),
            ("B92", "Bad git", "git status"),
            ("B93", "Bad launchctl", "launchctl list"),
            ("B94", "Bad menubar", "python3 scripts/setup_menubar.py restart"),
            ("B95", "Bad watcher", "python3 scripts/watch_telemetry.py"),
            ("B96", "Bad publish", "python3 scripts/publish_to_public.py v1.0.0"),
        ]
        for gate_id, desc, cmd in bad_commands:
            with self.subTest(cmd=cmd):
                self.assertFalse(
                    is_command_permitted(cmd),
                    f"Command '{cmd}' should be rejected as side-effecting or unpermitted",
                )

    def test_unrecognised_expect_rejected(self):
        """A gate with an unrecognised EXPECT form must fail with 'unrecognised EXPECT'."""
        dummy_proc = subprocess.CompletedProcess(args="true", returncode=0, stdout="ok", stderr="")
        with self.assertRaises(AssertionError) as ctx:
            evaluate_expect("T1", "true", "invalid_expect_form", dummy_proc, 0.1, self)
        self.assertIn("unrecognised EXPECT", str(ctx.exception))

    def test_evaluate_expect_all_forms(self):
        """Verify each supported EXPECT form evaluates correctly."""
        # OK
        ok_proc = subprocess.CompletedProcess(args="true", returncode=0, stdout="", stderr="")
        evaluate_expect("T_OK", "true", "OK", ok_proc, 0.1, self)

        # exit code 0
        evaluate_expect("T_EXIT", "true", "exit code 0", ok_proc, 0.1, self)

        # 0
        zero_proc = subprocess.CompletedProcess(args="grep", returncode=1, stdout="0\n", stderr="")
        evaluate_expect("T_ZERO", "grep", "0", zero_proc, 0.1, self)

        # > N
        gt_proc = subprocess.CompletedProcess(args="grep", returncode=0, stdout="5\n", stderr="")
        evaluate_expect("T_GT", "grep", "> 2", gt_proc, 0.1, self)

        # < N
        lt_proc = subprocess.CompletedProcess(args="grep", returncode=0, stdout="3\n", stderr="")
        evaluate_expect("T_LT", "grep", "< 10", lt_proc, 0.1, self)

        # == N
        eq_proc = subprocess.CompletedProcess(args="grep", returncode=0, stdout="42\n", stderr="")
        evaluate_expect("T_EQ", "grep", "== 42", eq_proc, 0.1, self)

        # < N lines
        lines_proc = subprocess.CompletedProcess(args="wc", returncode=0, stdout="  24 VDONE.md\n", stderr="")
        evaluate_expect("T_LINES", "wc", "< 150 lines", lines_proc, 0.1, self)

        # < N s
        time_proc = subprocess.CompletedProcess(args="true", returncode=0, stdout="", stderr="")
        evaluate_expect("T_TIME", "true", "< 5 s", time_proc, 0.2, self)

        # Comma separated
        evaluate_expect("T_COMBO", "true", "OK, < 5 s", time_proc, 0.2, self)

        # Substring in stdout
        substr_proc = subprocess.CompletedProcess(args="grep", returncode=0, stdout="Frontend error-free render\n", stderr="")
        evaluate_expect("T_SUBSTR", "grep", "Frontend error-free render", substr_proc, 0.1, self)


if __name__ == "__main__":
    unittest.main()
