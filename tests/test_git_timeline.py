"""
Unit tests for Git Reflog Temporal Branch Attribution (ADR-046 / M33).
"""

import datetime
import math
import os
from pathlib import Path
import tempfile
import time
import unittest

from src.git_timeline import (
    clear_reflog_cache,
    find_git_dir,
    find_reflog_path,
    get_repo_reflog_intervals,
    parse_reflog_intervals,
    parse_timestamp_to_epoch,
    resolve_turn_branch,
    _REPO_CACHE,
)

SAMPLE_REFLOG_CONTENT = """0000000000000000000000000000000000000000 1111111111111111111111111111111111111111 Dev <dev@example.com> 1000 +0000	commit (initial): initial commit
1111111111111111111111111111111111111111 2222222222222222222222222222222222222222 Dev <dev@example.com> 2000 +0000	checkout: moving from main to feat/alpha
2222222222222222222222222222222222222222 3333333333333333333333333333333333333333 Dev <dev@example.com> 2500 +0000	commit: work on alpha
3333333333333333333333333333333333333333 4444444444444444444444444444444444444444 Dev <dev@example.com> 3000 +0000	checkout: moving from feat/alpha to feat/beta
4444444444444444444444444444444444444444 5555555555555555555555555555555555555555 Dev <dev@example.com> 4000 +0000	checkout: moving from feat/beta to main
5555555555555555555555555555555555555555 6666666666666666666666666666666666666666 Dev <dev@example.com> 4500 +0000	merge feat/beta: Merge made by ort
"""


class TestGitTimeline(unittest.TestCase):

    def setUp(self):
        clear_reflog_cache()

    def tearDown(self):
        clear_reflog_cache()

    def test_parse_reflog_intervals_synthetic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reflog_file = Path(tmpdir) / "HEAD"
            reflog_file.write_text(SAMPLE_REFLOG_CONTENT, encoding="utf-8")

            intervals = parse_reflog_intervals(str(reflog_file))
            # 3 checkouts -> 4 intervals
            self.assertEqual(len(intervals), 4)

            # Interval 0: before first checkout at 2000
            self.assertEqual(intervals[0], (0.0, 2000.0, "main"))

            # Interval 1: between 2000 and 3000
            self.assertEqual(intervals[1], (2000.0, 3000.0, "feat/alpha"))

            # Interval 2: between 3000 and 4000
            self.assertEqual(intervals[2], (3000.0, 4000.0, "feat/beta"))

            # Interval 3: from 4000 onwards to infinity
            self.assertEqual(intervals[3][0], 4000.0)
            self.assertTrue(math.isinf(intervals[3][1]))
            self.assertEqual(intervals[3][2], "main")

    def test_parse_reflog_intervals_empty_and_missing(self):
        self.assertEqual(parse_reflog_intervals("/nonexistent/reflog/path"), [])

        with tempfile.TemporaryDirectory() as tmpdir:
            empty_file = Path(tmpdir) / "empty"
            empty_file.write_text("", encoding="utf-8")
            self.assertEqual(parse_reflog_intervals(str(empty_file)), [])

            no_checkouts = Path(tmpdir) / "no_checkouts"
            no_checkouts.write_text(
                "111 222 Dev <d@e.com> 1000 +0000\tcommit: some commit\n",
                encoding="utf-8",
            )
            self.assertEqual(parse_reflog_intervals(str(no_checkouts)), [])

    def test_interval_resolution_boundaries(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dot_git = Path(tmpdir) / ".git"
            logs_head = dot_git / "logs" / "HEAD"
            logs_head.parent.mkdir(parents=True)
            logs_head.write_text(SAMPLE_REFLOG_CONTENT, encoding="utf-8")

            # 1. Before first event (exact boundary, middle, zero, negative)
            self.assertEqual(resolve_turn_branch(tmpdir, 500.0), "main")
            self.assertEqual(resolve_turn_branch(tmpdir, 0.0), "main")
            self.assertEqual(resolve_turn_branch(tmpdir, -100.0), "main")
            self.assertEqual(resolve_turn_branch(tmpdir, 1999.999), "main")

            # 2. Exact boundary at first checkout (t=2000.0)
            self.assertEqual(resolve_turn_branch(tmpdir, 2000.0), "feat/alpha")

            # 3. Middle of interval 1
            self.assertEqual(resolve_turn_branch(tmpdir, 2500.0), "feat/alpha")
            self.assertEqual(resolve_turn_branch(tmpdir, 2999.999), "feat/alpha")

            # 4. Exact boundary at second checkout (t=3000.0)
            self.assertEqual(resolve_turn_branch(tmpdir, 3000.0), "feat/beta")

            # 5. Middle of interval 2
            self.assertEqual(resolve_turn_branch(tmpdir, 3500.0), "feat/beta")
            self.assertEqual(resolve_turn_branch(tmpdir, 3999.999), "feat/beta")

            # 6. Exact boundary at third checkout (t=4000.0)
            self.assertEqual(resolve_turn_branch(tmpdir, 4000.0), "main")

            # 7. After last event (middle and far future)
            self.assertEqual(resolve_turn_branch(tmpdir, 5000.0), "main")
            self.assertEqual(resolve_turn_branch(tmpdir, 1000000.0), "main")
            self.assertEqual(resolve_turn_branch(tmpdir, float("inf")), "main")

    def test_cache_hit_and_invalidation_on_mtime(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dot_git = Path(tmpdir) / ".git"
            logs_head = dot_git / "logs" / "HEAD"
            logs_head.parent.mkdir(parents=True)
            logs_head.write_text(SAMPLE_REFLOG_CONTENT, encoding="utf-8")

            # First resolution populates cache
            b1 = resolve_turn_branch(tmpdir, 2500.0)
            self.assertEqual(b1, "feat/alpha")

            norm_path = str(Path(tmpdir).resolve())
            self.assertIn(norm_path, _REPO_CACHE)
            _, cached_mtime, cached_inv, _ = _REPO_CACHE[norm_path]

            # Cache hit check: returns same cached list
            inv2 = get_repo_reflog_intervals(tmpdir)
            self.assertIs(inv2, cached_inv)

            # Invalidate cache by appending a new checkout line and advancing mtime
            time.sleep(0.01)
            new_line = "666 777 Dev <d@e.com> 5000 +0000\tcheckout: moving from main to feat/gamma\n"
            with open(logs_head, "a", encoding="utf-8") as f:
                f.write(new_line)

            # Explicitly bump mtime to ensure filesystem reflects change
            new_mtime = cached_mtime + 5.0
            os.utime(logs_head, (new_mtime, new_mtime))

            # Query turn at t=6000.0 should now resolve to feat/gamma
            b2 = resolve_turn_branch(tmpdir, 6000.0)
            self.assertEqual(b2, "feat/gamma")

            # Verify cache has updated mtime
            _, updated_mtime, _, _ = _REPO_CACHE[norm_path]
            self.assertEqual(updated_mtime, new_mtime)

    def test_worktree_and_submodule_support(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            main_repo = Path(tmpdir) / "main_repo"
            worktree_dir = Path(tmpdir) / "worktree_repo"
            main_repo.mkdir()
            worktree_dir.mkdir()

            # Main repo has gitdir with worktrees metadata
            wt_gitdir = main_repo / ".git" / "worktrees" / "wt1"
            wt_logs_head = wt_gitdir / "logs" / "HEAD"
            wt_logs_head.parent.mkdir(parents=True)
            wt_logs_head.write_text(SAMPLE_REFLOG_CONTENT, encoding="utf-8")

            # Case A: Worktree with absolute gitdir
            git_file = worktree_dir / ".git"
            git_file.write_text(f"gitdir: {wt_gitdir}\n", encoding="utf-8")

            found_dir = find_git_dir(worktree_dir)
            self.assertEqual(found_dir, wt_gitdir)
            self.assertEqual(resolve_turn_branch(str(worktree_dir), 2500.0), "feat/alpha")

            # Case B: Submodule or worktree with relative gitdir
            clear_reflog_cache()
            git_file.write_text("gitdir: ../main_repo/.git/worktrees/wt1\n", encoding="utf-8")
            self.assertEqual(resolve_turn_branch(str(worktree_dir), 3500.0), "feat/beta")

    def test_non_git_workspace_fallback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Completely empty directory
            self.assertEqual(resolve_turn_branch(tmpdir, 1000.0), "main")
            self.assertEqual(resolve_turn_branch(tmpdir, 1000.0, fallback="develop"), "develop")
            self.assertEqual(get_repo_reflog_intervals(tmpdir), [])

            # Non-existent workspace
            non_existent = str(Path(tmpdir) / "does_not_exist")
            self.assertEqual(resolve_turn_branch(non_existent, 1000.0), "main")

    def test_timestamp_parsing_formats(self):
        # 1. ISO string with Z
        epoch_z = parse_timestamp_to_epoch("2026-09-13T20:42:00Z")
        self.assertIsNotNone(epoch_z)
        self.assertEqual(epoch_z, 1789332120.0)

        # 2. ISO string with timezone offset
        epoch_off = parse_timestamp_to_epoch("2026-09-13T21:42:00+01:00")
        self.assertEqual(epoch_off, 1789332120.0)

        # 3. ISO string naive (defaults to UTC)
        epoch_naive = parse_timestamp_to_epoch("2026-09-13T20:42:00")
        self.assertEqual(epoch_naive, 1789332120.0)

        # 4. datetime object timezone-aware
        dt_aware = datetime.datetime(2026, 9, 13, 20, 42, 0, tzinfo=datetime.timezone.utc)
        self.assertEqual(parse_timestamp_to_epoch(dt_aware), 1789332120.0)

        # 5. datetime object naive
        dt_naive = datetime.datetime(2026, 9, 13, 20, 42, 0)
        self.assertEqual(parse_timestamp_to_epoch(dt_naive), 1789332120.0)

        # 6. Numeric epoch float
        self.assertEqual(parse_timestamp_to_epoch(1789332120.0), 1789332120.0)

        # 7. Numeric epoch int
        self.assertEqual(parse_timestamp_to_epoch(1789332120), 1789332120.0)

        # 8. Numeric millisecond epoch (> 1e11)
        self.assertEqual(parse_timestamp_to_epoch(1789332120000), 1789332120.0)

        # 9. String numeric
        self.assertEqual(parse_timestamp_to_epoch("1789332120.0"), 1789332120.0)
        self.assertEqual(parse_timestamp_to_epoch("1789332120000"), 1789332120.0)

        # 10. Invalid and None
        self.assertIsNone(parse_timestamp_to_epoch(None))
        self.assertIsNone(parse_timestamp_to_epoch(""))
        self.assertIsNone(parse_timestamp_to_epoch("not-a-timestamp"))
        self.assertIsNone(parse_timestamp_to_epoch([12345]))

    def test_live_reflog_gate_v171(self):
        # Gate V171 exact check against local development reflog
        intervals = parse_reflog_intervals(".git/logs/HEAD")
        if len(intervals) < 10:
            self.skipTest("Local git reflog contains fewer than 10 transitions (fresh clone or CI environment)")
        self.assertGreaterEqual(len(intervals), 10)
        b = resolve_turn_branch(".", "2026-09-13T20:42:00+00:00")
        self.assertEqual(b, "feat/ci-offline-fixtures-and-showcase")

    def test_lookup_performance_10k(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dot_git = Path(tmpdir) / ".git"
            logs_head = dot_git / "logs" / "HEAD"
            logs_head.parent.mkdir(parents=True)
            logs_head.write_text(SAMPLE_REFLOG_CONTENT, encoding="utf-8")

            # Prime the cache
            resolve_turn_branch(tmpdir, 2500.0)

            t0 = time.perf_counter()
            for _ in range(10000):
                b = resolve_turn_branch(tmpdir, 2500.0)
                self.assertEqual(b, "feat/alpha")
            elapsed = time.perf_counter() - t0

            # 10,000 lookups should complete in under 0.25s (25 microseconds per lookup)
            self.assertLess(elapsed, 0.25)


if __name__ == "__main__":
    unittest.main()
