"""
IAMS Threshold Calibration Script

Grabs frames from the RTSP stream, runs face recognition on each detected
face, and analyzes score distributions to recommend optimal RECOGNITION_THRESHOLD
and RECOGNITION_MARGIN values for the current deployment environment.

Requires registered students to be standing in view of the camera during
calibration.

Usage:
    docker compose exec api-gateway python -m scripts.calibrate_threshold
    docker compose exec api-gateway python -m scripts.calibrate_threshold --frames 200
"""

import argparse
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings


def run_calibration(num_frames: int = 100, fps: float = 10.0) -> None:
    """Capture frames and analyze recognition score distributions."""

    # Late imports to avoid loading models at module level
    from app.services.frame_grabber import FrameGrabber
    from app.services.ml.faiss_manager import FAISSManager
    from app.services.ml.insightface_model import InsightFaceModel

    print("=" * 60)
    print("IAMS Threshold Calibration")
    print("=" * 60)

    # Initialize components
    print("\n[1/4] Loading models...")
    model = InsightFaceModel()
    model.load_model()

    faiss_mgr = FAISSManager()
    faiss_mgr.load_or_create_index()
    faiss_mgr.rebuild_user_map_from_db()

    index_size = faiss_mgr.index.ntotal if faiss_mgr.index else 0
    unique_users = len(set(faiss_mgr.user_map.values()))
    print(f"  FAISS index: {index_size} vectors, {unique_users} unique users")

    if index_size == 0:
        print("\n  ERROR: FAISS index is empty. Register faces first.")
        return

    # Start frame grabber
    rtsp_url = settings.DEFAULT_RTSP_URL
    if not rtsp_url:
        # Try to get from a room in the DB
        from app.models.room import Room

        db2 = SessionLocal()
        try:
            room = db2.query(Room).first()
            if room and room.rtsp_url:
                rtsp_url = room.rtsp_url
        finally:
            db2.close()

    if not rtsp_url:
        print("\n  ERROR: No RTSP URL configured. Set DEFAULT_RTSP_URL or add a room.")
        return

    print(f"\n[2/4] Connecting to RTSP stream: {rtsp_url}")
    grabber = FrameGrabber(
        rtsp_url=rtsp_url,
        fps=fps,
        width=settings.FRAME_GRABBER_WIDTH,
        height=settings.FRAME_GRABBER_HEIGHT,
    )
    # FrameGrabber auto-starts FFmpeg in __init__, wait for first frame
    time.sleep(2.0)
    test_frame = grabber.grab()
    if test_frame is None:
        print("  ERROR: No frames received. Check RTSP stream.")
        grabber.stop()
        return

    print(f"  Frame size: {test_frame.shape[1]}x{test_frame.shape[0]}")

    # Collect scores
    print(f"\n[3/4] Capturing {num_frames} frames...")
    genuine_scores: list[float] = []  # Top-1 matches (registered users)
    all_top1_scores: list[float] = []  # All top-1 scores
    all_gaps: list[float] = []  # top1 - top2 gaps
    frames_processed = 0
    faces_total = 0
    faces_matched = 0

    interval = 1.0 / fps
    try:
        for i in range(num_frames):
            frame = grabber.grab()
            if frame is None:
                time.sleep(interval)
                continue

            frames_processed += 1
            raw_faces = model.app.get(frame) if model.app else []

            for face in raw_faces:
                embedding = face.normed_embedding.copy()
                faces_total += 1

                # Search with no threshold to get raw scores
                results = faiss_mgr.search(embedding, k=3, threshold=0.0)

                if results:
                    top_user, top_score = results[0]
                    all_top1_scores.append(top_score)

                    if top_score >= 0.20:  # Loose filter for genuine-candidate scores
                        genuine_scores.append(top_score)
                        faces_matched += 1

                    if len(results) >= 2:
                        gap = top_score - results[1][1]
                        all_gaps.append(gap)

            if (i + 1) % 20 == 0:
                print(f"  {i + 1}/{num_frames} frames, {faces_total} faces detected, {faces_matched} potential matches")

            time.sleep(interval)
    finally:
        grabber.stop()

    # Analyze results
    print(f"\n[4/4] Analysis")
    print("-" * 60)
    print(f"  Frames processed: {frames_processed}")
    print(f"  Faces detected: {faces_total}")
    print(f"  Faces with top-1 >= 0.20: {faces_matched}")

    if not genuine_scores:
        print("\n  WARNING: No faces scored above 0.20.")
        print("  Make sure registered students are visible to the camera.")
        return

    genuine_arr = np.array(genuine_scores)
    all_arr = np.array(all_top1_scores)

    print(f"\n  Score distribution (all top-1 scores):")
    print(f"    Min:    {all_arr.min():.4f}")
    print(f"    Mean:   {all_arr.mean():.4f}")
    print(f"    Max:    {all_arr.max():.4f}")
    print(f"    Std:    {all_arr.std():.4f}")

    print(f"\n  Genuine match scores (top-1 >= 0.20):")
    print(f"    Min:    {genuine_arr.min():.4f}")
    print(f"    Mean:   {genuine_arr.mean():.4f}")
    print(f"    Max:    {genuine_arr.max():.4f}")
    print(f"    Std:    {genuine_arr.std():.4f}")

    if all_gaps:
        gap_arr = np.array(all_gaps)
        print(f"\n  Top-1 vs Top-2 gap:")
        print(f"    Min:    {gap_arr.min():.4f}")
        print(f"    Mean:   {gap_arr.mean():.4f}")
        print(f"    Max:    {gap_arr.max():.4f}")

    # Recommend threshold
    # Use 10th percentile of genuine scores as a conservative threshold
    recommended_threshold = float(np.percentile(genuine_arr, 10))
    # Clamp to reasonable range
    recommended_threshold = max(0.30, min(0.55, recommended_threshold))

    # Recommend margin based on gap distribution
    if all_gaps:
        gap_arr = np.array(all_gaps)
        recommended_margin = float(np.percentile(gap_arr, 25))
        recommended_margin = max(0.05, min(0.15, recommended_margin))
    else:
        recommended_margin = 0.10

    print(f"\n{'=' * 60}")
    print(f"  RECOMMENDATIONS")
    print(f"{'=' * 60}")
    print(f"  RECOGNITION_THRESHOLD = {recommended_threshold:.2f}")
    print(f"  RECOGNITION_MARGIN    = {recommended_margin:.2f}")
    print(f"\n  Current values:")
    print(f"  RECOGNITION_THRESHOLD = {settings.RECOGNITION_THRESHOLD}")
    print(f"  RECOGNITION_MARGIN    = {settings.RECOGNITION_MARGIN}")

    if abs(recommended_threshold - settings.RECOGNITION_THRESHOLD) > 0.03:
        print(f"\n  -> Threshold adjustment recommended!")
        print(f"     Set RECOGNITION_THRESHOLD={recommended_threshold:.2f} in your .env")
    else:
        print(f"\n  -> Current threshold looks good for this environment.")

    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IAMS Threshold Calibration")
    parser.add_argument(
        "--frames",
        type=int,
        default=100,
        help="Number of frames to capture (default: 100)",
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=10.0,
        help="Frame capture rate (default: 10.0)",
    )
    args = parser.parse_args()
    run_calibration(num_frames=args.frames, fps=args.fps)
