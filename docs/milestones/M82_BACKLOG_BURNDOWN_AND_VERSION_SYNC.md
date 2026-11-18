# Milestone 82: Backlog Burndown, Token Compliance & Manifest Sync (Rows 8–13)

**Date**: 2026-09-29
**Scope**: Rows 8 through 13 from `docs/HANDOVER.md` & `docs/AUDIT_2026-09-29_SYSTEM_PERFORMANCE_AND_UX.md`
**Branch**: `main`
**Verdict**: **PASS**

---

## 1. Overview & Context

This milestone resolves all remaining open backlog items identified in the 2026-09-29 system performance and UX audit:
- **Row 8 (C5 / P2)**: Deduplicate redundant `sync_conversations_to_vault` in watcher daemon loop.
- **Row 9 (U4 / P2)**: Add `tabindex="0"`, `role="region"`, and unique `aria-label`s to mobile scrollable tables and unmask `scrollable-region-focusable` in `e2e/a11y.spec.js`.
- **Row 10 (D1 / P2)**: Replace all banned `border-radius: 9999px` instances with canonical design tokens (`var(--radius-card, 6px)` and `--radius-pill`).
- **Row 11 (D2 / P2)**: Migrate all embedded raw hex color literals in `dashboard/js/*.js` to semantic CSS custom properties.
- **Row 12 (D3 / P2)**: Synchronize version declarations across `package.json`, `pyproject.toml`, and Git tags to `2.25.0`.
- **Row 13 (D4 / P3)**: Decompose `dashboard/js/plan-manager.js` and `dashboard/js/core.js` so all JavaScript files in `dashboard/js/` strictly comply with ADR-066 (`<= 750` lines).

---

## 2. Changes Implemented

- **`scripts/watch_telemetry.py` & `scripts/export_dashboard.py` (Row 8 / C5)**:
  - Removed duplicate `sync_vault_telemetry` scan prior to `export_telemetry`, ensuring conversation vault synchronization runs strictly 1x per export cycle.
- **`dashboard/index.html` & `dashboard/styles.css` (Rows 9 & 10)**:
  - Equipped 16 horizontal overflow table containers with `role="region"`, `tabindex="0"`, focus indicators, and descriptive `aria-label`s.
  - Replaced all 6 occurrences of `border-radius: 9999px` with `var(--radius-card, 6px)` and `--radius-pill`.
- **`dashboard/js/*.js` (Row 11 / D2)**:
  - Migrated 68 raw hex color codes across 8 frontend modules to CSS custom properties (`--accent-green`, `--accent-purple`, `--camel-500`, `--status-alert`, etc.).
- **`dashboard/js/plan-rates.js`, `plan-manager.js`, `core.js`, `core-utils.js` (Row 13 / D4)**:
  - Extracted `MODEL_TAXONOMY`, `resolveModelDisplay`, `getModelSortRank`, and `renderRateHistoryTable` into `dashboard/js/plan-rates.js` (205 lines), dropping `plan-manager.js` to 622 lines.
  - Delegated shell mode controllers to `dashboard/js/core-utils.js`, dropping `core.js` to 732 lines.
  - Registered `dashboard/js/plan-rates.js` in `docs/REPO_MAP.md`.
- **`package.json`, `pyproject.toml`, Git tag (Row 12 / D3)**:
  - Synchronized versions to `2.25.0` and tagged `HEAD` with `v2.25.0`.

---

## 3. Acceptance Gates

| Gate # | Description | Check Command | Expected | Verdict |
| :---: | :--- | :--- | :--- | :--- |
| G1 | Watcher vault sync deduplication (Row 8) | `python3 -c "import inspect, scripts.watch_telemetry; src=inspect.getsource(scripts.watch_telemetry.watch_loop); assert src.count('sync_conversations_to_vault') == 0; print('OK')"` | `OK` | PASS |
| G2 | Zero banned 9999px border-radius (Row 10) | `python3 -c "import pathlib; text = pathlib.Path('dashboard/styles.css').read_text() + pathlib.Path('dashboard/index.html').read_text(); assert '9999px' not in text; print('OK')"` | `OK` | PASS |
| G3 | Zero raw hex color codes in JS (Row 11) | `python3 -c "import pathlib, re; js_files = list(pathlib.Path('dashboard/js').glob('*.js')); raw = [f.name for f in js_files if re.search(r'#[0-9a-fA-F]{3,8}\b', f.read_text())]; assert len(raw) == 0; print('OK')"` | `OK` | PASS |
| G4 | Manifest & Git version alignment to 2.25.0 (Row 12) | `python3 -c "import json, tomllib, pathlib, subprocess; tag=subprocess.check_output(['git','describe','--tags','--abbrev=0']).decode().strip().lstrip('v'); py_ver=tomllib.loads(pathlib.Path('pyproject.toml').read_text())['project']['version']; js_ver=json.loads(pathlib.Path('package.json').read_text())['version']; assert tag==py_ver==js_ver=='2.25.0'; print('OK')"` | `OK` | PASS |
| G5 | All dashboard JS modules <= 750 lines (Row 13) | `python3 -c "import pathlib; max_lines = max(len(p.read_text().splitlines()) for p in pathlib.Path('dashboard/js').glob('*.js')); assert max_lines <= 750; print('OK')"` | `OK` | PASS (max 732 lines) |
| G6 | Full unit test suite passes | `python3 -m unittest discover -s tests` | `392 passed, < 90s` | PASS (392 passed in 55.3s) |
| G7 | Full quality gate passes | `git diff --check && python3 -m unittest tests/test_docs_integrity.py && python3 scripts/build_demo_showcase.py && npx playwright test e2e/dashboard-boot.spec.js` | `OK` | PASS |
