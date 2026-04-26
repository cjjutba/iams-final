"""
IAMS Latency Benchmark

Measures the end-to-end face-recognition latency for the live CCTV pipeline
the same way Chapter 4 'Objective 2: ≤5 s' must be reported. Runs the
production SCRFD → ArcFace → FAISS path against a real RTSP stream for
N seconds and produces percentile timings plus an SLA-violation summary.

The realtime pipeline already ships per-frame timings over WebSocket
(``det_ms``, ``embed_ms``, ``faiss_ms``, ``other_ms``, ``processing_ms``,
``server_time_ms``, ``detected_at_ms``) — see
``backend/app/services/realtime_pipeline.py:_broadcast_frame_update``.
This benchmark is the offline counterpart: it reproduces the exact same
math without needing a live session, so the panel can read controlled,
reproducible numbers from a single test run.

Usage:

    # Use the configured RTSP URL of a room (looked up from DB by name):
    docker exec -it iams-api-gateway-onprem bash -lc \\
        "python -m scripts.latency_benchmark \\
            --room EB226 --duration 60"

    # Or specify the URL directly (no DB needed):
    python -m scripts.latency_benchmark \\
        --rtsp-url rtsp://host.docker.internal:8554/eb226 \\
        --duration 60

Stage definitions (matching production):

  1. SCRFD detection (``InsightFaceModel.detect``).
  2. ArcFace embedding for every detected face
     (``InsightFaceModel.embed_from_kps``). Total time grows linearly in
     N_faces; the report shows the per-frame total because that is the
     latency the live pipeline pays on each scan.
  3. FAISS similarity search.
  4. ``total_ms`` = stages 1 + 2 + 3 + small per-frame overhead.

End-to-end latency = ``total_ms`` + the camera-grab transport delay
(RTSP encode + network + FFmpeg drain). The benchmark approximates the
transport portion by recording how long each ``grab()`` blocked. The
production pipeline carries this same information across the wire as
``detected_at_ms`` so an admin overlay can compute
``(client_now_ms - detected_at_ms)`` for true wall-clock end-to-end.

Outputs (under ``reports/``):

  - ``latency_<timestamp>.csv``   per-frame timings
  - ``latency_<timestamp>.txt``   summary (percentiles + SLA verdict)
  - ``latency_<timestamp>.json``  the same summary as machine-readable JSON
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings  # noqa: E402

# Thesis Objective 2: end-to-end latency must not exceed this many seconds.
DEFAULT_SLA_MS = 5000.0


@dataclass
class FrameTiming:
    """One row of the per-frame CSV."""

    frame_index: int
    wall_time_iso: str
    grab_ms: float
    detect_ms: float
    embed_ms: float
    faiss_ms: float
    other_ms: float
    total_ms: float
    n_faces: int

    def end_to_end_ms(self) -> float:
        """grab + processing — close approximation of the SLA-relevant figure."""
        return self.grab_ms + self.total_ms


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    return float(np.percentile(values, pct))


def _resolve_rtsp_url(args) -> str:
    if args.rtsp_url:
        return args.rtsp_url

    from app.database import SessionLocal
    from app.models.room import Room

    db = SessionLocal()
    try:
        room = (
            db.query(Room)
            .filter((Room.name == args.room) | (Room.stream_key == args.room))
            .first()
        )
        if room is None:
            raise SystemExit(
                f"Room '{args.room}' not found and --rtsp-url was not provided."
            )
        url = (
            getattr(room, "rtsp_url", None)
            or getattr(room, "camera_endpoint", None)
            or getattr(room, "rtsp_main", None)
        )
        if not url:
            raise SystemExit(
                f"Room '{args.room}' has no RTSP URL configured. "
                "Set rtsp_url/camera_endpoint or pass --rtsp-url explicitly."
            )
        return url
    finally:
        db.close()


def _load_pipeline():
    from app.services.ml.faiss_manager import faiss_manager
    from app.services.ml.insightface_model import InsightFaceModel

    print("[1/3] Loading InsightFace model...")
    model = InsightFaceModel()
    model.load_model()

    print("[2/3] Loading FAISS index...")
    faiss_manager.load_or_create_index()
    faiss_manager.rebuild_user_map_from_db()
    if faiss_manager.index is None or faiss_manager.index.ntotal == 0:
        # The latency benchmark still works with an empty index — ArcFace
        # produces an embedding either way — but FAISS search is a no-op
        # with zero vectors which under-reports its real cost. Warn the
        # operator so they understand the timing.
        print(
            "      WARNING: FAISS index is empty — faiss_ms will read as ~0 ms. "
            "Register at least one face to get a representative number."
        )
    return model, faiss_manager


def _process_frame(model, faiss_manager, frame: np.ndarray) -> tuple[float, float, float, int]:
    """Run one frame through the production stages.

    Returns (detect_ms, embed_ms, faiss_ms, n_faces). ``embed_ms`` and
    ``faiss_ms`` aggregate across all detected faces in the frame.
    """
    t0 = time.perf_counter()
    detections = model.detect(frame)
    detect_ms = (time.perf_counter() - t0) * 1000.0

    embed_ms = 0.0
    faiss_ms = 0.0
    n_faces = len(detections)
    for det in detections:
        # Embed
        t1 = time.perf_counter()
        embedding = model.embed_from_kps(frame, det["kps"])
        embed_ms += (time.perf_counter() - t1) * 1000.0

        # FAISS search
        t2 = time.perf_counter()
        faiss_manager.search(embedding, k=2, threshold=0.0)
        faiss_ms += (time.perf_counter() - t2) * 1000.0

    return detect_ms, embed_ms, faiss_ms, n_faces


def _print_header(line: str) -> None:
    bar = "=" * 74
    print(bar)
    print(line)
    print(bar)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="IAMS face-recognition latency benchmark.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--room",
        type=str,
        default="EB226",
        help="Room name or stream_key to look up an RTSP URL from the DB. "
        "Ignored if --rtsp-url is given. Default: EB226.",
    )
    parser.add_argument(
        "--rtsp-url",
        type=str,
        default=None,
        help="Full RTSP URL to pull from. Overrides --room.",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=60.0,
        help="How many seconds to run the benchmark (default: 60).",
    )
    parser.add_argument(
        "--target-fps",
        type=float,
        default=settings.PROCESSING_FPS,
        help=f"Target processing rate in frames per second "
        f"(default: settings.PROCESSING_FPS={settings.PROCESSING_FPS}).",
    )
    parser.add_argument(
        "--sla-ms",
        type=float,
        default=DEFAULT_SLA_MS,
        help=f"Latency SLA in milliseconds (default: {DEFAULT_SLA_MS}; thesis Objective 2 = 5000).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports"),
        help="Directory to write CSV + summary (default: ./reports).",
    )
    parser.add_argument(
        "--warmup-seconds",
        type=float,
        default=3.0,
        help="Discard frames captured during this initial period (default: 3 s). "
        "Lets ONNX Runtime / CoreML JIT settle so the percentiles aren't "
        "polluted by first-call costs.",
    )
    args = parser.parse_args()

    rtsp_url = _resolve_rtsp_url(args)

    _print_header("IAMS Latency Benchmark")
    print(f"RTSP URL:        {rtsp_url}")
    print(f"Duration:        {args.duration:.1f} s "
          f"(plus {args.warmup_seconds:.1f} s warmup, discarded)")
    print(f"Target FPS:      {args.target_fps}")
    print(f"SLA:             {args.sla_ms:.0f} ms (thesis Objective 2)")

    model, faiss_manager = _load_pipeline()

    print(f"\n[3/3] Connecting to RTSP stream and benchmarking...")
    from app.services.frame_grabber import FrameGrabber

    grabber = FrameGrabber(
        rtsp_url=rtsp_url,
        fps=args.target_fps,
        width=settings.FRAME_GRABBER_WIDTH,
        height=settings.FRAME_GRABBER_HEIGHT,
    )

    # Wait for the first frame to be available before starting the timer.
    deadline = time.monotonic() + 15.0
    while time.monotonic() < deadline:
        first = grabber.grab()
        if first is not None:
            break
        time.sleep(0.2)
    else:
        grabber.stop()
        raise SystemExit(
            "Timed out waiting for the first frame. "
            "Check that mediamtx + ffmpeg-cam-relay are running."
        )

    print(f"      First frame: {first.shape[1]}×{first.shape[0]}")

    rows: list[FrameTiming] = []
    interval = 1.0 / args.target_fps if args.target_fps > 0 else 0.0
    warmup_until = time.monotonic() + args.warmup_seconds
    end_at = warmup_until + args.duration
    in_warmup = True

    try:
        idx = 0
        while True:
            now = time.monotonic()
            if now >= end_at:
                break
            if in_warmup and now >= warmup_until:
                in_warmup = False
                print("      Warmup complete — recording timings now.")

            grab_t0 = time.perf_counter()
            frame = grabber.grab()
            grab_ms = (time.perf_counter() - grab_t0) * 1000.0
            if frame is None:
                # No fresh frame yet — back off briefly and try again.
                time.sleep(interval if interval > 0 else 0.05)
                continue

            detect_ms, embed_ms, faiss_ms, n_faces = _process_frame(model, faiss_manager, frame)
            total_ms = detect_ms + embed_ms + faiss_ms
            other_ms = max(0.0, (time.perf_counter() - grab_t0) * 1000.0 - grab_ms - total_ms)

            if not in_warmup:
                idx += 1
                rows.append(
                    FrameTiming(
                        frame_index=idx,
                        wall_time_iso=datetime.now().isoformat(timespec="milliseconds"),
                        grab_ms=grab_ms,
                        detect_ms=detect_ms,
                        embed_ms=embed_ms,
                        faiss_ms=faiss_ms,
                        other_ms=other_ms,
                        total_ms=total_ms,
                        n_faces=n_faces,
                    )
                )
                if idx % 20 == 0:
                    print(
                        f"      Frame {idx}: total={total_ms:6.1f} ms "
                        f"(detect={detect_ms:5.1f}, embed={embed_ms:5.1f}, "
                        f"faiss={faiss_ms:5.1f}, faces={n_faces})"
                    )

            # Pace to target FPS so we don't out-run the camera.
            elapsed = (time.perf_counter() - grab_t0)
            sleep_for = max(0.0, interval - elapsed)
            if sleep_for > 0:
                time.sleep(sleep_for)
    finally:
        grabber.stop()

    if not rows:
        raise SystemExit(
            "No frames were captured. Verify the RTSP stream and try again."
        )

    # Aggregate
    end_to_end = [r.end_to_end_ms() for r in rows]
    detect = [r.detect_ms for r in rows]
    embed = [r.embed_ms for r in rows]
    faiss_lat = [r.faiss_ms for r in rows]
    grab = [r.grab_ms for r in rows]
    total = [r.total_ms for r in rows]
    n_faces_per_frame = [r.n_faces for r in rows]

    sla_violations = sum(1 for x in end_to_end if x > args.sla_ms)
    sla_pct = sla_violations / len(end_to_end) * 100.0
    sla_meets = sla_violations == 0

    # ─── Write outputs
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir: Path = args.output_dir
    csv_path = out_dir / f"latency_{timestamp}.csv"
    txt_path = out_dir / f"latency_{timestamp}.txt"
    json_path = out_dir / f"latency_{timestamp}.json"
    out_dir.mkdir(parents=True, exist_ok=True)

    with csv_path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "frame_index",
                "wall_time",
                "grab_ms",
                "detect_ms",
                "embed_ms",
                "faiss_ms",
                "other_ms",
                "total_ms",
                "end_to_end_ms",
                "n_faces",
            ]
        )
        for r in rows:
            w.writerow(
                [
                    r.frame_index,
                    r.wall_time_iso,
                    f"{r.grab_ms:.2f}",
                    f"{r.detect_ms:.2f}",
                    f"{r.embed_ms:.2f}",
                    f"{r.faiss_ms:.2f}",
                    f"{r.other_ms:.2f}",
                    f"{r.total_ms:.2f}",
                    f"{r.end_to_end_ms():.2f}",
                    r.n_faces,
                ]
            )

    def _fmt(values: list[float], unit: str = "ms") -> str:
        if not values:
            return "no data"
        p50 = _percentile(values, 50)
        p90 = _percentile(values, 90)
        p95 = _percentile(values, 95)
        p99 = _percentile(values, 99)
        return (
            f"min={min(values):7.1f} mean={statistics.mean(values):7.1f} "
            f"p50={p50:7.1f} p90={p90:7.1f} p95={p95:7.1f} p99={p99:7.1f} "
            f"max={max(values):7.1f} {unit}"
        )

    with txt_path.open("w") as fh:

        def w(line: str = "") -> None:
            fh.write(line + "\n")

        w("=" * 74)
        w("IAMS Latency Benchmark Report")
        w("=" * 74)
        w(f"Generated:    {datetime.now().isoformat(timespec='seconds')}")
        w(f"RTSP URL:     {rtsp_url}")
        w(f"Duration:     {args.duration:.1f} s   target FPS: {args.target_fps}")
        w(f"Warmup discarded: {args.warmup_seconds:.1f} s")
        w(f"Frames recorded:  {len(rows)}")
        w(f"Total faces seen: {sum(n_faces_per_frame)}  "
          f"(mean per frame: {statistics.mean(n_faces_per_frame):.2f})")
        w(f"Model:        {settings.INSIGHTFACE_MODEL} "
          f"(det_size={settings.INSIGHTFACE_DET_SIZE})")
        w("")
        w("-- Per-stage latency (ms) --")
        w(f"  Camera grab        : {_fmt(grab)}")
        w(f"  SCRFD detect       : {_fmt(detect)}")
        w(f"  ArcFace embed      : {_fmt(embed)}")
        w(f"  FAISS search       : {_fmt(faiss_lat)}")
        w(f"  Total processing   : {_fmt(total)}")
        w("")
        w("-- End-to-end latency (grab + processing) --")
        w(f"  {_fmt(end_to_end)}")
        w("")
        w("-- Faces detected per frame --")
        if n_faces_per_frame:
            w(f"  min={min(n_faces_per_frame)} max={max(n_faces_per_frame)} "
              f"mean={statistics.mean(n_faces_per_frame):.2f}")
        w("")
        w(f"-- SLA verdict: ≤ {args.sla_ms:.0f} ms (thesis Objective 2) --")
        w(f"  Frames over SLA:  {sla_violations} / {len(rows)}  ({sla_pct:.2f}%)")
        if sla_meets:
            w("  RESULT: PASS — every recorded frame finished within the SLA.")
        else:
            w("  RESULT: FAIL — some frames exceeded the SLA. Investigate the")
            w("          dominant stage above (probably 'SCRFD detect' on CPU).")
            w("          On Mac, verify the ML sidecar is running with CoreML")
            w("          providers (curl http://127.0.0.1:8001/health).")
        w("")
        w("Notes for Chapter 4:")
        w("  - End-to-end latency is the only number tied to the SLA.")
        w("    Per-stage timings exist to attribute root cause.")
        w("  - The live pipeline broadcasts the same stages over WebSocket")
        w("    (det_ms / embed_ms / faiss_ms / other_ms / detected_at_ms /")
        w("     server_time_ms) — see backend/app/services/realtime_pipeline.py")
        w("    in the _broadcast_frame_update method around line 396.")

    summary = {
        "generated_at": datetime.now().isoformat(),
        "rtsp_url": rtsp_url,
        "duration_s": args.duration,
        "target_fps": args.target_fps,
        "frames_recorded": len(rows),
        "total_faces": sum(n_faces_per_frame),
        "mean_faces_per_frame": statistics.mean(n_faces_per_frame) if n_faces_per_frame else 0.0,
        "model": settings.INSIGHTFACE_MODEL,
        "det_size": settings.INSIGHTFACE_DET_SIZE,
        "sla_ms": args.sla_ms,
        "sla_violations": sla_violations,
        "sla_violation_pct": sla_pct,
        "sla_pass": sla_meets,
        "stages_ms": {
            "grab": {
                "min": min(grab),
                "mean": statistics.mean(grab),
                "p50": _percentile(grab, 50),
                "p90": _percentile(grab, 90),
                "p95": _percentile(grab, 95),
                "p99": _percentile(grab, 99),
                "max": max(grab),
            },
            "detect": {
                "min": min(detect),
                "mean": statistics.mean(detect),
                "p50": _percentile(detect, 50),
                "p90": _percentile(detect, 90),
                "p95": _percentile(detect, 95),
                "p99": _percentile(detect, 99),
                "max": max(detect),
            },
            "embed": {
                "min": min(embed),
                "mean": statistics.mean(embed),
                "p50": _percentile(embed, 50),
                "p90": _percentile(embed, 90),
                "p95": _percentile(embed, 95),
                "p99": _percentile(embed, 99),
                "max": max(embed),
            },
            "faiss": {
                "min": min(faiss_lat),
                "mean": statistics.mean(faiss_lat),
                "p50": _percentile(faiss_lat, 50),
                "p90": _percentile(faiss_lat, 90),
                "p95": _percentile(faiss_lat, 95),
                "p99": _percentile(faiss_lat, 99),
                "max": max(faiss_lat),
            },
            "total_processing": {
                "min": min(total),
                "mean": statistics.mean(total),
                "p50": _percentile(total, 50),
                "p90": _percentile(total, 90),
                "p95": _percentile(total, 95),
                "p99": _percentile(total, 99),
                "max": max(total),
            },
            "end_to_end": {
                "min": min(end_to_end),
                "mean": statistics.mean(end_to_end),
                "p50": _percentile(end_to_end, 50),
                "p90": _percentile(end_to_end, 90),
                "p95": _percentile(end_to_end, 95),
                "p99": _percentile(end_to_end, 99),
                "max": max(end_to_end),
            },
        },
    }
    with json_path.open("w") as fh:
        json.dump(summary, fh, indent=2, default=str)

    print()
    _print_header("Done")
    print(f"  Per-frame CSV:  {csv_path}")
    print(f"  Summary text:   {txt_path}")
    print(f"  Summary JSON:   {json_path}")
    if sla_meets:
        print(f"  SLA verdict:    PASS  (0 / {len(rows)} frames over {args.sla_ms:.0f} ms)")
    else:
        print(f"  SLA verdict:    FAIL  ({sla_violations} / {len(rows)} frames over {args.sla_ms:.0f} ms)")
    print()


if __name__ == "__main__":
    main()
