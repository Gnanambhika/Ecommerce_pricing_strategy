"""End-to-end smoke test (works on Windows PowerShell, macOS and Linux).

1. Renders every page with Streamlit's AppTest and fails on any exception.
2. Starts a real headless Streamlit server and checks its health endpoint.

    python scripts/smoke_test.py
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGES = ["overview", "pricing", "discounts", "elasticity", "simulator", "data_quality"]


def render_pages() -> bool:
    os.environ.setdefault("STREAMLIT_LOGGER_LEVEL", "error")
    from streamlit.testing.v1 import AppTest

    ok = True
    for page in PAGES:
        at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120)
        at.run()
        if page != "overview":
            at.switch_page(str(ROOT / "src" / "pricing_intel" / "ui" / "pages" / f"{page}.py"))
            at.run()
        errors = [e.value for e in at.exception]
        status = "FAIL" if errors else "ok"
        print(f"  [{status}] page: {page}")
        for err in errors:
            print(f"        {err}")
        ok &= not errors
    return ok


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def server_health() -> bool:
    port = free_port()
    cmd = [sys.executable, "-m", "streamlit", "run", str(ROOT / "app.py"), "--server.headless", "true",
           "--server.port", str(port), "--server.address", "127.0.0.1"]
    env = {**os.environ, "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false"}
    proc = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, env=env)
    try:
        deadline = time.time() + 60
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/_stcore/health", timeout=2) as r:
                    if r.status == 200:
                        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5) as page:
                            body = page.read().decode("utf-8", "ignore")
                        print(f"  [ok] server healthy on port {port}; index page {len(body):,} bytes")
                        return True
            except OSError:
                time.sleep(1)
            if proc.poll() is not None:
                print("  [FAIL] server exited early:\n" + proc.stderr.read().decode("utf-8", "ignore")[-2000:])
                return False
        print("  [FAIL] server did not become healthy within 60 s")
        return False
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def main() -> int:
    print("Rendering pages with AppTest…")
    pages_ok = render_pages()
    print("Starting headless server…")
    server_ok = server_health()
    print("SMOKE TEST " + ("PASSED" if pages_ok and server_ok else "FAILED"))
    return 0 if pages_ok and server_ok else 1


if __name__ == "__main__":
    sys.exit(main())
