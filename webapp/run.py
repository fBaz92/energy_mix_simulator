"""Convenience launcher for the webapp (backend + frontend dev server).

Starts:
- FastAPI backend via uvicorn on port 8000.
- Vite dev server (frontend) on port 5173.

Vite proxies /api requests to the backend, so in development you only
need to open http://localhost:5173 in your browser.

Usage::

    python webapp/run.py

Requires ``npm install`` to have been run in ``webapp/frontend/``.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"


def main() -> None:
    """Start both backend and frontend dev servers."""
    if not (FRONTEND / "node_modules").exists():
        print("ERROR: frontend dependencies not installed.", file=sys.stderr)
        print(f"Run: cd {FRONTEND} && npm install", file=sys.stderr)
        sys.exit(1)

    backend_cmd = [
        sys.executable, "-m", "uvicorn",
        "webapp.backend.app:app",
        "--host", "127.0.0.1",
        "--port", "8000",
        "--reload",
    ]
    frontend_cmd = ["npm", "run", "dev"]

    print(">>> Starting FastAPI backend on http://127.0.0.1:8000")
    backend = subprocess.Popen(backend_cmd, cwd=ROOT.parent)

    print(">>> Starting Vite frontend on http://127.0.0.1:5173")
    frontend = subprocess.Popen(frontend_cmd, cwd=FRONTEND)

    print()
    print("Open http://localhost:5173 in your browser.")
    print("Press Ctrl+C to stop both servers.")

    def shutdown(signum, frame) -> None:
        """Graceful shutdown on SIGINT/SIGTERM."""
        _ = (signum, frame)
        print("\n>>> Shutting down...")
        for p in (frontend, backend):
            try:
                p.send_signal(signal.SIGTERM)
            except ProcessLookupError:
                pass
        for p in (frontend, backend):
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Wait for either process to exit
    while True:
        ret = backend.poll()
        if ret is not None:
            print(f"!!! Backend exited with code {ret}")
            shutdown(0, None)
        ret = frontend.poll()
        if ret is not None:
            print(f"!!! Frontend exited with code {ret}")
            shutdown(0, None)
        try:
            backend.wait(timeout=1)
        except subprocess.TimeoutExpired:
            continue


if __name__ == "__main__":
    main()
