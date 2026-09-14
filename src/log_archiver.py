"""
Log archiver and truncation-resilient tailer for Antigravity runtime logs (ADR-018).

Monitors and tails ~/Library/Logs/Antigravity/language_server.log,
detecting file truncations, rotations, and IDE restarts via file size and inode tracking.
Extracts 429 RESOURCE_EXHAUSTED rate-limit events, lifecycle transitions, and error events,
persisting them idempotently into data/antigravity_vault.db (log_events_archive).
"""

from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import re
import sqlite3
from typing import Any, Dict, List, Optional, Union

# Default system paths
DEFAULT_LOG_PATH = Path.home() / "Library" / "Logs" / "Antigravity" / "language_server.log"
DEFAULT_VAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "antigravity_vault.db"

# Event type constants
EVENT_RESOURCE_EXHAUSTED = "RESOURCE_EXHAUSTED"
EVENT_LIFECYCLE = "LIFECYCLE"
EVENT_ERROR = "ERROR"

# Google glog timestamp pattern: e.g. I0905 13:35:13.877653 8813 run.go:371]
GLOG_TIMESTAMP_PATTERN = re.compile(
    r"[IWEF](\d{2})(\d{2})\s+(\d{2}):(\d{2}):(\d{2})\.(\d{6})"
)

# ISO 8601 timestamp pattern
ISO_TIMESTAMP_PATTERN = re.compile(
    r"(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)"
)

# Google glog preface prefix frequently prepended by Go binaries before google.Init
GLOG_PREFACE_PATTERN = re.compile(
    r"^ERROR:\s*logging before google\.Init:\s*", re.IGNORECASE
)

# Glog Error or Fatal flags (Emmdd or Fmmdd)
GLOG_SEVERITY_PATTERN = re.compile(
    r"^[EF]\d{4}\s+\d{2}:\d{2}:\d{2}\.\d{6}"
)

# 429 RESOURCE_EXHAUSTED detection pattern
EXHAUSTION_PATTERN = re.compile(
    r"(RESOURCE_EXHAUSTED|code\s+429|status\s+429|exhausted your capacity|rate[_\s]limit|quota[_\s]exceeded)",
    re.IGNORECASE,
)

# Server startup / shutdown / lifecycle event pattern
LIFECYCLE_PATTERN = re.compile(
    r"(Starting language server|Language server started|Language server listening|"
    r"Server listening|Language server initialized|Language server ready|"
    r"Shutting down language server|Server shutting down|Language server stopped|Language server exiting|"
    r"Language server process (?:started|stopped|exited)|"
    r"server process stopped|terminating language server|server shutdown|"
    r"server restart|server started|"
    r"server\.go:\d+\]\s+(?:Starting|Shutting down|Shutdown|Stopped|Listening|Started))",
    re.IGNORECASE,
)

# Error and exception pattern
ERROR_PATTERN = re.compile(
    r"(\b(?:ERROR|FATAL|PANIC|CRITICAL|FAIL|FAILED|FAILURE|EXCEPTION)\b|"
    r"level=(?:error|fatal|critical)|"
    r"Traceback \(most recent call last\):|"
    r"\[(?:ERROR|FATAL|CRITICAL)\]|"
    r"connection refused|connection reset|broken pipe|segmentation fault)",
    re.IGNORECASE,
)


def parse_timestamp(
    line: str,
    default_year: Optional[int] = None,
    mtime: Optional[float] = None,
) -> Optional[datetime]:
    """Extract and parse timestamp from a log line (supports glog and ISO 8601)."""
    if default_year is None and mtime is not None:
        try:
            default_year = datetime.fromtimestamp(mtime, tz=timezone.utc).year
        except Exception:
            pass
    if default_year is None:
        default_year = datetime.now(timezone.utc).year

    # 1. Glog timestamp
    glog_match = GLOG_TIMESTAMP_PATTERN.search(line)
    if glog_match:
        month = int(glog_match.group(1))
        day = int(glog_match.group(2))
        hour = int(glog_match.group(3))
        minute = int(glog_match.group(4))
        second = int(glog_match.group(5))
        microsecond = int(glog_match.group(6))
        try:
            return datetime(
                default_year, month, day, hour, minute, second, microsecond, tzinfo=timezone.utc
            )
        except ValueError:
            pass

    # 2. ISO 8601 timestamp
    iso_match = ISO_TIMESTAMP_PATTERN.search(line)
    if iso_match:
        iso_str = iso_match.group(1).replace(" ", "T")
        if not iso_str.endswith("Z") and "+" not in iso_str and "-" not in iso_str[10:]:
            iso_str += "+00:00"
        elif iso_str.endswith("Z"):
            iso_str = iso_str[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(iso_str)
        except ValueError:
            pass

    return None


def classify_event(line: str) -> Optional[str]:
    """
    Classify a log line into one of the tracked event types:
    - RESOURCE_EXHAUSTED (429 rate limit events)
    - LIFECYCLE (server startup, shutdown, initialization)
    - ERROR (exceptions, panics, fatal/error lines)
    Returns None if line is a regular untracked log.
    """
    # 1. 429 RESOURCE_EXHAUSTED takes highest priority
    if EXHAUSTION_PATTERN.search(line):
        return EVENT_RESOURCE_EXHAUSTED

    # 2. Server startup / shutdown / lifecycle events
    if LIFECYCLE_PATTERN.search(line):
        return EVENT_LIFECYCLE

    # Clean glog preface if present
    cleaned = GLOG_PREFACE_PATTERN.sub("", line).strip()

    # 3. Glog severity flag (E or F)
    if GLOG_SEVERITY_PATTERN.search(cleaned):
        return EVENT_ERROR

    # 4. General error keywords
    if ERROR_PATTERN.search(cleaned):
        return EVENT_ERROR

    return None


def compute_event_fingerprint(ts_iso: str, line: str) -> str:
    """Generate deterministic SHA-256 fingerprint for a log event."""
    return hashlib.sha256(f"{ts_iso}:{line.strip()}".encode("utf-8")).hexdigest()


class LogArchiver:
    """
    Continuous tailer for language_server.log with truncation and rotation defense.
    Persists deduplicated 429, lifecycle, and error events into data/antigravity_vault.db.
    """

    def __init__(
        self,
        log_path: Optional[Union[str, Path]] = None,
        vault_path: Optional[Union[str, Path, sqlite3.Connection]] = None,
        default_year: Optional[int] = None,
    ):
        self.log_path = Path(log_path) if log_path else DEFAULT_LOG_PATH
        if isinstance(vault_path, sqlite3.Connection):
            self.vault_path: Union[Path, sqlite3.Connection] = vault_path
        elif vault_path:
            self.vault_path = Path(vault_path)
        else:
            self.vault_path = DEFAULT_VAULT_PATH

        self.default_year = default_year
        self.file_offset: int = 0
        self.last_size: int = 0
        self.last_inode: Optional[int] = None
        self._shared_conn: Optional[sqlite3.Connection] = None

    def _init_db(self, conn: sqlite3.Connection) -> None:
        """Ensure log_events_archive table and indexes exist."""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS log_events_archive (
                event_fingerprint TEXT PRIMARY KEY,
                timestamp_iso TEXT,
                event_type TEXT,
                raw_line TEXT,
                line_text TEXT,
                file_path TEXT,
                created_at TEXT
            );
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_log_events_ts 
            ON log_events_archive(timestamp_iso);
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_log_events_type 
            ON log_events_archive(event_type);
        """)
        conn.commit()

    def _get_connection(self) -> sqlite3.Connection:
        if isinstance(self.vault_path, sqlite3.Connection):
            self._init_db(self.vault_path)
            return self.vault_path
        if str(self.vault_path) == ":memory:":
            if self._shared_conn is None:
                self._shared_conn = sqlite3.connect(":memory:")
                self._init_db(self._shared_conn)
            return self._shared_conn

        self.vault_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.vault_path), timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        self._init_db(conn)
        return conn

    def poll(self) -> int:
        """
        Reads new lines from file_offset up to EOF.
        Updates file_offset, last_size, and last_inode.
        Detects file truncation or IDE restart when file size becomes smaller
        than file_offset (or inode changes), safely resetting file_offset = 0.
        Detects 429 RESOURCE_EXHAUSTED, lifecycle, and error events.
        Inserts events into log_events_archive table in data/antigravity_vault.db
        using INSERT OR IGNORE to guarantee deduplication.
        Returns count of newly inserted events.
        """
        if not self.log_path.exists():
            return 0

        try:
            stat = self.log_path.stat()
        except (PermissionError, OSError):
            return 0

        current_size = stat.st_size
        current_inode = getattr(stat, "st_ino", None)

        # Truncation or rotation / IDE restart detection
        is_truncated = False
        if current_size < self.file_offset:
            is_truncated = True
        elif self.last_inode is not None and current_inode != self.last_inode:
            is_truncated = True

        if is_truncated:
            self.file_offset = 0

        self.last_inode = current_inode
        self.last_size = current_size

        if current_size <= self.file_offset:
            return 0

        # Read new bytes up to EOF
        events_to_archive = []
        try:
            with open(self.log_path, "rb") as f:
                f.seek(self.file_offset)
                while True:
                    raw_line = f.readline()
                    if not raw_line:
                        break
                    line_str = raw_line.decode("utf-8", errors="replace")
                    stripped = line_str.strip()
                    if not stripped:
                        continue

                    event_type = classify_event(stripped)
                    if event_type:
                        dt = parse_timestamp(
                            stripped,
                            default_year=self.default_year,
                            mtime=stat.st_mtime,
                        )
                        ts_iso = dt.isoformat() if dt else ""
                        fingerprint = compute_event_fingerprint(ts_iso, stripped)
                        events_to_archive.append((fingerprint, ts_iso, event_type, stripped))

                self.file_offset = f.tell()
        except (PermissionError, OSError):
            return 0

        if not events_to_archive:
            return 0

        # Insert events into vault
        conn = self._get_connection()
        is_disk_conn = not isinstance(self.vault_path, sqlite3.Connection) and str(self.vault_path) != ":memory:"
        inserted_count = 0
        try:
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(log_events_archive)")
            existing_cols = {row[1] for row in cur.fetchall()}

            now_iso = datetime.now(timezone.utc).isoformat()
            for fingerprint, ts_iso, event_type, stripped in events_to_archive:
                candidate_values = {
                    "event_fingerprint": fingerprint,
                    "timestamp_iso": ts_iso,
                    "event_type": event_type,
                    "raw_line": stripped,
                    "line_text": stripped,
                    "message": stripped,
                    "file_path": str(self.log_path),
                    "created_at": now_iso,
                }
                cols = [c for c in existing_cols if c in candidate_values]
                if not cols:
                    continue
                placeholders = ", ".join(["?"] * len(cols))
                col_names = ", ".join(cols)
                sql = f"INSERT OR IGNORE INTO log_events_archive ({col_names}) VALUES ({placeholders})"
                cur.execute(sql, [candidate_values[c] for c in cols])
                if cur.rowcount > 0:
                    inserted_count += cur.rowcount

            conn.commit()
        finally:
            if is_disk_conn:
                conn.close()

        return inserted_count

    def get_archived_events(
        self,
        event_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Query archived log events from vault."""
        conn = self._get_connection()
        is_disk_conn = not isinstance(self.vault_path, sqlite3.Connection) and str(self.vault_path) != ":memory:"
        try:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            if event_type:
                cur.execute(
                    "SELECT * FROM log_events_archive WHERE event_type = ? ORDER BY timestamp_iso ASC",
                    (event_type,),
                )
            else:
                cur.execute("SELECT * FROM log_events_archive ORDER BY timestamp_iso ASC")
            return [dict(r) for r in cur.fetchall()]
        finally:
            if is_disk_conn:
                conn.close()

    def reset(self) -> None:
        """Reset tracking offsets to byte 0."""
        self.file_offset = 0
        self.last_size = 0
        self.last_inode = None

    def close(self) -> None:
        """Close any shared open connection."""
        if self._shared_conn:
            try:
                self._shared_conn.close()
            except Exception:
                pass
            self._shared_conn = None


def archive_logs(
    log_path: Optional[Union[str, Path]] = None,
    vault_path: Optional[Union[str, Path, sqlite3.Connection]] = None,
) -> int:
    """Helper function to instantiate a LogArchiver and perform a single poll."""
    archiver = LogArchiver(log_path=log_path, vault_path=vault_path)
    try:
        return archiver.poll()
    finally:
        archiver.close()


if __name__ == "__main__":
    count = archive_logs()
    print(f"Archived {count} new log events.")
