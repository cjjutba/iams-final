"""
Development Server Runner

Simple script to run the FastAPI application for development.
Automatically starts Redis and MediaMTX if not already running.

Usage:
    python run.py              # Single worker with auto-reload (default)
    python run.py --workers 4  # Multi-worker mode (no auto-reload)
"""

import atexit
import argparse
import os
import shutil
import signal
import subprocess
import sys

import uvicorn

_mediamtx_proc = None


def ensure_redis():
    """Start Redis if it's not already running."""
    try:
        result = subprocess.run(
            ["redis-cli", "ping"],
            capture_output=True, text=True, timeout=3
        )
        if result.stdout.strip() == "PONG":
            print("[run.py] Redis is already running")
            return
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    if not shutil.which("redis-server"):
        print("[run.py] redis-server not found — Redis features will be unavailable")
        return

    print("[run.py] Starting Redis...")
    subprocess.Popen(
        ["redis-server", "--daemonize", "yes"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    print("[run.py] Redis started")


def ensure_mediamtx():
    """Start MediaMTX if it's not already running."""
    global _mediamtx_proc

    # Check if already running on port 8554
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        s.connect(("127.0.0.1", 8554))
        s.close()
        print("[run.py] MediaMTX is already running (port 8554)")
        return
    except (ConnectionRefusedError, OSError):
        pass

    backend_dir = os.path.dirname(os.path.abspath(__file__))
    mediamtx_bin = os.path.join(backend_dir, "bin", "mediamtx")
    mediamtx_cfg = os.path.join(backend_dir, "mediamtx.yml")

    if not os.path.isfile(mediamtx_bin):
        print(f"[run.py] MediaMTX binary not found at {mediamtx_bin} — streaming will be unavailable")
        return

    if not os.path.isfile(mediamtx_cfg):
        print(f"[run.py] MediaMTX config not found at {mediamtx_cfg} — streaming will be unavailable")
        return

    print("[run.py] Starting MediaMTX...")
    _mediamtx_proc = subprocess.Popen(
        [mediamtx_bin, mediamtx_cfg],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print(f"[run.py] MediaMTX started (PID {_mediamtx_proc.pid})")


def _cleanup():
    """Stop MediaMTX on exit."""
    global _mediamtx_proc
    if _mediamtx_proc and _mediamtx_proc.poll() is None:
        print("[run.py] Stopping MediaMTX...")
        _mediamtx_proc.terminate()
        try:
            _mediamtx_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _mediamtx_proc.kill()
        print("[run.py] MediaMTX stopped")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IAMS Backend Server")
    parser.add_argument("--workers", type=int, default=1, help="Number of worker processes (default: 1)")
    args = parser.parse_args()

    ensure_redis()
    ensure_mediamtx()
    atexit.register(_cleanup)

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        workers=args.workers,
        reload=args.workers == 1,  # Auto-reload only in single-worker mode
        log_level="info",
    )
