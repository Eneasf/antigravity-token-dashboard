# VDONE — Active Acceptance Gates
Active branch: (run `git rev-parse --abbrev-ref HEAD`; never write it here)

## A. Always-on gates (run by tests/test_vdone_gates.py and by CI)
A1 Unit suite            CHECK python3 -m unittest discover -s tests -p 'test_*.py'      EXPECT OK, < 90 s
A2 Docs integrity        CHECK python3 -m unittest tests.test_docs_integrity                               EXPECT OK
A3 Model roster          CHECK python3 -m unittest tests.test_model_roster_integrity                       EXPECT OK
A4 No stale numbers      CHECK python3 -m unittest tests.test_docs_integrity -k test_stale_numbers          EXPECT OK
A5 Fixture determinism   CHECK python3 -c "import tempfile, subprocess, pathlib, shutil; d1, d2 = tempfile.mkdtemp(), tempfile.mkdtemp(); [subprocess.run(['python3', 'scripts/export_dashboard.py', '--antigravity-dir', 'tests/fixtures/antigravity', '--no-live-quota', '--reference-time', '2026-09-05T14:30:00Z', '--output-dir', d], check=True, capture_output=True) for d in (d1, d2)]; f1 = pathlib.Path(d1)/'data.json'; f2 = pathlib.Path(d2)/'data.json'; assert f1.read_bytes() == f2.read_bytes() and len(f1.read_bytes()) > 0; shutil.rmtree(d1); shutil.rmtree(d2)"   EXPECT OK

## §B. Current milestone gates
<!-- Empty between milestones -->
