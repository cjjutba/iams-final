"""
Migration: filesystem crops → MinIO.

Run after flipping ``RECOGNITION_EVIDENCE_BACKEND=minio`` on a stack that
was previously writing crops to the filesystem. The script walks every
``recognition_events`` row with non-NULL refs, uploads the matching JPEG
from ``RECOGNITION_EVIDENCE_CROP_ROOT`` to MinIO under the same key, and
leaves the DB ref column unchanged — because the storage abstraction
uses the same key format on both backends.

Idempotent: rows where the blob already exists in MinIO are skipped.

Usage (inside the api-gateway container):

    python -m scripts.migrate_crops_to_minio

Optional env:

    MIGRATE_BATCH=500        Batch size (default 500)
    MIGRATE_DRY_RUN=true     Scan + count, do not upload
    MIGRATE_DELETE_LOCAL=true Remove the FS JPEG after successful upload

When MIGRATE_DELETE_LOCAL is set, this becomes a true cutover: the FS
copy is deleted after MinIO confirms the object. Run it with dry-run
off once, verify, then flip MIGRATE_DELETE_LOCAL on for the final sweep.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import sys as _sys

_sys.path.insert(0, "/app")

from app.config import settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.services.evidence_storage import (  # noqa: E402
    FilesystemStorage,
    MinioStorage,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("migrate_crops")


def main() -> int:
    if settings.RECOGNITION_EVIDENCE_BACKEND != "minio":
        logger.error(
            "RECOGNITION_EVIDENCE_BACKEND=%s — the migration script only "
            "runs when the active backend is 'minio'. Flip the flag + "
            "restart the api-gateway first.",
            settings.RECOGNITION_EVIDENCE_BACKEND,
        )
        return 1

    dry_run = (os.environ.get("MIGRATE_DRY_RUN", "false").lower() in ("1", "true", "yes"))
    delete_local = (
        os.environ.get("MIGRATE_DELETE_LOCAL", "false").lower()
        in ("1", "true", "yes")
    )
    batch = max(1, int(os.environ.get("MIGRATE_BATCH", "500")))

    fs = FilesystemStorage(Path(settings.RECOGNITION_EVIDENCE_CROP_ROOT))
    try:
        minio = MinioStorage(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
            bucket=settings.MINIO_BUCKET,
            region=settings.MINIO_REGION,
        )
    except RuntimeError as exc:
        logger.error("Cannot construct MinioStorage: %s", exc)
        return 1

    from sqlalchemy import text

    stats = {
        "scanned": 0,
        "uploaded": 0,
        "skipped_present": 0,
        "missing_fs": 0,
        "deleted_local": 0,
        "errors": 0,
    }

    db = SessionLocal()
    try:
        offset = 0
        while True:
            rows = (
                db.execute(
                    text(
                        "SELECT id, live_crop_ref, registered_crop_ref "
                        "FROM recognition_events "
                        "WHERE live_crop_ref IS NOT NULL OR registered_crop_ref IS NOT NULL "
                        "ORDER BY created_at ASC "
                        "OFFSET :offset LIMIT :batch"
                    ),
                    {"offset": offset, "batch": batch},
                )
                .fetchall()
            )
            if not rows:
                break

            for _event_id, live_ref, reg_ref in rows:
                for ref in (live_ref, reg_ref):
                    if not ref:
                        continue
                    stats["scanned"] += 1

                    if minio.exists(ref):
                        stats["skipped_present"] += 1
                        continue

                    data = fs.get_bytes(ref)
                    if data is None:
                        stats["missing_fs"] += 1
                        continue

                    if dry_run:
                        stats["uploaded"] += 1  # "would upload"
                        continue

                    try:
                        minio.put(ref, data)
                        stats["uploaded"] += 1
                    except Exception:
                        stats["errors"] += 1
                        logger.exception("upload failed for %s", ref)
                        continue

                    if delete_local:
                        try:
                            fs.delete(ref)
                            stats["deleted_local"] += 1
                        except Exception:
                            logger.debug(
                                "local delete failed for %s", ref, exc_info=True
                            )

            offset += batch
            logger.info("progress offset=%d %s", offset, stats)
    finally:
        db.close()

    logger.info(
        "migration %s — %s",
        "DRY-RUN complete" if dry_run else "complete",
        stats,
    )
    return 0 if stats["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
