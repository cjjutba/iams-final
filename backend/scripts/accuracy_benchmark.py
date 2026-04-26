"""
IAMS Accuracy Benchmark

Computes the precision/recall/F1 numbers your thesis panel will demand for
Chapter 4. Loads the production model + FAISS index, runs a directory of
labeled test photos through the same SCRFD → ArcFace → FAISS pipeline that
the live CCTV pipeline uses, and produces:

  - reports/accuracy_<timestamp>.csv     (one row per test photo)
  - reports/accuracy_<timestamp>.txt     (summary stats + threshold sweep)

Test photo directory layout:

    test_photos/
      <student_uuid_1>/         # genuine photos of registered student #1
        photo1.jpg
        photo2.jpg
      <student_uuid_2>/         # genuine photos of registered student #2
        ...
      impostors/                # OPTIONAL: photos of UNREGISTERED faces
        stranger1.jpg           # used to measure False Match Rate
        stranger2.jpg

Each subdirectory name MUST be a registered user UUID (the same UUID stored
in the FAISS index). Use ``users/student-record-detail`` in the admin
portal to copy student UUIDs. The special ``impostors/`` directory holds
photos of people who are NOT in the FAISS index and is used to compute
False Match Rate (FMR).

Usage:

    # On the Mac, with the on-prem stack running:
    docker exec -it iams-api-gateway-onprem bash -lc \\
        "python -m scripts.accuracy_benchmark \\
            --photos-dir /workspace/test_photos \\
            --threshold 0.38"

    # Or natively on the host (requires the same venv as the ML sidecar):
    cd backend && python -m scripts.accuracy_benchmark \\
        --photos-dir ../test_photos --threshold 0.38

The script does NOT need the FastAPI gateway running. It opens its own
DB connection only to load the FAISS user map, then runs entirely
in-process with the same models.

Metrics produced (per threshold):

  - Genuine Accept Rate (GAR / TPR): genuine photos correctly matched to
    their owner above threshold.
  - False Non-Match Rate (FNMR): genuine photos REJECTED (similarity below
    threshold) or matched to a DIFFERENT user.
  - False Match Rate (FMR): impostor photos that crossed the threshold and
    were assigned an identity (false positive).
  - Rank-1 Identification Accuracy: % of genuine photos where the correct
    user was top-1 in FAISS, regardless of threshold.
  - Precision / Recall / F1:
        precision = TP / (TP + FP)        TP = genuine matched to self
        recall    = TP / (TP + FN)        FP = impostor matched
        F1        = 2 * P * R / (P + R)   FN = genuine missed or mis-matched
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

import cv2
import numpy as np

# Ensure ``backend/`` is on sys.path when running as a script
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings  # noqa: E402

# Threshold sweep covers the realistic ArcFace cosine-similarity range.
# 0.30 is below the production floor; 0.50 is well above. The span lets the
# panel see how the chosen threshold balances FMR vs FNMR.
DEFAULT_SWEEP = (0.30, 0.32, 0.34, 0.36, 0.38, 0.40, 0.42, 0.45, 0.50)

VALID_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


@dataclass
class PhotoResult:
    """One row in the per-photo CSV."""

    photo_path: str
    truth_user_id: str | None  # None for impostors
    is_impostor: bool
    detected: bool
    top1_user_id: str | None
    top1_similarity: float | None
    top2_user_id: str | None
    top2_similarity: float | None
    margin: float | None  # top1 - top2
    detect_ms: float
    embed_ms: float
    faiss_ms: float

    def decision_for_threshold(self, threshold: float) -> str:
        """Classify this photo at a given threshold.

        Returns one of:
          - "TP"   genuine, top-1 == truth and similarity >= threshold
          - "FN"   genuine, top-1 != truth OR similarity < threshold
          - "FP"   impostor, top-1 similarity >= threshold (matched someone)
          - "TN"   impostor, top-1 similarity <  threshold (correctly rejected)
          - "ND"   no face detected in the photo
        """
        if not self.detected:
            return "ND"
        if self.is_impostor:
            if self.top1_similarity is not None and self.top1_similarity >= threshold:
                return "FP"
            return "TN"
        # genuine
        if (
            self.top1_user_id == self.truth_user_id
            and self.top1_similarity is not None
            and self.top1_similarity >= threshold
        ):
            return "TP"
        return "FN"


def _print_header(line: str) -> None:
    bar = "=" * 74
    print(bar)
    print(line)
    print(bar)


def _load_pipeline():
    """Load InsightFace + FAISS the same way the production gateway does."""
    from app.services.ml.faiss_manager import faiss_manager
    from app.services.ml.insightface_model import InsightFaceModel

    print("[1/3] Loading InsightFace model...")
    model = InsightFaceModel()
    model.load_model()

    print("[2/3] Loading FAISS index...")
    faiss_manager.load_or_create_index()
    faiss_manager.rebuild_user_map_from_db()

    index_size = faiss_manager.index.ntotal if faiss_manager.index else 0
    unique_users = len(set(faiss_manager.user_map.values()))
    print(f"      FAISS index: {index_size} vectors across {unique_users} unique users")
    if index_size == 0:
        raise SystemExit("FAISS index is empty — no faces have been registered.")

    return model, faiss_manager


def _list_genuine_photos(photos_dir: Path) -> list[tuple[str, Path]]:
    """Walk photos_dir and return [(truth_user_id, photo_path), ...].

    Each immediate subdirectory whose name is NOT ``impostors`` is treated as
    a user_id. All image files inside are tagged with that user_id as truth.
    """
    items: list[tuple[str, Path]] = []
    for sub in sorted(photos_dir.iterdir()):
        if not sub.is_dir() or sub.name == "impostors":
            continue
        for f in sorted(sub.iterdir()):
            if f.is_file() and f.suffix.lower() in VALID_EXTS:
                items.append((sub.name, f))
    return items


def _list_impostor_photos(photos_dir: Path) -> list[Path]:
    """Return all impostor photo paths under photos_dir/impostors/."""
    impostor_dir = photos_dir / "impostors"
    if not impostor_dir.is_dir():
        return []
    out: list[Path] = []
    for f in sorted(impostor_dir.iterdir()):
        if f.is_file() and f.suffix.lower() in VALID_EXTS:
            out.append(f)
    return out


def _process_photo(
    model,
    faiss_manager,
    photo_path: Path,
    truth_user_id: str | None,
) -> PhotoResult:
    """Run one photo through SCRFD → ArcFace → FAISS and return a result row.

    Returns a PhotoResult with detected=False (and other fields None) when
    SCRFD finds no face — those count toward "no detection" in the report
    rather than as a false negative, so the panel can see how often photo
    quality is the limiting factor.
    """
    bgr = cv2.imread(str(photo_path))
    if bgr is None:
        # Treat unreadable file as "not detected" but flag it
        return PhotoResult(
            photo_path=str(photo_path),
            truth_user_id=truth_user_id,
            is_impostor=truth_user_id is None,
            detected=False,
            top1_user_id=None,
            top1_similarity=None,
            top2_user_id=None,
            top2_similarity=None,
            margin=None,
            detect_ms=0.0,
            embed_ms=0.0,
            faiss_ms=0.0,
        )

    # Stage 1: SCRFD detection
    t0 = time.perf_counter()
    detections = model.detect(bgr)
    detect_ms = (time.perf_counter() - t0) * 1000.0

    if not detections:
        return PhotoResult(
            photo_path=str(photo_path),
            truth_user_id=truth_user_id,
            is_impostor=truth_user_id is None,
            detected=False,
            top1_user_id=None,
            top1_similarity=None,
            top2_user_id=None,
            top2_similarity=None,
            margin=None,
            detect_ms=detect_ms,
            embed_ms=0.0,
            faiss_ms=0.0,
        )

    # Pick the highest-confidence face if multiple are detected. For a
    # registration-style headshot there is normally only one. For test
    # photos that happen to have a bystander, this matches the heuristic
    # the registration path uses (largest/most-confident face).
    detections.sort(key=lambda d: d["det_score"], reverse=True)
    best = detections[0]

    # Stage 2: ArcFace embedding from 5-point landmarks
    t1 = time.perf_counter()
    embedding = model.embed_from_kps(bgr, best["kps"])
    embed_ms = (time.perf_counter() - t1) * 1000.0

    # Stage 3: FAISS search (top-2 so we can also report margin)
    t2 = time.perf_counter()
    results = faiss_manager.search(embedding, k=2, threshold=0.0)
    faiss_ms = (time.perf_counter() - t2) * 1000.0

    top1_uid = top1_sim = top2_uid = top2_sim = None
    if results:
        top1_uid, top1_sim = results[0]
        if len(results) > 1:
            top2_uid, top2_sim = results[1]

    margin = (top1_sim - top2_sim) if (top1_sim is not None and top2_sim is not None) else None

    return PhotoResult(
        photo_path=str(photo_path),
        truth_user_id=truth_user_id,
        is_impostor=truth_user_id is None,
        detected=True,
        top1_user_id=top1_uid,
        top1_similarity=float(top1_sim) if top1_sim is not None else None,
        top2_user_id=top2_uid,
        top2_similarity=float(top2_sim) if top2_sim is not None else None,
        margin=float(margin) if margin is not None else None,
        detect_ms=detect_ms,
        embed_ms=embed_ms,
        faiss_ms=faiss_ms,
    )


def _summarise_at_threshold(
    results: list[PhotoResult],
    threshold: float,
) -> dict:
    """Compute counts + rates at one threshold."""
    counts = {"TP": 0, "FN": 0, "FP": 0, "TN": 0, "ND": 0}
    for r in results:
        counts[r.decision_for_threshold(threshold)] += 1

    n_genuine = counts["TP"] + counts["FN"]
    n_impostor = counts["FP"] + counts["TN"]

    gar = (counts["TP"] / n_genuine) if n_genuine else None
    fnmr = (counts["FN"] / n_genuine) if n_genuine else None
    fmr = (counts["FP"] / n_impostor) if n_impostor else None

    tp = counts["TP"]
    fp = counts["FP"]
    fn = counts["FN"]
    precision = (tp / (tp + fp)) if (tp + fp) else None
    recall = (tp / (tp + fn)) if (tp + fn) else None
    f1 = (
        (2 * precision * recall / (precision + recall))
        if (precision and recall)
        else None
    )

    return {
        "threshold": threshold,
        "counts": counts,
        "n_genuine": n_genuine,
        "n_impostor": n_impostor,
        "GAR": gar,
        "FNMR": fnmr,
        "FMR": fmr,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def _rank1_accuracy(results: list[PhotoResult]) -> float | None:
    """Identification rank-1 accuracy ignoring threshold.

    Of all GENUINE photos that were detected, what fraction had the correct
    user_id as the top-1 FAISS result?
    """
    genuine_detected = [r for r in results if not r.is_impostor and r.detected]
    if not genuine_detected:
        return None
    correct = sum(1 for r in genuine_detected if r.top1_user_id == r.truth_user_id)
    return correct / len(genuine_detected)


def _format_pct(v: float | None) -> str:
    return f"{v * 100:6.2f}%" if v is not None else "    --"


def _write_csv(results: list[PhotoResult], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "photo_path",
                "truth_user_id",
                "is_impostor",
                "detected",
                "top1_user_id",
                "top1_similarity",
                "top2_user_id",
                "top2_similarity",
                "margin",
                "detect_ms",
                "embed_ms",
                "faiss_ms",
            ]
        )
        for r in results:
            w.writerow(
                [
                    r.photo_path,
                    r.truth_user_id or "",
                    "1" if r.is_impostor else "0",
                    "1" if r.detected else "0",
                    r.top1_user_id or "",
                    f"{r.top1_similarity:.6f}" if r.top1_similarity is not None else "",
                    r.top2_user_id or "",
                    f"{r.top2_similarity:.6f}" if r.top2_similarity is not None else "",
                    f"{r.margin:.6f}" if r.margin is not None else "",
                    f"{r.detect_ms:.2f}",
                    f"{r.embed_ms:.2f}",
                    f"{r.faiss_ms:.2f}",
                ]
            )


def _write_summary(
    results: list[PhotoResult],
    sweep: tuple[float, ...],
    primary_threshold: float,
    out_path: Path,
    photos_dir: Path,
) -> dict:
    detected_results = [r for r in results if r.detected]
    detect_times = [r.detect_ms for r in detected_results]
    embed_times = [r.embed_ms for r in detected_results]
    faiss_times = [r.faiss_ms for r in detected_results]

    n_total = len(results)
    n_genuine = sum(1 for r in results if not r.is_impostor)
    n_impostor = sum(1 for r in results if r.is_impostor)
    n_detected = sum(1 for r in results if r.detected)
    n_no_detect = n_total - n_detected
    detection_rate = (n_detected / n_total) if n_total else None

    rank1 = _rank1_accuracy(results)
    primary = _summarise_at_threshold(results, primary_threshold)
    sweep_rows = [_summarise_at_threshold(results, t) for t in sweep]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as fh:

        def w(line: str = "") -> None:
            fh.write(line + "\n")

        w("=" * 74)
        w("IAMS Accuracy Benchmark Report")
        w("=" * 74)
        w(f"Generated:        {datetime.now().isoformat(timespec='seconds')}")
        w(f"Photos directory: {photos_dir}")
        w(f"Model:            {settings.INSIGHTFACE_MODEL} "
          f"(det_size={settings.INSIGHTFACE_DET_SIZE}, "
          f"det_thresh={settings.INSIGHTFACE_DET_THRESH})")
        w(f"Production thresh: {settings.RECOGNITION_THRESHOLD}")
        w("")
        w("-- Sample sizes --")
        w(f"  Total photos:           {n_total}")
        w(f"  Genuine (registered):   {n_genuine}")
        w(f"  Impostor (unregistered):{n_impostor}")
        w(f"  Faces successfully detected: {n_detected}  ({_format_pct(detection_rate)})")
        w(f"  No face detected:       {n_no_detect}")
        w("")
        if detect_times:
            w("-- Per-photo timings (ms) on the machine that ran this benchmark --")
            w(f"  SCRFD detect    p50={statistics.median(detect_times):7.1f}   mean={statistics.mean(detect_times):7.1f}   max={max(detect_times):7.1f}")
            w(f"  ArcFace embed   p50={statistics.median(embed_times):7.1f}   mean={statistics.mean(embed_times):7.1f}   max={max(embed_times):7.1f}")
            w(f"  FAISS search    p50={statistics.median(faiss_times):7.1f}   mean={statistics.mean(faiss_times):7.1f}   max={max(faiss_times):7.1f}")
            w("")
        w(f"-- Identification rank-1 accuracy (threshold-independent): {_format_pct(rank1)} --")
        w("")
        w(f"-- Detailed results at production threshold ({primary_threshold:.2f}) --")
        w(f"  TP (correct match):       {primary['counts']['TP']}")
        w(f"  FN (missed / wrong id):   {primary['counts']['FN']}")
        w(f"  FP (impostor matched):    {primary['counts']['FP']}")
        w(f"  TN (impostor rejected):   {primary['counts']['TN']}")
        w(f"  ND (no face detected):    {primary['counts']['ND']}")
        w("")
        w(f"  Genuine Accept Rate (GAR / TPR): {_format_pct(primary['GAR'])}")
        w(f"  False Non-Match Rate (FNMR):     {_format_pct(primary['FNMR'])}")
        w(f"  False Match Rate (FMR):          {_format_pct(primary['FMR'])}")
        w(f"  Precision:                       {_format_pct(primary['precision'])}")
        w(f"  Recall:                          {_format_pct(primary['recall'])}")
        w(f"  F1 score:                        {_format_pct(primary['f1'])}")
        w("")
        w("-- Threshold sweep (rates as % of relevant denominator) --")
        w("  threshold  | n_gen | n_imp |    GAR  |   FNMR  |   FMR   |  Prec   | Recall  |   F1")
        w("  -----------+-------+-------+---------+---------+---------+---------+---------+--------")
        for r in sweep_rows:
            w(
                f"   {r['threshold']:5.2f}     | {r['n_genuine']:5d} | {r['n_impostor']:5d} |"
                f" {_format_pct(r['GAR'])} | {_format_pct(r['FNMR'])} | {_format_pct(r['FMR'])} |"
                f" {_format_pct(r['precision'])} | {_format_pct(r['recall'])} |"
                f" {_format_pct(r['f1'])}"
            )
        w("")
        w("Notes for thesis Chapter 4:")
        w("  - GAR (Genuine Accept Rate) corresponds to objective 1 'accuracy'.")
        w("  - FMR/FNMR follow ISO/IEC 19795-1 biometric metrics — cite that")
        w("    standard so the panel knows the numbers are not ad-hoc.")
        w("  - Rank-1 identification accuracy answers 'correctly identifies")
        w("    the registered student' independent of threshold tuning.")

    summary = {
        "generated_at": datetime.now().isoformat(),
        "photos_dir": str(photos_dir),
        "model": settings.INSIGHTFACE_MODEL,
        "det_size": settings.INSIGHTFACE_DET_SIZE,
        "det_thresh": settings.INSIGHTFACE_DET_THRESH,
        "production_threshold": settings.RECOGNITION_THRESHOLD,
        "n_total": n_total,
        "n_genuine": n_genuine,
        "n_impostor": n_impostor,
        "n_detected": n_detected,
        "detection_rate": detection_rate,
        "rank1_accuracy": rank1,
        "primary_threshold": primary,
        "sweep": sweep_rows,
        "timing_ms": (
            {
                "detect_p50": statistics.median(detect_times),
                "detect_mean": statistics.mean(detect_times),
                "embed_p50": statistics.median(embed_times),
                "embed_mean": statistics.mean(embed_times),
                "faiss_p50": statistics.median(faiss_times),
                "faiss_mean": statistics.mean(faiss_times),
            }
            if detect_times
            else None
        ),
    }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="IAMS face-recognition accuracy benchmark.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--photos-dir",
        required=True,
        type=Path,
        help="Path to the test_photos/ directory (see module docstring).",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=settings.RECOGNITION_THRESHOLD,
        help=f"Primary threshold for the report (default: settings.RECOGNITION_THRESHOLD={settings.RECOGNITION_THRESHOLD}).",
    )
    parser.add_argument(
        "--sweep",
        type=float,
        nargs="+",
        default=list(DEFAULT_SWEEP),
        help="Threshold values to sweep in the summary table.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports"),
        help="Directory to write CSV + summary text + JSON (default: ./reports).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="If > 0, stop after processing this many photos (for smoke-testing).",
    )
    args = parser.parse_args()

    photos_dir: Path = args.photos_dir
    if not photos_dir.is_dir():
        raise SystemExit(f"Photos directory not found: {photos_dir}")

    _print_header("IAMS Accuracy Benchmark")
    print(f"Photos dir:      {photos_dir}")
    print(f"Primary thresh:  {args.threshold}")
    print(f"Sweep:           {args.sweep}")

    model, faiss_manager = _load_pipeline()

    genuine = _list_genuine_photos(photos_dir)
    impostors = _list_impostor_photos(photos_dir)
    print(f"      {len(genuine)} genuine photos across "
          f"{len({uid for uid, _ in genuine})} subjects")
    print(f"      {len(impostors)} impostor photos")

    # Warn about subjects in test set that aren't actually registered
    registered_users = set(faiss_manager.user_map.values())
    unknown_subjects = [uid for uid, _ in genuine if uid not in registered_users]
    if unknown_subjects:
        unique_unknown = sorted(set(unknown_subjects))
        print("\n  WARNING: the following test-set subjects are NOT in the FAISS index:")
        for u in unique_unknown:
            print(f"    - {u}")
        print("  Their photos cannot produce a True-Positive — they will all count as FN.\n")

    # Process every photo
    print("\n[3/3] Running pipeline on test photos...")
    todo = [(uid, p) for uid, p in genuine] + [(None, p) for p in impostors]
    if args.limit and len(todo) > args.limit:
        todo = todo[: args.limit]

    results: list[PhotoResult] = []
    t_start = time.perf_counter()
    for i, (truth_uid, path) in enumerate(todo, 1):
        results.append(_process_photo(model, faiss_manager, path, truth_uid))
        if i % 25 == 0 or i == len(todo):
            elapsed = time.perf_counter() - t_start
            rate = i / elapsed if elapsed > 0 else 0.0
            print(f"      {i}/{len(todo)} processed ({rate:.1f} photos/s)")

    # Write outputs
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir: Path = args.output_dir
    csv_path = out_dir / f"accuracy_{timestamp}.csv"
    txt_path = out_dir / f"accuracy_{timestamp}.txt"
    json_path = out_dir / f"accuracy_{timestamp}.json"

    _write_csv(results, csv_path)
    summary = _write_summary(
        results,
        tuple(args.sweep),
        args.threshold,
        txt_path,
        photos_dir,
    )
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with json_path.open("w") as fh:
        json.dump(summary, fh, indent=2, default=str)

    print()
    _print_header("Done")
    print(f"  Per-photo CSV:  {csv_path}")
    print(f"  Summary text:   {txt_path}")
    print(f"  Summary JSON:   {json_path}")
    print()


if __name__ == "__main__":
    main()
