# Contributing to Antigravity Token Consumption Dashboard

Thank you for your interest in contributing! This project provides offline, deterministic telemetry analytics, rolling quota modeling, and a visual dashboard for Google Antigravity workspaces.

---

## 0. Feature Proposals & Alignment (Discuss First)

To respect everyone's time and avoid wasted effort:
- **Small fixes & calibrations**: Bug fixes, documentation clarifications, and new model IDs in `config/pricing.json` can be submitted directly via Pull Request.
- **New features & architectural changes**: Please **open an Issue first** to discuss your proposal and reach alignment with the maintainers *before* writing code. Pull Requests introducing unaligned major features, UI redesigns, or new subsystems may be closed without review.
- **Maintainer Discretion**: As maintainers, we prioritize simplicity, zero external dependencies, and low maintenance overhead. If a proposed feature falls outside our core roadmap, we may decline it. Under the MIT License, you are always welcome and encouraged to maintain custom enhancements in your personal fork!

---

## 1. Core Architectural Invariants

Before submitting a Pull Request, please ensure your contribution adheres to our core architectural invariants:

1. **Zero External Runtime Dependencies (ADR-001 / ADR-002)**:
   - The engine, parsers, and telemetry extractors use **100% pure Python standard library** (`sqlite3`, `json`, `pathlib`, `re`, `datetime`, `urllib.request`).
   - PRs introducing third-party runtime dependencies (e.g., `requests`, `numpy`, `pandas`, `protobuf`) will be declined to preserve offline security, speed, and supply-chain safety.
2. **Strict Read-Only SQLite Access (ADR-001)**:
   - All connections to Antigravity databases must use URI read-only syntax (`sqlite3.connect(f'file:{path}?mode=ro', uri=True)`) to prevent blocking or corrupting live IDE sessions.
3. **Byte-Deterministic Output (ADR-004)**:
   - Exporter scripts must generate byte-identical output given identical inputs. Do not introduce wall-clock timestamps or unordered dictionary iteration into generated files.
4. **Decoupled User Data (ADR-024)**:
   - Personal telemetry databases, incident ledgers, and local vaults must never be committed to git. Use `data/exhaustion_ledger.sample.json` as a template.

---

## 2. Setting Up & Testing

### Running Tests
The project uses Python's built-in `unittest` framework:
```bash
python3 -m unittest discover -s tests
```
All tests must pass cleanly before opening a Pull Request.

### Verifying Dashboard Export
To ensure the dashboard exporter runs cleanly:
```bash
python3 scripts/export_dashboard.py
```

---

## 3. Contributing New Model Calibrations

Google regularly releases new model IDs in Antigravity. We actively welcome PRs calibrating new models!

1. Check your `language_server.log` or SQLite `steps.metadata` for the numeric `model_id`.
2. Update [`config/pricing.json`](config/pricing.json) with the model's display name, family (`gemini`, `claude_gpt`), reasoning tier, and pricing per million tokens.
3. Add a unit test or verify `tests/test_quota_client.py` passes cleanly.

---

## 4. Git Commit Hygiene

We enforce the [Conventional Commits](https://www.conventionalcommits.org/) standard for clear, readable project history:
- `feat(component): description`
- `fix(component): description`
- `docs(component): description`
- `refactor(component): description`
- `test(component): description`
- `chore(component): description`

---

## 5. Scope & Platform Support

- **Primary Platform**: This tool is authored and maintained primarily for **macOS** (utilizing macOS LaunchAgents for the background watcher).
- **Linux & Windows**: Contributions adding cross-platform support (e.g., `systemd` user units, Windows Task Scheduler scripts, or path normalization) are warmly welcome, provided they maintain the zero-dependency invariant and pass existing tests.
