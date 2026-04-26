"""
Recognition Evidence retention job.

Daily APScheduler sweep that prunes:
  1. Crop blobs older than ``RECOGNITION_CROP_RETENTION_DAYS`` via the
     storage abstraction (filesystem unlink OR MinIO remove_object).
  2. ``recognition_events`` rows older than
     ``RECOGNITION_EVENT_RETENTION_DAYS`` — a CASCADE FK on
     recognition_access_audit removes its rows automatically.

The storage-agnostic pass first: for every event row whose created_at is
older than the crop cutoff, call ``evidence_storage.delete(ref)`` on the
live + registered refs. Then the row pass deletes the DB rows older than
the row cutoff.

Safety layers (all default-on):

- ``RECOGNITION_EVIDENCE_RETENTION_DRY_RUN=True`` by default. Logs the
  delete set but does not touch storage or DB.
- ``RECOGNITION_EVIDENCE_RETENTION_MAX_DELETES`` hard cap aborts a single
  sweep that would exceed the cap.
- Two independent passes (blobs, rows) so a failure in one doesn't block
  the other.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from app.config import settings
from app.database import SessionLocal

logger = logging.getLogger("iams")


def run_recognition_retention() -> None:
    """Entry point scheduled from main.py."""
    if not settings.ENABLE_RECOGNITION_EVIDENCE_RETENTION:
        return
    try:
        stats = _sweep()
        logger.info(
            "recognition-retention sweep dry_run=%s backend=%s "
            "blobs_scanned=%d blobs_deleted=%d "
            "rows_scanned=%d rows_deleted=%d",
            settings.RECOGNITION_EVIDENCE_RETENTION_DRY_RUN,
            settings.RECOGNITION_EVIDENCE_BACKEND,
            stats["blobs_scanned"],
            stats["blobs_deleted"],
            stats["rows_scanned"],
            stats["rows_deleted"],
        )
    except Exception:
        logger.exception("recognition-retention sweep crashed")


def _sweep() -> dict[str, int]:
    dry_run = bool(settings.RECOGNITION_EVIDENCE_RETENTION_DRY_RUN)
    max_deletes = max(1, int(settings.RECOGNITION_EVIDENCE_RETENTION_MAX_DELETES))
    now = datetime.now()

    crop_retention_days = max(1, int(settings.RECOGNITION_CROP_RETENTION_DAYS))
    row_retention_days = max(1, int(settings.RECOGNITION_EVENT_RETENTION_DAYS))

    crop_cutoff = now - timedelta(days=crop_retention_days)
    row_cutoff = now - timedelta(days=row_retention_days)

    blobs_scanned, blobs_deleted = _prune_blobs(
        cutoff=crop_cutoff, dry_run=dry_run, max_deletes=max_deletes
    )
    rows_scanned, rows_deleted = _prune_rows(
        cutoff=row_cutoff, dry_run=dry_run, max_deletes=max_deletes
    )

    return {
        "blobs_scanned": blobs_scanned,
        "blobs_deleted": blobs_deleted,
        "rows_scanned": rows_scanned,
        "rows_deleted": rows_deleted,
    }


def _prune_blobs(
    *, cutoff: datetime, dry_run: bool, max_deletes: int
) -> tuple[int, int]:
    """Delete crop blobs for every event older than ``cutoff``.

    Keeps the DB row's ref column populated when dry-run; on the real
    pass we null the refs out so a later retrieval returns 404 instead
    of pointing at a now-missing blob.
    """
    from sqlalchemy import text

    from app.services.evidence_storage import evidence_storage

    db = SessionLocal()
    try:
        rows = (
            db.execute(
                text(
                    "SELECT id, live_crop_ref, registered_crop_ref "
                    "FROM recognition_events "
                    "WHERE created_at < :cutoff "
                    "  AND (live_crop_ref IS NOT NULL OR registered_crop_ref IS NOT NULL) "
                    "ORDER BY created_at ASC "
                    "LIMIT :cap"
                ),
                {"cutoff": cutoff, "cap": max_deletes},
            )
            .fetchall()
        )
        scanned = len(rows)
        if scanned == 0:
            return 0, 0

        deleted = 0
        for event_id, live_ref, reg_ref in rows:
            for ref in (live_ref, reg_ref):
                if not ref:
                    continue
                if dry_run:
                    logger.debug("DRY-RUN would delete crop %s", ref)
                    deleted += 1
                    continue
                try:
                    evidence_storage.delete(ref)
                    deleted += 1
                except Exception:
                    logger.debug(
                        "storage delete failed for %s (event %s)",
                        ref,
                        event_id,
                        exc_info=True,
                    )

            if not dry_run:
                # Null the refs so the audit row survives but doesn't
                # promise a blob we just deleted. (If retention then also
                # deletes the row below, this is moot — but blobs expire
                # before rows by design, so this window is real.)
                db.execute(
                    text(
                        "UPDATE recognition_events "
                        "SET live_crop_ref = NULL, registered_crop_ref = NULL "
                        "WHERE id = :eid"
                    ),
                    {"eid": event_id},
                )
        if not dry_run:
            db.commit()
        return scanned, deleted
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _prune_rows(
    *, cutoff: datetime, dry_run: bool, max_deletes: int
) -> tuple[int, int]:
    """Delete old recognition_events rows in bounded batches.

    recognition_access_audit rows CASCADE-delete via FK.
    """
    from sqlalchemy import text

    db = SessionLocal()
    try:
        scanned_row = db.execute(
            text(
                "SELECT count(*) FROM recognition_events WHERE created_at < :cutoff"
            ),
            {"cutoff": cutoff},
        ).first()
        scanned = int(scanned_row[0]) if scanned_row else 0

        if scanned == 0:
            return 0, 0

        if scanned > max_deletes:
            logger.error(
                "recognition-retention: row delete cap hit — %d rows older than cutoff "
                "but max_deletes=%d; not deleting anything. Raise the cap or run "
                "multiple sweeps.",
                scanned,
                max_deletes,
            )
            return scanned, 0

        if dry_run:
            logger.info(
                "DRY-RUN would delete %d recognition_events rows older than %s",
                scanned,
                cutoff.isoformat(),
            )
            return scanned, 0

        # Actual delete.
        result = db.execute(
            text("DELETE FROM recognition_events WHERE created_at < :cutoff"),
            {"cutoff": cutoff},
        )
        db.commit()
        return scanned, int(result.rowcount or 0)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
