#!/usr/bin/env python3
"""
capture_showcase_screenshots.py

Generates high-resolution, privacy-safe Light Mode UI screenshots for README.md and OpenGraph cards.

Architecture & Isolation Guarantees:
1. Stages dashboard static assets (`index.html`, `styles.css`, `favicon.ico`, `js/`) inside an
   isolated `tempfile.TemporaryDirectory()` so live `dashboard/data.js` and `dashboard/meta.js`
   can NEVER bleed into screenshots.
2. Populates synthetic `data.js`, `meta.js`, and `turns.js` directly via
   `scripts.build_demo_showcase.write_demo_files()`, matching the GitHub Pages showcase 1-for-1.
3. Serves the isolated directory over an ephemeral loopback `ThreadingHTTPServer(("127.0.0.1", 0))`
   and captures crisp Light Mode screenshots via headless Chrome:
   - docs/assets/showcase_hero_quotas.png
   - docs/assets/showcase_swarm_lineage.png
   - docs/assets/showcase_simulator.png
   - docs/assets/showcase_projects_branches.png
   - docs/assets/showcase_turns_inspector.png
   - docs/assets/github_social_preview.png
   - dashboard/og-card.png
"""

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.build_demo_showcase import write_demo_files  # noqa: E402


DASHBOARD_DIR = REPO_ROOT / "dashboard"
ASSETS_DIR = REPO_ROOT / "docs" / "assets"
CHROME_BIN = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


class _QuietHandler(SimpleHTTPRequestHandler):
    """Silence HTTP request logs during automated screenshot capture."""

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        pass


def capture_url(
    url: str,
    output_path: Path,
    width: int = 1440,
    height: int = 900,
    virtual_time_budget_ms: int = 2500,
) -> None:
    """Invoke headless Chrome to render and capture a URL in Light Mode."""
    if output_path.exists():
        output_path.unlink()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    profile_dir = tempfile.mkdtemp(prefix="chrome_shot_")
    cmd = [
        CHROME_BIN,
        "--headless=new",
        "--disable-gpu",
        "--no-first-run",
        "--hide-scrollbars",
        "--force-device-scale-factor=1.5",
        f"--virtual-time-budget={virtual_time_budget_ms}",
        f"--user-data-dir={profile_dir}",
        f"--window-size={width},{height}",
        f"--screenshot={output_path}",
        url,
    ]
    print(f"[*] Capturing {output_path.relative_to(REPO_ROOT)} ({width}x{height})...")
    try:
        subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30.0,
            check=False,
        )
    except subprocess.TimeoutExpired:
        print(f"[!] Warning: Chrome screenshot timed out after 30s: {output_path.name}", file=sys.stderr)
    finally:
        shutil.rmtree(profile_dir, ignore_errors=True)

    if not output_path.exists() or output_path.stat().st_size <= 5000:
        raise RuntimeError(f"Failed to capture {output_path.name}")


def stage_isolated_showcase(stage_dir: Path) -> None:
    """Populate stage_dir with clean static assets and 100% synthetic demo telemetry."""
    shutil.copy2(DASHBOARD_DIR / "styles.css", stage_dir / "styles.css")
    if (DASHBOARD_DIR / "favicon.ico").exists():
        shutil.copy2(DASHBOARD_DIR / "favicon.ico", stage_dir / "favicon.ico")
    shutil.copytree(DASHBOARD_DIR / "js", stage_dir / "js")

    write_demo_files(
        out_data_path=stage_dir / "data.js",
        out_meta_path=stage_dir / "meta.js",
        out_turns_path=stage_dir / "turns.js",
    )

    raw_html = (DASHBOARD_DIR / "index.html").read_text(encoding="utf-8")
    raw_html = raw_html.replace('<html lang="en">', '<html lang="en" data-theme="light" class="light">')

    # Preload turns.js and force light theme + scroll helper for deterministic view framing
    helper_snippet = """
  <script src="turns.js"></script>
  <script>
    try { localStorage.setItem("antigravity_dashboard_theme", "light"); } catch (e) {}
    document.documentElement.setAttribute("data-theme", "light");
    document.documentElement.classList.remove("dark");
    document.documentElement.classList.add("light");
    window.addEventListener("load", function() {
      try {
        var params = new URLSearchParams(window.location.search);
        if (params.get("focus_turns") === "1") {
          if (typeof switchTab === "function") switchTab("tab-sessions");
          var convos = (window.globalDashboardData && window.globalDashboardData.conversations) || [];
          if (convos.length > 0 && typeof openTurnsDrawer === "function") {
            openTurnsDrawer(convos[0]);
          }
        }
        if (params.get("focus_sim") === "1") {
          if (typeof switchTab === "function") switchTab("tab-plan");
          var hydroBtn = document.querySelector('[data-preset="hydrogen_xhigh_sprint"]');
          if (hydroBtn && typeof hydroBtn.click === "function") {
            hydroBtn.click();
          }
        }
      } catch (e) {}
    });
  </script>
"""
    staged_html = raw_html.replace("</head>", helper_snippet + "</head>", 1)
    (stage_dir / "index.html").write_text(staged_html, encoding="utf-8")


def main() -> None:
    if not Path(CHROME_BIN).exists():
        print(f"[!] Error: Google Chrome binary not found at {CHROME_BIN}", file=sys.stderr)
        sys.exit(1)

    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="agy_showcase_stage_") as tmp:
        stage_dir = Path(tmp)
        stage_isolated_showcase(stage_dir)

        handler = partial(_QuietHandler, directory=str(stage_dir))
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        base_url = f"http://127.0.0.1:{port}/index.html"
        try:
            # 1. Hero Executive Cockpit & Quota Bento (Now tab)
            capture_url(f"{base_url}?tab=tab-now", ASSETS_DIR / "showcase_hero_quotas.png", width=1440, height=920)

            # 2. GitHub Social Preview & OpenGraph Card
            capture_url(f"{base_url}?tab=tab-now", ASSETS_DIR / "github_social_preview.png", width=1280, height=640)
            capture_url(f"{base_url}?tab=tab-now", DASHBOARD_DIR / "og-card.png", width=1200, height=630)

            # 3. Autonomous Subagent Swarm Lineage DAG Explorer
            capture_url(f"{base_url}?tab=tab-swarms", ASSETS_DIR / "showcase_swarm_lineage.png", width=1440, height=880)

            # 4. Interactive What-If Workload Simulator & Plan Rates
            capture_url(f"{base_url}?tab=tab-plan&focus_sim=1", ASSETS_DIR / "showcase_simulator.png", width=1440, height=880)

            # 5. Workspace Portfolio & Git Branch Attribution (expanded first project)
            capture_url(
                f"{base_url}?tab=tab-projects&expand_project=0",
                ASSETS_DIR / "showcase_projects_branches.png",
                width=1440,
                height=860,
            )

            # 6. Turn-by-Turn Telemetry, Wire TTFT & Thinking Token Inspector
            capture_url(
                f"{base_url}?tab=tab-sessions&focus_turns=1",
                ASSETS_DIR / "showcase_turns_inspector.png",
                width=1440,
                height=860,
            )
        finally:
            server.shutdown()
            server.server_close()

    print("\n✓ Captured all isolated Light Mode showcase assets successfully.")


if __name__ == "__main__":
    main()
