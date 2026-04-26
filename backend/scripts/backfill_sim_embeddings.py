"""
IAMS Per-Camera Sim Embedding Backfill

Re-runs the CCTV-simulated embedding generator for every existing active
face registration using the NEW per-camera lens-aware path
(``FaceService._generate_cctv_simulated_embeddings`` with profiles loaded
from ``backend/data/camera_lens.json``). Replaces each user's old
``sim_*`` embeddings with new ``sim_eb226_v0``, ``sim_eb227_v0`` etc.
vectors that live in each registered camera's native lens domain.

Why this exists
---------------
The original synthesis path generated camera-agnostic ``sim_0``..``sim_4``
embeddings using a generic blur+JPEG+downscale degradation. After
2026-04-25 we learnt that:

  * Each room has a different lens (Reolink P340 wide-angle vs CX810
    normal lens) — generic synthesis under-represents the geometric
    distortion of the wide-angle case.
  * Phone selfies hit live recognition at sims well below the 0.45
    threshold for many students because the synthesis didn't bridge the
    domain gap aggressively enough.

The new synthesis applies per-camera lens distortion + colour shift +
2D pose perturbation BEFORE the existing degradation pipeline. This
script lets you upgrade existing students without making them
re-register.

Usage
-----
    docker exec iams-api-gateway-onprem python -m scripts.backfill_sim_embeddings
    docker exec iams-api-gateway-onprem python -m scripts.backfill_sim_embeddings --dry-run
    docker exec iams-api-gateway-onprem python -m scripts.backfill_sim_embeddings --user-id <uuid>

Flags:
    --dry-run        Print what would change but don't write the new index.
    --user-id <uuid> Limit backfill to a single user (good for testing).
    --notify         Publish faiss_reload event after rebuild (multi-worker).

Failure isolation: each user is processed in its own DB transaction. A
failure on one user logs and continues; the rest still benefit. After
all users are done, the FAISS index is rebuilt from the canonical DB
state (drops orphaned vectors from earlier failed attempts).

Limitations
-----------
* Requires the original phone-captured JPEGs to be on disk (the
  ``face_uploads_onprem`` Docker volume). Users who registered before
  Phase 2 of the registered-images plan have no JPEGs to re-process and
  will be skipped with a warning. They need to re-register on the phone
  to benefit, OR run ``scripts/cctv_enroll.py`` for them manually.

Exit codes
----------
    0  Backfill complete.
    1  Dry-run only — nothing written.
    2  Errors during backfill; partial completion. Inspect logs.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import logger, settings  # noqa: E402


def run_backfill(
    dry_run: bool = False,
    only_user_id: str | None = None,
    notify: bool = False,
) -> int:
    # Late imports so logging + settings init first
    from app.database import SessionLocal
    from app.repositories.face_repository import FaceRepository
    from app.services.face_service import FaceService
    from app.services.ml.camera_lens import camera_lens_registry
    from app.services.ml.faiss_manager import faiss_manager
    from app.services.ml.insightface_model import insightface_model
    from app.utils.face_image_storage import FaceImageStorage

    print("=" * 64)
    print("IAMS Per-Camera Sim Embedding Backfill")
    print("=" * 64)
    print(f"  Variants per camera: {settings.SIM_VARIANTS_PER_CAMERA}")
    profiles = camera_lens_registry.all_known_profiles()
    print(f"  Known camera profiles: {[p.stream_key for p in profiles] or '(none — fallback only)'}")
    print(f"  Dry run: {dry_run}")
    if only_user_id:
        print(f"  Limited to user: {only_user_id}")
    print()

    print("[1/4] Loading model + FAISS index...")
    insightface_model.load_model()
    faiss_manager.load_or_create_index()
    faiss_manager.rebuild_user_map_from_db()
    print(f"      FAISS: {faiss_manager.index.ntotal} vectors before backfill")
    print()

    db = SessionLocal()
    try:
        repo = FaceRepository(db)
        regs = repo.get_active_embeddings()  # list of FaceRegistration with is_active=True
        if only_user_id:
            regs = [r for r in regs if str(r.user_id) == only_user_id]
        if not regs:
            print("  No matching registrations found.")
            return 1
        print(f"[2/4] Found {len(regs)} active registration(s) to process.")
        print()

        face_service = FaceService(db)
        storage = FaceImageStorage()

        # Per-user metrics
        succeeded: list[str] = []
        skipped_no_disk: list[str] = []
        failed: list[tuple[str, str]] = []

        ANGLE_NAMES = ["center", "left", "right", "up", "down"]

        for reg_idx, registration in enumerate(regs, start=1):
            uid = str(registration.user_id)
            print(f"[3/4] ({reg_idx}/{len(regs)}) Processing user {uid[:8]}...")

            # Load existing per-angle embeddings rows
            existing_embs = repo.get_embeddings_by_registration(str(registration.id))
            if not existing_embs:
                print(f"      Skipping — no embedding rows in face_embeddings.")
                failed.append((uid, "no_embedding_rows"))
                continue

            # Find the on-disk phone-captured JPEGs
            phone_crops_bgr: list[np.ndarray] = []
            for emb in existing_embs:
                if emb.angle_label not in ANGLE_NAMES or not emb.image_storage_key:
                    continue
                try:
                    path = storage.resolve_path(emb.image_storage_key)
                    img_bytes = path.read_bytes()
                    pil = cv2.imdecode(
                        np.frombuffer(img_bytes, dtype=np.uint8), cv2.IMREAD_COLOR
                    )
                    if pil is None:
                        continue
                    # Re-detect to extract aligned face crop the way registration did
                    face_data = insightface_model.get_face_with_quality(img_bytes)
                    bx, by, bw, bh = face_data["bbox"]
                    crop = face_data["image_bgr"][by : by + bh, bx : bx + bw]
                    if crop.size > 0:
                        phone_crops_bgr.append(crop)
                except FileNotFoundError:
                    continue
                except Exception as exc:
                    logger.debug("Skipping angle %s for user %s: %s", emb.angle_label, uid, exc)

            if not phone_crops_bgr:
                print(f"      Skipping — no phone JPEGs on disk (legacy registration).")
                skipped_no_disk.append(uid)
                continue
            print(f"      Loaded {len(phone_crops_bgr)} phone face crops from disk.")

            # Drop old sim rows for this user (we'll add new ones)
            old_sim_rows = [
                e for e in existing_embs
                if e.angle_label and e.angle_label.startswith("sim")
            ]
            if old_sim_rows:
                print(f"      Will drop {len(old_sim_rows)} old sim_* rows.")
            else:
                print(f"      No old sim_* rows to drop.")

            # Generate new per-camera sim embeddings
            sim_pairs = face_service._generate_cctv_simulated_embeddings(
                phone_crops_bgr,
                camera_profiles=None,  # uses all known profiles
                variants_per_camera=settings.SIM_VARIANTS_PER_CAMERA,
            )
            if not sim_pairs:
                print(f"      Generator produced 0 embeddings — skipping commit.")
                failed.append((uid, "generator_empty"))
                continue
            print(f"      Generated {len(sim_pairs)} new per-camera sim embeddings.")

            if dry_run:
                continue

            # Commit per user: drop old sim rows from DB; insert new ones.
            # FAISS will be rebuilt from DB at the end so we don't manually
            # touch index here.
            try:
                for old in old_sim_rows:
                    db.delete(old)
                # Build entries to insert
                # faiss_id will be re-assigned at rebuild — store a sentinel
                # and let the rebuild_faiss_index step re-key everything.
                new_entries = []
                for idx, (emb, suffix) in enumerate(sim_pairs):
                    new_entries.append({
                        "faiss_id": -1,  # placeholder; rebuild assigns real IDs
                        "embedding_vector": emb.astype(np.float32).tobytes(),
                        "angle_label": f"sim_{suffix}",
                        "quality_score": None,
                    })
                repo.create_embeddings_batch(str(registration.id), new_entries)
                db.commit()
                succeeded.append(uid)
            except Exception as exc:
                db.rollback()
                logger.exception("Backfill failed for user %s", uid)
                failed.append((uid, str(exc)))

        print()
        print("[4/4] Rebuilding FAISS index from canonical DB state...")
        if dry_run:
            print(f"      DRY RUN — skipped rebuild.")
        else:
            # face_service.rebuild_faiss_index uses the DB embeddings as
            # the source of truth and re-keys faiss_ids 0..N. After this
            # the placeholders we wrote above (-1) are overwritten with
            # the real positions in the rebuilt index.
            import asyncio
            asyncio.run(face_service.rebuild_faiss_index())

            # Now sync back the new faiss_ids to face_embeddings rows so
            # the user_map lookup at recognition time finds them. We do
            # this by ordering the rows the same way rebuild does:
            # _collect_embeddings_static returns them in the same order
            # the rebuild adds them.
            embeddings_data = FaceService._collect_embeddings_static(repo)
            # The repo doesn't expose a bulk faiss_id update by row order,
            # so we step through each user's embeddings and assign IDs in
            # insertion order. This matches what add_batch does in rebuild().
            from sqlalchemy import update
            from app.models.face_embedding import FaceEmbedding
            ids_by_user: dict[str, list[int]] = {}
            for fid, (_, uid) in enumerate(embeddings_data):
                ids_by_user.setdefault(uid, []).append(fid)

            for uid, fids in ids_by_user.items():
                try:
                    user_reg = repo.get_by_user(uid)
                    if user_reg is None:
                        continue
                    user_embs = sorted(
                        repo.get_embeddings_by_registration(str(user_reg.id)),
                        key=lambda e: e.id,  # stable insertion order
                    )
                    for emb_row, new_fid in zip(user_embs, fids):
                        if emb_row.faiss_id != new_fid:
                            db.execute(
                                update(FaceEmbedding)
                                .where(FaceEmbedding.id == emb_row.id)
                                .values(faiss_id=new_fid)
                            )
                except Exception:
                    logger.exception("Faiss-id sync failed for user %s", uid)
            db.commit()
            print(f"      FAISS rebuilt: {faiss_manager.index.ntotal} vectors")

            if notify:
                try:
                    asyncio.run(faiss_manager.notify_index_changed())
                    print("      Published Redis faiss_reload notification.")
                except Exception as exc:
                    print(f"      WARN: notify failed: {exc}")

        print()
        print("=" * 64)
        print("  Backfill summary")
        print("=" * 64)
        print(f"  Succeeded: {len(succeeded)}")
        print(f"  Skipped (no disk JPEGs): {len(skipped_no_disk)}")
        print(f"  Failed:    {len(failed)}")
        if failed:
            for uid, reason in failed[:10]:
                print(f"    - {uid[:8]}: {reason}")
            if len(failed) > 10:
                print(f"    ... and {len(failed) - 10} more")

        if dry_run:
            return 1
        return 0 if not failed else 2
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IAMS sim-embedding backfill")
    parser.add_argument("--dry-run", action="store_true", help="Don't commit anything")
    parser.add_argument("--user-id", type=str, default="", help="Limit to one user UUID")
    parser.add_argument("--notify", action="store_true", help="Notify other workers via Redis")
    args = parser.parse_args()

    only = args.user_id.strip() or None
    try:
        sys.exit(run_backfill(dry_run=args.dry_run, only_user_id=only, notify=args.notify))
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(130)
    except Exception:
        logger.exception("Backfill failed")
        sys.exit(2)
