# Milestone 69: Watcher Thread Lock & Tempfile Safety (C3)

**Date**: 2026-09-26
**Scope**: Row 3 (C3) from `docs/HANDOVER.md` §4 & `docs/AUDIT_2026-09-26_BACKEND_AND_PIPELINES.md`
**Branch**: `fix/watcher-thread-lock-temp-safety`
**Verdict**: **PASS**

---

## 1. Overview & Context

Audit finding `C3` identified that `update_watcher_heartbeat` in `scripts/watch_telemetry.py` used a hardcoded temporary file name (`.{target.name}.tmp.{os.getpid()}`) without thread locking. When the 10-second daemon heartbeat thread and event-triggered updates in the main watcher thread coincided, both wrote to the exact same temporary file concurrently, resulting in race conditions, corrupted JSON, or `FileNotFoundError` during `os.replace`.

---

## 2. Changes Implemented

- **`scripts/watch_telemetry.py`**:
  - Added module-level `_status_lock = threading.Lock()` to serialize status writes within the process.
  - Guarded `update_watcher_heartbeat` with `with _status_lock:`.
  - Replaced fixed temporary file name with an isolated, unique tempfile per thread and write attempt: `.{target.name}.tmp.{os.getpid()}_{threading.get_ident()}_{nonce}`, incorporating process ID, thread identifier, and an 8-character hex nonce (`uuid.uuid4().hex[:8]`).
  - Added error cleanup ensuring unlinked temporary files on replace failure.

- **`tests/test_watch_telemetry.py`**:
  - Added `test_update_watcher_heartbeat_concurrent_writes` validating 50 concurrent heartbeat updates from 8 worker threads against pre-seeded status.
  - Added `test_update_watcher_heartbeat_replace_error_cleanup` verifying temporary file unlinking when `os.replace` fails.

---

## 3. Acceptance Gates (§B)

| Gate # | Check Command | Expected | Verdict |
| :---: | :--- | :--- | :---: |
| B1 | `python3 -c "import concurrent.futures, pathlib, json; from scripts.watch_telemetry import update_watcher_heartbeat; p=pathlib.Path('/tmp/test_race_status.json'); ex=concurrent.futures.ThreadPoolExecutor(max_workers=8); futs=[ex.submit(update_watcher_heartbeat, p) for _ in range(50)]; res=[f.result() for f in futs]; ex.shutdown(wait=True); assert all(res); d=json.loads(p.read_text()); assert 'watcher' in d; p.unlink(); print('OK')"` | `OK` | PASS |

Tested with: `ThreadPoolExecutor(max_workers=8)` submitting 50 concurrent `update_watcher_heartbeat` invocations with `assert all(res)`, verified to exit with code 1 on base commit `3e3b0cd` and exit 0 (`OK`) on branch HEAD `e68d280`.
