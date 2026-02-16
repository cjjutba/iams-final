"""
Push Email Templates to Supabase

Reads HTML templates from backend/templates/emails/ and pushes them
to the Supabase project via the Management API.

Requires SUPABASE_ACCESS_TOKEN (personal access token) in .env.
Generate one at: https://supabase.com/dashboard/account/tokens

Usage:
    python -m scripts.push_email_templates          # Push all templates
    python -m scripts.push_email_templates --dry-run # Preview without pushing
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import json
import subprocess
from app.config import settings

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates" / "emails"

# Map: template file name → (subject field, content field)
TEMPLATE_MAP = {
    "confirmation.html": (
        "mailer_subjects_confirmation",
        "mailer_templates_confirmation_content",
    ),
    "recovery.html": (
        "mailer_subjects_recovery",
        "mailer_templates_recovery_content",
    ),
}

# Default subjects (can be overridden per-template via front-matter later)
SUBJECTS = {
    "confirmation.html": "Confirm your IAMS account",
    "recovery.html": "Reset your IAMS password",
}


def get_project_ref() -> str:
    """Extract project ref from SUPABASE_URL (e.g. https://xxxxx.supabase.co → xxxxx)."""
    url = settings.SUPABASE_URL
    # https://fspnxqmewtxmuyqqwwni.supabase.co → fspnxqmewtxmuyqqwwni
    return url.replace("https://", "").split(".")[0]


def push_templates(dry_run: bool = False) -> None:
    token = getattr(settings, "SUPABASE_ACCESS_TOKEN", "")
    if not token:
        print("ERROR: SUPABASE_ACCESS_TOKEN is not set in .env")
        print("Generate one at: https://supabase.com/dashboard/account/tokens")
        sys.exit(1)

    project_ref = get_project_ref()
    api_url = f"https://api.supabase.com/v1/projects/{project_ref}/config/auth"

    print(f"Project ref: {project_ref}")
    print(f"Templates dir: {TEMPLATES_DIR}")
    print()

    payload = {}

    for filename, (subject_key, content_key) in TEMPLATE_MAP.items():
        filepath = TEMPLATES_DIR / filename
        if not filepath.exists():
            print(f"  SKIP  {filename} (file not found)")
            continue

        html = filepath.read_text(encoding="utf-8")
        subject = SUBJECTS.get(filename, "")

        payload[subject_key] = subject
        payload[content_key] = html

        print(f"  LOAD  {filename}")
        print(f"         Subject: {subject}")
        print(f"         Size: {len(html)} bytes")

    if not payload:
        print("\nNo templates found to push.")
        return

    if dry_run:
        print(f"\n[DRY RUN] Would push {len(payload) // 2} template(s) to Supabase.")
        print("Run without --dry-run to apply.")
        return

    print(f"\nPushing {len(payload) // 2} template(s) to Supabase...")

    # Use curl with -4 (IPv4) to avoid IPv6 SSL issues on some networks
    result = subprocess.run(
        [
            "curl.exe", "-4", "-s",
            "-X", "PATCH", api_url,
            "-H", f"Authorization: Bearer {token}",
            "-H", "Content-Type: application/json",
            "-d", json.dumps(payload),
            "-w", "\n%{http_code}",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    lines = result.stdout.strip().rsplit("\n", 1)
    status_code = int(lines[-1]) if len(lines) > 1 else 0

    if status_code == 200:
        print("SUCCESS — Email templates updated!")
    else:
        print(f"FAILED — HTTP {status_code}")
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
        sys.exit(1)


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    push_templates(dry_run=dry_run)
