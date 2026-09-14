"""
Git Reflog Temporal Branch Attribution Engine (ADR-046 / M33).

Provides deterministic temporal branch resolution for Antigravity workspaces by
parsing the authoritative Git reflog (.git/logs/HEAD) checkout transitions.
Allows attributing conversation turns to specific feature branches based on turn
timestamps even when checkouts occurred mid-session.
"""

import bisect
import datetime
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple, Union

# Checkout transition regex matching Git's reflog format:
# <old-sha> <new-sha> <committer> <timestamp> <tz-offset>	checkout: moving from <from_branch> to <to_branch>
RE_CHECKOUT = re.compile(
    r"^([0-9a-f]+)\s+([0-9a-f]+)\s+.*?\s+(\d+)\s+([+-]\d{4})\tcheckout: moving from (.+?) to (.+?)$"
)

# In-memory caches:
# _REPO_CACHE: repo_path -> (reflog_path_str, mtime, intervals, start_times)
_REPO_CACHE: Dict[str, Tuple[Optional[str], float, List[Tuple[float, float, str]], List[float]]] = {}


def clear_reflog_cache() -> None:
    """Clear in-memory reflog cache."""
    _REPO_CACHE.clear()


def parse_timestamp_to_epoch(ts_val: Any) -> Optional[float]:
    """
    Parse a timestamp into a UTC epoch float in seconds.
    Accepts datetime objects (aware or naive), ISO strings ('Z' or offset),
    or numeric epoch timestamps (seconds or milliseconds).
    """
    if ts_val is None:
        return None

    if isinstance(ts_val, (int, float)):
        val = float(ts_val)
        if val > 1e11:  # Epoch milliseconds
            val /= 1000.0
        return val

    if isinstance(ts_val, datetime.datetime):
        if ts_val.tzinfo is None:
            ts_val = ts_val.replace(tzinfo=datetime.timezone.utc)
        return ts_val.timestamp()

    if isinstance(ts_val, str):
        val_str = ts_val.strip()
        if not val_str:
            return None

        # Check for numeric string
        try:
            val_num = float(val_str)
            if val_num > 1e11:
                val_num /= 1000.0
            return val_num
        except ValueError:
            pass

        # Handle 'Z' or 'z' suffix
        if val_str.endswith("Z") or val_str.endswith("z"):
            val_str = val_str[:-1] + "+00:00"

        try:
            dt = datetime.datetime.fromisoformat(val_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            return dt.timestamp()
        except Exception:
            return None

    return None


def find_git_dir(workspace_path: Union[str, Path]) -> Optional[Path]:
    """
    Locate the .git directory for a given workspace path.
    Handles:
    - Standard repositories with .git/ directory
    - Git worktrees and submodules with .git file containing 'gitdir: <path>'
    - Direct references to a .git directory itself
    """
    try:
        path = Path(workspace_path).expanduser().resolve()
    except Exception:
        return None

    # Check if path itself is already a .git directory
    if path.name == ".git" and path.is_dir():
        return path

    dot_git = path / ".git"
    if dot_git.is_dir():
        return dot_git

    if dot_git.is_file():
        try:
            content = dot_git.read_text(encoding="utf-8", errors="replace")
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("gitdir:"):
                    gitdir_str = line[len("gitdir:") :].strip()
                    gitdir_path = Path(gitdir_str)
                    if not gitdir_path.is_absolute():
                        gitdir_path = (path / gitdir_path).resolve()
                    if gitdir_path.exists():
                        return gitdir_path
        except Exception:
            return None

    # In case the directory itself contains logs/HEAD (bare repo or direct git dir)
    if (path / "logs" / "HEAD").is_file():
        return path

    return None


def find_reflog_path(workspace_path: Union[str, Path]) -> Optional[Path]:
    """
    Locate the reflog file (.git/logs/HEAD) for a given workspace.
    """
    git_dir = find_git_dir(workspace_path)
    if git_dir is None:
        return None

    reflog = git_dir / "logs" / "HEAD"
    if reflog.is_file():
        return reflog
    return None


def parse_reflog_intervals(reflog_path: str) -> List[Tuple[float, float, str]]:
    """
    Parse a Git reflog file (typically .git/logs/HEAD) into chronological branch intervals.

    Returns a list of tuples: (start_epoch, end_epoch, branch_name).
    - If no checkout events found, returns []
    - For the first checkout event (epoch_0, from_b, to_b):
        interval 0 is (0.0, epoch_0, from_b)
    - Between event[i] and event[i+1]:
        interval is (epoch[i], epoch[i+1], event[i].to_b)
    - After the last event event[-1]:
        interval is (epoch[-1], float('inf'), event[-1].to_b)
    """
    try:
        p = Path(reflog_path).expanduser().resolve()
        if not p.is_file():
            return []
        content = p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []

    events: List[Tuple[float, str, str]] = []
    for line in content.splitlines():
        line = line.strip()
        m = RE_CHECKOUT.match(line)
        if m:
            try:
                epoch = float(m.group(3))
                from_b = m.group(5).strip()
                to_b = m.group(6).strip()
                events.append((epoch, from_b, to_b))
            except (ValueError, IndexError):
                continue

    if not events:
        return []

    # Sort events chronologically by epoch
    events.sort(key=lambda x: x[0])

    intervals: List[Tuple[float, float, str]] = []
    # Interval before first checkout event: from epoch 0.0 to events[0][0]
    intervals.append((0.0, events[0][0], events[0][1]))

    # Intervals between checkouts
    for i in range(len(events) - 1):
        intervals.append((events[i][0], events[i + 1][0], events[i][2]))

    # Interval after the last checkout event to infinity
    intervals.append((events[-1][0], float("inf"), events[-1][2]))

    return intervals


def get_repo_reflog_intervals(repo_path: str) -> List[Tuple[float, float, str]]:
    """
    Retrieve chronological branch intervals for a repository workspace.
    Uses in-memory caching with os.path.getmtime validation for microsecond lookups.
    """
    cached = _REPO_CACHE.get(repo_path)
    if cached is not None:
        reflog_str, cached_mtime, intervals, _ = cached
        if reflog_str is None:
            return []
        try:
            if os.path.getmtime(reflog_str) == cached_mtime:
                return intervals
        except OSError:
            pass

    try:
        norm_path = str(Path(repo_path).expanduser().resolve())
    except Exception:
        return []

    # Check normalized path cache as well
    if norm_path != repo_path:
        cached = _REPO_CACHE.get(norm_path)
        if cached is not None:
            reflog_str, cached_mtime, intervals, _ = cached
            if reflog_str is None:
                _REPO_CACHE[repo_path] = cached
                return []
            try:
                if os.path.getmtime(reflog_str) == cached_mtime:
                    _REPO_CACHE[repo_path] = cached
                    return intervals
            except OSError:
                pass

    reflog = find_reflog_path(norm_path)
    if reflog is None:
        entry = (None, 0.0, [], [])
        _REPO_CACHE[repo_path] = entry
        _REPO_CACHE[norm_path] = entry
        return []

    reflog_str = str(reflog)
    try:
        current_mtime = os.path.getmtime(reflog_str)
    except OSError:
        return []

    intervals = parse_reflog_intervals(reflog_str)
    start_times = [inv[0] for inv in intervals]
    entry = (reflog_str, current_mtime, intervals, start_times)
    _REPO_CACHE[repo_path] = entry
    _REPO_CACHE[norm_path] = entry
    return intervals


def resolve_turn_branch(
    workspace_path: str,
    turn_timestamp: Optional[Union[str, datetime.datetime, float]],
    fallback: str = "main",
) -> str:
    """
    Resolve the active Git branch at the moment a conversation turn occurred.

    Arguments:
        workspace_path: Path to the workspace directory.
        turn_timestamp: Timestamp of the turn (ISO string, datetime, or epoch number).
        fallback: Default branch to return if resolution fails or repo has no reflog.

    Returns:
        Branch name active at turn_timestamp, or fallback.
    """
    if turn_timestamp is None:
        return fallback

    target_ts = parse_timestamp_to_epoch(turn_timestamp)
    if target_ts is None:
        return fallback

    # Direct fast-path cache inspection for sub-microsecond resolution
    cached = _REPO_CACHE.get(workspace_path)
    if cached is not None:
        reflog_str, cached_mtime, intervals, start_times = cached
        if reflog_str is None:
            return fallback
        try:
            if os.path.getmtime(reflog_str) == cached_mtime:
                if not intervals:
                    return fallback
                idx = bisect.bisect_right(start_times, target_ts) - 1
                if idx < 0:
                    return intervals[0][2]
                inv = intervals[idx]
                if inv[0] <= target_ts < inv[1]:
                    return inv[2]
                if idx == len(intervals) - 1 and target_ts >= inv[0]:
                    return inv[2]
                return fallback
        except OSError:
            pass

    intervals = get_repo_reflog_intervals(workspace_path)
    if not intervals:
        return fallback

    cached = _REPO_CACHE.get(workspace_path)
    if cached is not None:
        start_times = cached[3]
    else:
        start_times = [inv[0] for inv in intervals]

    idx = bisect.bisect_right(start_times, target_ts) - 1

    # Before first checkout interval
    if idx < 0:
        return intervals[0][2]

    inv = intervals[idx]
    if inv[0] <= target_ts < inv[1]:
        return inv[2]

    # Boundary at the very end or after last event
    if idx == len(intervals) - 1 and target_ts >= inv[0]:
        return inv[2]

    return fallback
