"""
Development Server Runner

Simple script to run the FastAPI application for development.
Usage:
    python run.py              # Single worker with auto-reload (default)
    python run.py --workers 4  # Multi-worker mode (no auto-reload)
"""

import argparse
import uvicorn

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IAMS Backend Server")
    parser.add_argument("--workers", type=int, default=1, help="Number of worker processes (default: 1)")
    args = parser.parse_args()

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        workers=args.workers,
        reload=args.workers == 1,  # Auto-reload only in single-worker mode
        log_level="info",
    )
