"""
IAMS Threshold Calibration

Captures frames from one or more configured room cameras, runs SCRFD + ArcFace
on each detected face, queries the FAISS index with NO threshold, and
analyses the resulting (top-1, top-2) score distribution to recommend
defensible RECOGNITION_THRESHOLD and RECOGNITION_MARGIN values.

Limitations honestly stated:
  * This is unsupervised — there is no ground truth telling the script which
    detection corresponds to which student. The output is a *score
    distribution* over what the camera actually sees right now, not a
    precision/recall curve.
  * The "genuine" partition is heuristic: top-1 sims above
    GENUINE_FLOOR (default 0.30) are treated as plausible matches.
    Set GENUINE_FLOOR low enough to capture real CCTV-distance scores;
    high enough to exclude pure noise.
  * For a *true* calibration, run this with a controlled scene: only ONE
    enrolled student in front of the camera at a time, then aggregate
    multiple sessions. The CSV output supports that workflow.

Usage:
    docker exec iams-api-gateway-onprem python -m scripts.calibrate_threshold
    docker exec iams-api-gateway-onprem python -m scripts.calibrate_threshold --frames 200
    docker exec iams-api-gateway-onprem python -m scripts.calibrate_threshold --rooms eb226,eb227
    docker exec iams-api-gateway-onprem python -m scripts.calibrate_threshold --csv /tmp/calib.csv

Recommendations are printed; nothing is written back to the env file. Edit
backend/.env.onprem manually after reviewing the output.
"""

import argparse
import csv
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import logger, settings  # noqa: E402

GENUINE_FLOOR_DEFAULT = 0.30  # Floor for "plausible match" partition


def _resolve_room_streams(room_codes: list[str] | None) -> list[tuple[str, str]]:
    """Return (label, rtsp_url) for each room to sample from.

    If room_codes is None, samples every room that has a camera_endpoint.
    """
    from app.database import SessionLocal
    from app.models.room import Room

    db = SessionLocal()
    try:
        q = db.query(Room).filter(Room.camera_endpoint.isnot(None))
        if room_codes:
            q = q.filter(Room.code.in_(room_codes))
        rooms = q.all()
        return [(r.code or str(r.id), r.camera_endpoint) for r in rooms]
    finally:
        db.close()


def _per_user_summary(per_user_top1: dict[str, list[float]]) -> str:
    """Format per-user top-1 sim distribution as a tidy table."""
    if not per_user_top1:
        return "  (no per-user observations)"

    from app.database import SessionLocal
    from app.models.user import User

    db = SessionLocal()
    name_by_id: dict[str, str] = {}
    try:
        users = db.query(User).filter(User.id.in_(list(per_user_top1.keys()))).all()
        for u in users:
            name_by_id[str(u.id)] = (u.first_name or "") + " " + (u.last_name or "")
    finally:
        db.close()

    lines = ["  user                        n   min    p25    median p75    max"]
    lines.append("  " + "-" * 64)
    for user_id, sims in sorted(per_user_top1.items(), key=lambda kv: -np.mean(kv[1])):
        arr = np.array(sims)
        name = (name_by_id.get(user_id, "?") or "?")[:24]
        lines.append(
            f"  {name:<24}  {len(arr):3d}  "
            f"{arr.min():.3f}  {np.percentile(arr, 25):.3f}  "
            f"{np.median(arr):.3f}  {np.percentile(arr, 75):.3f}  {arr.max():.3f}"
        )
    return "\n".join(lines)


def run_calibration(
    num_frames: int,
    fps: float,
    room_codes: list[str] | None,
    csv_path: str | None,
    genuine_floor: float,
) -> int:
    # Late imports so config / logging is set up first
    from app.services.frame_grabber import FrameGrabber
    from app.services.ml.faiss_manager import faiss_manager
    from app.services.ml.insightface_model import insightface_model

    print("=" * 64)
    print("IAMS Threshold Calibration")
    print("=" * 64)

    # 1. Load model + index
    print("\n[1/5] Loading models + FAISS index...")
    insightface_model.load_model()
    faiss_manager.load_or_create_index()
    faiss_manager.rebuild_user_map_from_db()

    index_size = faiss_manager.index.ntotal if faiss_manager.index else 0
    unique_users = len(set(faiss_manager.user_map.values()))
    print(f"      FAISS: {index_size} vectors, {unique_users} unique users")

    if index_size == 0:
        print("\n  ERROR: FAISS index is empty. Register faces first.")
        return 1

    # 2. Resolve which cameras to sample
    print("\n[2/5] Resolving rooms to sample...")
    streams = _resolve_room_streams(room_codes)
    if not streams:
        if room_codes:
            print(f"  ERROR: None of {room_codes} have a camera_endpoint set.")
        else:
            print("  ERROR: No rooms with camera_endpoint configured.")
        return 1
    for label, url in streams:
        print(f"      {label}: {url}")

    # 3. Capture
    print(f"\n[3/5] Capturing {num_frames} frames per camera at {fps} fps...")
    print(f"      Using genuine floor = {genuine_floor:.2f} (top-1 sims above this count as plausible matches)")

    rows: list[dict] = []  # raw observations for CSV
    per_user_top1: dict[str, list[float]] = defaultdict(list)
    all_top1: list[float] = []
    all_gaps: list[float] = []
    all_top2: list[float] = []
    impostor_candidates: list[float] = []  # top-1 sims below genuine_floor

    for label, rtsp_url in streams:
        print(f"\n  ── {label} ──")
        grabber = FrameGrabber(
            rtsp_url=rtsp_url,
            fps=fps,
            width=settings.FRAME_GRABBER_WIDTH,
            height=settings.FRAME_GRABBER_HEIGHT,
        )
        try:
            time.sleep(2.0)  # let ffmpeg warm up
            test = grabber.grab()
            if test is None:
                print(f"  WARN: no frames from {label}, skipping")
                continue

            interval = 1.0 / fps
            frames_done = 0
            faces_done = 0
            for i in range(num_frames):
                frame = grabber.grab()
                if frame is None:
                    time.sleep(interval)
                    continue
                frames_done += 1

                raw_faces = (
                    insightface_model.app.get(frame) if insightface_model.app else []
                )
                for face in raw_faces:
                    embedding = face.normed_embedding.copy()
                    # Search with NO threshold — we want raw scores
                    results = faiss_manager.search(embedding, k=3, threshold=0.0)
                    if not results:
                        continue
                    faces_done += 1

                    top_user, top_sim = results[0]
                    second_sim = results[1][1] if len(results) > 1 else 0.0
                    gap = top_sim - second_sim

                    all_top1.append(top_sim)
                    all_top2.append(second_sim)
                    all_gaps.append(gap)

                    if top_sim >= genuine_floor:
                        per_user_top1[top_user].append(top_sim)
                    else:
                        impostor_candidates.append(top_sim)

                    rows.append({
                        "room": label,
                        "frame_idx": i,
                        "det_score": float(face.det_score),
                        "bbox_w": int(face.bbox[2] - face.bbox[0]),
                        "bbox_h": int(face.bbox[3] - face.bbox[1]),
                        "top1_user": top_user,
                        "top1_sim": float(top_sim),
                        "top2_sim": float(second_sim),
                        "gap": float(gap),
                    })

                if (i + 1) % 25 == 0:
                    print(f"    {i + 1}/{num_frames} frames, {faces_done} face observations")

                time.sleep(interval)

            print(f"  {label} done: {frames_done} frames processed, {faces_done} face observations")
        finally:
            grabber.stop()

    if not all_top1:
        print("\n  ERROR: no face observations collected. Make sure students are visible.")
        return 1

    # 4. Analyse
    print("\n[4/5] Analysis")
    print("-" * 64)
    arr_top1 = np.array(all_top1)
    arr_top2 = np.array(all_top2)
    arr_gap = np.array(all_gaps)
    arr_imp = np.array(impostor_candidates) if impostor_candidates else None

    print(f"  Total face observations: {len(arr_top1)}")
    print(f"  Plausible-genuine (top-1 >= {genuine_floor:.2f}): {sum(arr_top1 >= genuine_floor)}")
    print(f"  Impostor candidates (top-1 <  {genuine_floor:.2f}): {sum(arr_top1 <  genuine_floor)}")
    print()
    print("  All top-1 sims:")
    print(f"    min={arr_top1.min():.3f}  p10={np.percentile(arr_top1, 10):.3f}  "
          f"p50={np.median(arr_top1):.3f}  p90={np.percentile(arr_top1, 90):.3f}  "
          f"max={arr_top1.max():.3f}")
    print("  All top-1 vs top-2 gaps:")
    print(f"    min={arr_gap.min():.3f}  p25={np.percentile(arr_gap, 25):.3f}  "
          f"p50={np.median(arr_gap):.3f}  p75={np.percentile(arr_gap, 75):.3f}  "
          f"max={arr_gap.max():.3f}")
    if arr_imp is not None and len(arr_imp) > 0:
        print("  Impostor-candidate top-1 sims (these should NOT clear the threshold):")
        print(f"    min={arr_imp.min():.3f}  p50={np.median(arr_imp):.3f}  "
              f"p95={np.percentile(arr_imp, 95):.3f}  max={arr_imp.max():.3f}")

    print("\n  Per-user top-1 distribution (genuine partition only):")
    print(_per_user_summary(per_user_top1))

    # 5. Recommendations
    # Threshold heuristic:
    #   - Lower bound: 95th-percentile of impostor-candidate top-1 sims (or
    #     0.30 if there were none) — anything below this is provably noise.
    #   - Upper bound: 10th-percentile of plausible-genuine sims, so 90 % of
    #     real faces still match.
    #   - Choose the higher (more conservative) of the two; clamp to [0.35, 0.55].
    p10_genuine = (
        np.percentile(np.concatenate(list(per_user_top1.values())), 10)
        if per_user_top1
        else float(np.percentile(arr_top1, 10))
    )
    p95_impostor = (
        np.percentile(arr_imp, 95) if arr_imp is not None and len(arr_imp) > 0 else 0.30
    )
    rec_thresh = float(min(p10_genuine, max(p95_impostor + 0.02, 0.35)))
    rec_thresh = max(0.35, min(0.55, rec_thresh))

    # Margin: 25th-percentile of all gaps so 75 % of decisions clear it
    rec_margin = float(np.percentile(arr_gap, 25))
    rec_margin = max(0.05, min(0.20, rec_margin))

    print("\n[5/5] RECOMMENDATIONS")
    print("=" * 64)
    print(f"  RECOGNITION_THRESHOLD = {rec_thresh:.2f}   (currently {settings.RECOGNITION_THRESHOLD})")
    print(f"  RECOGNITION_MARGIN    = {rec_margin:.2f}   (currently {settings.RECOGNITION_MARGIN})")
    print()
    print("  How these were chosen:")
    print(f"    - p10 of plausible-genuine top-1 sims:   {p10_genuine:.3f}")
    print(f"    - p95 of impostor-candidate top-1 sims:  {p95_impostor:.3f}")
    print(f"    - p25 of top-1 vs top-2 gaps:            {rec_margin:.3f}")
    print()
    print("  If the per-user table shows a user with median sim < threshold,")
    print("  that user needs CCTV-side re-enrollment (scripts/cctv_enroll.py).")

    # Optional CSV
    if csv_path:
        with open(csv_path, "w", newline="") as f:
            w = csv.DictWriter(
                f,
                fieldnames=["room", "frame_idx", "det_score", "bbox_w", "bbox_h",
                            "top1_user", "top1_sim", "top2_sim", "gap"],
            )
            w.writeheader()
            w.writerows(rows)
        print(f"\n  Raw observations written to: {csv_path}")
    print()
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IAMS Threshold Calibration")
    parser.add_argument("--frames", type=int, default=100,
                        help="Frames per camera (default: 100)")
    parser.add_argument("--fps", type=float, default=10.0,
                        help="Capture rate (default: 10.0)")
    parser.add_argument("--rooms", type=str, default="",
                        help="Comma-separated room codes (default: all rooms with camera_endpoint)")
    parser.add_argument("--csv", type=str, default="",
                        help="Optional path to write per-observation CSV")
    parser.add_argument("--genuine-floor", type=float, default=GENUINE_FLOOR_DEFAULT,
                        help=f"Top-1 sim above this counts as a plausible match (default: {GENUINE_FLOOR_DEFAULT})")
    args = parser.parse_args()

    room_codes = [c.strip() for c in args.rooms.split(",") if c.strip()] or None
    csv_path = args.csv.strip() or None

    try:
        sys.exit(
            run_calibration(
                num_frames=args.frames,
                fps=args.fps,
                room_codes=room_codes,
                csv_path=csv_path,
                genuine_floor=args.genuine_floor,
            )
        )
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(130)
    except Exception:
        logger.exception("Calibration failed")
        sys.exit(1)
