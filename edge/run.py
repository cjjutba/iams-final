#!/usr/bin/env python3
"""
IAMS Edge Device Entry Point

Run the edge device application.

Usage:
    python run.py
    python -m edge.run

Environment:
    Configure via .env file in edge/ directory.
    See .env.example for required variables.
"""

import sys
from pathlib import Path

# Add app directory to Python path
app_dir = Path(__file__).parent / "app"
sys.path.insert(0, str(app_dir))

from app.main import main

if __name__ == "__main__":
    main()
