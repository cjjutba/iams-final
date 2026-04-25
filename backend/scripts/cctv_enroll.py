"""
IAMS CCTV-Side Enrolment

Augments an existing student's phone-captured face registration with
embeddings drawn from the actual CCTV stream. This closes the
phone→CCTV cross-domain gap that ArcFace cannot bridge with selfie-only
training data, and is the primary mitigation against the type of
identity-swap incident captured in lessons.md (2026-04-25).

Workflow:
  1. Stand the target student alone in front of the chosen camera so
     exactly ONE face is visible. Multiple faces in the frame will
     cause the script to skip — it cannot tell which face belongs to
     the user_id you pass.
  2. Run this script. The capture loop grabs frames, filters to
     usable detections (det_score and face-size thresholds), and
     captures `--captures` (default 5) embeddings spaced
     `--interval` seconds apart so the student can shift pose
     between captures.
  3. Verify with `scripts/calibrate_threshold.py --rooms <code>` —
     after enrolment the per-user table should show this student
     scoring well above the threshold consistently.

Usage:
  docker exec iams-api-gateway-onprem python -m scripts.cctv_enroll \\
      --user-id 11111111-2222-3333-4444-555555555555 \\
      --room EB226 --captures 5

Common arguments:
  --user-id     UUID of the student to enrol (required)
  --room        Room code (e.g. "EB226") OR Room UUID (required)
  --captures    Number of embeddings to add (default: 5, max: 10)
  --interval    Seconds between successful captures (default: 1.0)
  --min-size    Min face short-edge in pixels (default: 60)
  --min-det     Min SCRFD detection confidence (default: 0.65)

Exit codes:
  0   Captures committed.
  1   Validation error (no existing registration, room not found, no
      usable captures, or sanity-check rejected the captures as
      not-this-user).
  2   Internal error during persistence — the FAISS index will have
      been rolled back automatically; check logs.
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import logger, settings  # noqa: E402


async def _run(args) -> int:
    # Late imports so logging is initialised first
    from app.database import SessionLocal
    from app.services.face_service import FaceService
    from app.services.ml.faiss_manager import faiss_manager
    from app.services.ml.insightface_model import insightface_model
    from app.utils.exceptions import FaceRecognitionError, ValidationError

    print("=" * 64)
    print("IAMS CCTV-Side Enrolment")
    print("=" * 64)
    print(f"  user_id:         {args.user_id}")
    print(f"  room:            {args.room}")
    print(f"  captures:        {args.captures}")
    print(f"  interval:        {args.interval} s")
    print(f"  min face size:   {args.min_size} px")
    print(f"  min det score:   {args.min_det}")
    print(f"  RECOG_THRESHOLD: {settings.RECOGNITION_THRESHOLD}")
    print()

    # Make sure ML + FAISS are loaded (the api-gateway lifespan does this,
    # but a CLI invocation has its own process)
    print("[1/3] Loading model + FAISS index...")
    insightface_model.load_model()
    faiss_manager.load_or_create_index()
    faiss_manager.rebuild_user_map_from_db()
    print(f"      FAISS: {faiss_manager.index.ntotal} vectors")
    print()

    print("[2/3] Capturing — keep ONE student in front of the camera...")
    db = SessionLocal()
    try:
        face_service = FaceService(db)
        try:
            result = await face_service.cctv_enroll(
                user_id=args.user_id,
                room_code_or_id=args.room,
                num_captures=args.captures,
                capture_interval=args.interval,
                min_face_size_px=args.min_size,
                min_det_score=args.min_det,
            )
        except ValidationError as exc:
            print(f"\n  ERROR (validation): {exc}")
            return 1
        except FaceRecognitionError as exc:
            print(f"\n  ERROR (internal): {exc}")
            return 2
    finally:
        db.close()

    print()
    print("[3/3] Done.")
    print("=" * 64)
    print(f"  Added:                       {result['added']}")
    print(f"  FAISS IDs:                   {result['faiss_ids']}")
    print(f"  Labels:                      {result['labels']}")
    print(f"  Frames attempted:            {result['attempts']}")
    print(f"  Skipped reasons:             {result['skipped_reasons']}")
    print(f"  Sim to phone (mean/min/max): "
          f"{result['self_similarity_to_phone_mean']:.3f} / "
          f"{result['self_similarity_to_phone_min']:.3f} / "
          f"{result['self_similarity_to_phone_max']:.3f}")
    print()
    if result['self_similarity_to_phone_mean'] < 0.40:
        print("  WARNING: mean sim to phone embedding is low.")
        print("  The captures landed in this user's vector cluster, but only")
        print("  weakly. Consider re-running with a closer / better-lit camera")
        print("  framing, or running scripts/calibrate_threshold.py to confirm")
        print("  the user now scores above RECOGNITION_THRESHOLD reliably.")
    else:
        print("  Looks good. Verify with: python -m scripts.calibrate_threshold")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IAMS CCTV-side enrolment")
    parser.add_argument("--user-id", required=True, help="Student UUID")
    parser.add_argument("--room", required=True, help="Room code (e.g. EB226) or UUID")
    parser.add_argument("--captures", type=int, default=5, help="Number of embeddings (1-10)")
    parser.add_argument("--interval", type=float, default=1.0, help="Seconds between captures")
    parser.add_argument("--min-size", type=int, default=60, help="Minimum face short-edge in pixels")
    parser.add_argument("--min-det", type=float, default=0.65, help="Minimum SCRFD det_score")
    args = parser.parse_args()

    try:
        sys.exit(asyncio.run(_run(args)))
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(130)
    except Exception:
        logger.exception("cctv_enroll failed")
        sys.exit(2)
