"""
IAMS FAISS Index Rebuild

Wipes the in-memory FAISS index and rebuilds it strictly from canonical
embeddings stored in the database (face_embeddings table, fallback to the
legacy face_registrations.embedding_vector). Optionally purges volatile
"adaptive" embeddings that the realtime tracker may have appended.

This is the recovery path when:
  * RECOGNITION_THRESHOLD has been changed and you want a fresh,
    uncorrupted index to evaluate it against.
  * Adaptive enrollment was previously enabled and may have written
    wrong-identity vectors into the index (see the 2026-04-25 identity-swap
    incident — the on-prem deployment had Desiree's face crop appended to
    Ivy Leah's identity cluster after a stable lock-in on a wrong match).
  * The index file on disk has gotten out of sync with the DB (orphaned
    vectors, dangling user_map entries) — the health check at the end
    will surface this.

Usage:
    docker exec iams-api-gateway-onprem python -m scripts.rebuild_faiss
    docker exec iams-api-gateway-onprem python -m scripts.rebuild_faiss --dry-run
    docker exec iams-api-gateway-onprem python -m scripts.rebuild_faiss --notify

Flags:
    --dry-run  Print what would change but don't write the new index file.
    --notify   After rebuild, publish a Redis "faiss_reload" event so other
               api-gateway workers reload the index without a restart.
               Off by default — the script's normal use case is one-shot
               recovery while the api-gateway is restarted right after.

Exit codes:
    0  Index rebuilt (or dry-run completed) successfully.
    1  No active embeddings in DB — the rebuilt index would be empty.
       The on-disk file is left untouched in this case to avoid silently
       wiping a working index when the DB read failed.
    2  FAISS health check after rebuild reported orphaned vectors or
       dangling user_map entries — investigate before trusting recognition.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import logger, settings  # noqa: E402


def run_rebuild(dry_run: bool = False, notify: bool = False) -> int:
    # Late imports so config / logging is set up first
    from app.database import SessionLocal
    from app.repositories.face_repository import FaceRepository
    from app.services.face_service import FaceService
    from app.services.ml.faiss_manager import faiss_manager

    print("=" * 64)
    print("IAMS FAISS Index Rebuild")
    print("=" * 64)
    print(f"  Index path:       {settings.FAISS_INDEX_PATH}")
    print(f"  Adaptive enabled: {settings.ADAPTIVE_ENROLL_ENABLED}")
    print(f"  Threshold:        {settings.RECOGNITION_THRESHOLD}")
    print(f"  Margin:           {settings.RECOGNITION_MARGIN}")
    print(f"  Dry run:          {dry_run}")
    print(f"  Notify reload:    {notify}")
    print()

    # 1. Load the current index (if any) so we can report before/after
    print("[1/5] Loading current FAISS index from disk...")
    faiss_manager.load_or_create_index()
    pre_total = faiss_manager.index.ntotal if faiss_manager.index else 0
    pre_adaptive = len(faiss_manager._adaptive_ids)
    print(f"      Existing vectors: {pre_total}")
    print(f"      Of which adaptive (volatile): {pre_adaptive}")
    print()

    # 2. Collect canonical embeddings from the DB
    print("[2/5] Collecting canonical embeddings from DB...")
    db = SessionLocal()
    try:
        repo = FaceRepository(db)
        embeddings_data = FaceService._collect_embeddings_static(repo)
    finally:
        db.close()

    db_count = len(embeddings_data)
    unique_users = len({uid for _, uid in embeddings_data})
    print(f"      DB embeddings:     {db_count}")
    print(f"      Unique users:      {unique_users}")
    print()

    if db_count == 0:
        print("  ERROR: No active embeddings in DB. Refusing to wipe the index.")
        print("  If this is a fresh install with no registrations, ignore — the")
        print("  index is created lazily on first registration.")
        return 1

    # 3. Wipe + rebuild
    if dry_run:
        delta = db_count - (pre_total - pre_adaptive)
        print("[3/5] DRY RUN — would rebuild now.")
        print(f"      Delta: {delta:+d} canonical vectors vs current non-adaptive.")
        print(f"      Would discard {pre_adaptive} adaptive vector(s).")
        print()
        print("[4/5] DRY RUN — skipped save.")
        print("[5/5] DRY RUN — skipped health check.")
        return 0

    print("[3/5] Rebuilding FAISS index from canonical embeddings...")
    # rebuild() also clears _adaptive_ids implicitly (new index, fresh state)
    new_map = faiss_manager.rebuild(embeddings_data)
    # After rebuild, adaptive IDs are stale (they referenced the old index).
    # Defensive clear so a stale list never confuses later add_adaptive() calls.
    faiss_manager._adaptive_ids.clear()
    print(f"      Rebuilt with {len(new_map)} vectors.")
    print()

    # 4. (rebuild() already saved + may have published, but be explicit)
    print("[4/5] Persisting index to disk...")
    faiss_manager.save()
    print(f"      Wrote {settings.FAISS_INDEX_PATH}.")
    if notify:
        # Best-effort publish so any other api-gateway workers reload.
        # This must happen inside an event loop for asyncio.create_task to
        # succeed; if there is no running loop, fall back to a synchronous run.
        import asyncio

        try:
            asyncio.run(faiss_manager.notify_index_changed())
            print("      Published Redis faiss_reload notification.")
        except Exception as exc:
            print(f"      WARN: notify failed: {exc}")
    print()

    # 5. Health check
    print("[5/5] Health check...")
    health = faiss_manager.check_health()
    for key, value in health.items():
        print(f"      {key}: {value}")
    if not health.get("healthy", False):
        print()
        print("  WARNING: index reports unhealthy state. Investigate before")
        print("  relying on recognition results.")
        return 2

    print()
    print("=" * 64)
    print("  Rebuild complete.")
    print(f"  Vectors: {pre_total} → {faiss_manager.index.ntotal}")
    print(f"  Adaptive purged: {pre_adaptive}")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rebuild FAISS index from DB")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing the new index.",
    )
    parser.add_argument(
        "--notify",
        action="store_true",
        help="Publish faiss_reload event so other workers reload (requires Redis).",
    )
    args = parser.parse_args()

    try:
        sys.exit(run_rebuild(dry_run=args.dry_run, notify=args.notify))
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(130)
    except Exception:
        logger.exception("Rebuild failed")
        sys.exit(1)
