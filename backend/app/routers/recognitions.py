"""
Recognition Evidence Router

Admin-only surface over ``recognition_events``:

- ``GET /api/v1/recognitions``                       — cursor-paginated list
- ``GET /api/v1/recognitions/{event_id}``            — one row
- ``GET /api/v1/recognitions/{event_id}/live-crop``  — JPEG bytes
- ``GET /api/v1/recognitions/{event_id}/registered-crop`` — JPEG bytes
- ``GET /api/v1/recognitions/summary``               — per-student stats
- ``GET /api/v1/recognitions/export.csv``            — streaming CSV of the filtered set

All endpoints require an admin-authenticated user. Mounted only when
``ENABLE_RECOGNITION_ROUTES`` is true (disabled on VPS thin profile).
"""

from __future__ import annotations

import csv
import io
import logging
import uuid
from datetime import datetime
from typing import Iterable, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal, get_db
from app.models.recognition_access_audit import RecognitionAccessAudit
from app.models.user import User
from app.repositories.recognition_repository import RecognitionRepository
from app.schemas.recognition import (
    AccessAuditEntry,
    AccessAuditListResponse,
    BBoxModel,
    CropUrls,
    RecognitionEventResponse,
    RecognitionListResponse,
    RecognitionSummaryResponse,
)
from app.services.evidence_storage import evidence_storage
from app.utils.dependencies import get_current_admin

logger = logging.getLogger("iams")

router = APIRouter()


def _audit_crop_fetch_sync(
    *,
    viewer_user_id: str,
    event_id: str,
    crop_kind: str,
    ip: Optional[str],
    user_agent: Optional[str],
) -> None:
    """BackgroundTask-friendly insert into recognition_access_audit.

    Uses its own SessionLocal so the request-scoped session can be closed
    before the task runs — FastAPI BackgroundTasks execute after the
    response is sent.
    """
    if not settings.ENABLE_RECOGNITION_ACCESS_AUDIT:
        return
    db = SessionLocal()
    try:
        row = RecognitionAccessAudit(
            viewer_user_id=uuid.UUID(viewer_user_id),
            event_id=uuid.UUID(event_id),
            crop_kind=crop_kind,
            ip=ip,
            user_agent=user_agent,
        )
        db.add(row)
        db.commit()
    except Exception:
        db.rollback()
        logger.debug(
            "access-audit insert failed viewer=%s event=%s kind=%s",
            viewer_user_id,
            event_id,
            crop_kind,
            exc_info=True,
        )
    finally:
        db.close()


def _client_ip(request: Request) -> Optional[str]:
    """Best-effort client IP honouring nginx X-Forwarded-For."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # First entry is the original client; later entries are proxies.
        return forwarded.split(",")[0].strip() or None
    client = request.client
    return client.host if client else None


# -- helpers --------------------------------------------------------------


def _event_to_response(row) -> RecognitionEventResponse:
    student_name: Optional[str] = None
    if row.student is not None:
        first = getattr(row.student, "first_name", None) or ""
        last = getattr(row.student, "last_name", None) or ""
        full = f"{first} {last}".strip()
        student_name = full or None
    subject = None
    if row.schedule is not None:
        subject = getattr(row.schedule, "subject_code", None)

    crop_urls = CropUrls(
        live=f"{settings.API_PREFIX}/recognitions/{row.id}/live-crop",
        registered=(
            f"{settings.API_PREFIX}/recognitions/{row.id}/registered-crop"
            if row.registered_crop_ref
            else None
        ),
    )

    bbox_data = row.bbox or {}
    bbox = BBoxModel(
        x1=int(bbox_data.get("x1", 0)),
        y1=int(bbox_data.get("y1", 0)),
        x2=int(bbox_data.get("x2", 0)),
        y2=int(bbox_data.get("y2", 0)),
    )

    return RecognitionEventResponse(
        event_id=str(row.id),
        schedule_id=str(row.schedule_id),
        schedule_subject=subject,
        student_id=str(row.student_id) if row.student_id else None,
        student_name=student_name,
        track_id=int(row.track_id),
        camera_id=str(row.camera_id),
        frame_idx=int(row.frame_idx),
        similarity=float(row.similarity),
        threshold_used=float(row.threshold_used),
        matched=bool(row.matched),
        is_ambiguous=bool(row.is_ambiguous),
        det_score=float(row.det_score),
        embedding_norm=float(row.embedding_norm),
        bbox=bbox,
        model_name=str(row.model_name),
        crop_urls=crop_urls,
        created_at=row.created_at,
    )


def _parse_cursor(cursor: Optional[str]) -> tuple[Optional[datetime], Optional[str]]:
    """Cursor format is ``<iso>|<uuid>`` produced by the server on the previous
    page. Both halves required. Silently ignores malformed cursors — the
    client gets the first page instead of a 500.
    """
    if not cursor:
        return None, None
    try:
        iso, raw_id = cursor.split("|", 1)
        created_at = datetime.fromisoformat(iso)
        # Validate uuid roundtrip (also guards against injection).
        uuid.UUID(raw_id)
        return created_at, raw_id
    except Exception:
        return None, None


def _build_cursor(row) -> str:
    return f"{row.created_at.isoformat()}|{row.id}"


def _serve_crop(
    ref: Optional[str],
    *,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User,
    event_id: str,
    crop_kind: str,
    filename: str,
) -> Response:
    """Resolve a crop ref via the storage abstraction and return the right
    response shape for the active backend.

    - Filesystem: ``FileResponse(local_path)`` — zero-copy sendfile.
    - MinIO: ``302 Found`` to a time-limited presigned URL — the browser
      fetches bytes directly from MinIO, not through FastAPI.

    Schedules a fire-and-forget audit insert either way.
    """
    if not ref:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No {crop_kind} crop for this event",
        )

    # Audit first — intent to fetch should be logged even if the blob has
    # since been pruned by retention. Background so the response isn't
    # blocked by the DB insert.
    background_tasks.add_task(
        _audit_crop_fetch_sync,
        viewer_user_id=str(current_user.id),
        event_id=event_id,
        crop_kind=crop_kind,
        ip=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )

    if evidence_storage.supports_presigned:
        url = evidence_storage.presigned_get(
            ref, settings.RECOGNITION_EVIDENCE_SIGNED_URL_TTL
        )
        if not url:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{crop_kind} crop is not reachable in object storage",
            )
        return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)

    # Filesystem fast path.
    path = evidence_storage.local_path(ref)
    if not path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{crop_kind} crop not on disk (retention pruned or write failed)",
        )
    return FileResponse(path, media_type="image/jpeg", filename=filename)


# -- endpoints ------------------------------------------------------------


@router.get("", response_model=RecognitionListResponse)
@router.get("/", response_model=RecognitionListResponse)
def list_recognitions(
    schedule_id: Optional[str] = Query(default=None),
    student_id: Optional[str] = Query(default=None),
    matched: Optional[bool] = Query(default=None),
    since: Optional[datetime] = Query(default=None),
    until: Optional[datetime] = Query(default=None),
    cursor: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> RecognitionListResponse:
    """Cursor-paginated listing. Pass the returned ``next_cursor`` to advance."""
    repo = RecognitionRepository(db)
    cursor_created, cursor_id = _parse_cursor(cursor)
    rows = repo.list_events(
        schedule_id=schedule_id,
        student_id=student_id,
        matched=matched,
        since=since,
        until=until,
        cursor_created_at=cursor_created,
        cursor_id=cursor_id,
        limit=limit,
    )
    items = [_event_to_response(r) for r in rows]
    next_cursor = _build_cursor(rows[-1]) if len(rows) == limit else None
    return RecognitionListResponse(items=items, next_cursor=next_cursor)


@router.get("/summary", response_model=RecognitionSummaryResponse)
def summarize_student(
    student_id: str = Query(...),
    schedule_id: Optional[str] = Query(default=None),
    since: Optional[datetime] = Query(default=None),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> RecognitionSummaryResponse:
    """Aggregated stats for one student (+ optional schedule scope)."""
    repo = RecognitionRepository(db)
    summary = repo.summarize_for_student(
        student_id=student_id, schedule_id=schedule_id, since=since
    )
    return RecognitionSummaryResponse(**summary)


@router.get("/export.csv")
def export_csv(
    schedule_id: Optional[str] = Query(default=None),
    student_id: Optional[str] = Query(default=None),
    matched: Optional[bool] = Query(default=None),
    since: Optional[datetime] = Query(default=None),
    until: Optional[datetime] = Query(default=None),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Streaming CSV export of the filtered set.

    Walks the cursor in a generator so a 100 k-row export doesn't
    materialise the whole set in memory.
    """
    repo = RecognitionRepository(db)

    def generate() -> Iterable[bytes]:
        header = io.StringIO()
        writer = csv.writer(header)
        writer.writerow(
            [
                "event_id",
                "created_at",
                "schedule_id",
                "student_id",
                "student_name",
                "track_id",
                "camera_id",
                "frame_idx",
                "similarity",
                "threshold_used",
                "matched",
                "is_ambiguous",
                "det_score",
                "model_name",
            ]
        )
        yield header.getvalue().encode()

        cursor_created: Optional[datetime] = None
        cursor_id: Optional[str] = None
        while True:
            rows = repo.list_events(
                schedule_id=schedule_id,
                student_id=student_id,
                matched=matched,
                since=since,
                until=until,
                cursor_created_at=cursor_created,
                cursor_id=cursor_id,
                limit=200,
            )
            if not rows:
                return
            buf = io.StringIO()
            w = csv.writer(buf)
            for r in rows:
                name = ""
                if r.student is not None:
                    name = f"{getattr(r.student, 'first_name', '')} {getattr(r.student, 'last_name', '')}".strip()
                w.writerow(
                    [
                        str(r.id),
                        r.created_at.isoformat() if r.created_at else "",
                        str(r.schedule_id),
                        str(r.student_id) if r.student_id else "",
                        name,
                        r.track_id,
                        r.camera_id,
                        r.frame_idx,
                        f"{float(r.similarity):.4f}",
                        f"{float(r.threshold_used):.4f}",
                        "true" if r.matched else "false",
                        "true" if r.is_ambiguous else "false",
                        f"{float(r.det_score):.4f}",
                        r.model_name,
                    ]
                )
            yield buf.getvalue().encode()
            if len(rows) < 200:
                return
            cursor_created = rows[-1].created_at
            cursor_id = str(rows[-1].id)

    filename = f"recognitions-{datetime.now():%Y%m%d-%H%M%S}.csv"
    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/access-audit", response_model=AccessAuditListResponse)
def list_access_audit(
    event_id: Optional[str] = Query(default=None),
    viewer_id: Optional[str] = Query(default=None),
    since: Optional[datetime] = Query(default=None),
    until: Optional[datetime] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> AccessAuditListResponse:
    """Read-only log of every crop fetch.

    Answers the legal question a registrar hears when a parent asks "who
    looked at my child's biometric data?". Admin-only.
    """
    from sqlalchemy import desc as _desc
    from sqlalchemy.orm import aliased, joinedload

    from app.models.recognition_event import RecognitionEvent
    from app.models.user import User as UserModel

    Viewer = aliased(UserModel)
    Student = aliased(UserModel)

    q = (
        db.query(
            RecognitionAccessAudit,
            Viewer.first_name.label("viewer_first"),
            Viewer.last_name.label("viewer_last"),
            RecognitionEvent.student_id.label("re_student_id"),
            Student.first_name.label("student_first"),
            Student.last_name.label("student_last"),
        )
        .join(Viewer, Viewer.id == RecognitionAccessAudit.viewer_user_id)
        .join(
            RecognitionEvent,
            RecognitionEvent.id == RecognitionAccessAudit.event_id,
        )
        .outerjoin(Student, Student.id == RecognitionEvent.student_id)
    )

    if event_id:
        try:
            q = q.filter(RecognitionAccessAudit.event_id == uuid.UUID(event_id))
        except ValueError:
            return AccessAuditListResponse(items=[], total=0)
    if viewer_id:
        try:
            q = q.filter(
                RecognitionAccessAudit.viewer_user_id == uuid.UUID(viewer_id)
            )
        except ValueError:
            return AccessAuditListResponse(items=[], total=0)
    if since:
        q = q.filter(RecognitionAccessAudit.viewed_at >= since)
    if until:
        q = q.filter(RecognitionAccessAudit.viewed_at < until)

    total = q.count()
    rows = (
        q.order_by(_desc(RecognitionAccessAudit.viewed_at))
        .offset(skip)
        .limit(limit)
        .all()
    )

    items: list[AccessAuditEntry] = []
    for row, v_first, v_last, re_student, s_first, s_last in rows:
        items.append(
            AccessAuditEntry(
                id=int(row.id),
                viewer_user_id=str(row.viewer_user_id),
                viewer_name=(f"{v_first or ''} {v_last or ''}".strip() or None),
                event_id=str(row.event_id),
                crop_kind=str(row.crop_kind),
                viewed_at=row.viewed_at,
                ip=str(row.ip) if row.ip is not None else None,
                user_agent=row.user_agent,
                student_id=str(re_student) if re_student else None,
                student_name=(
                    f"{s_first or ''} {s_last or ''}".strip() or None
                    if (s_first or s_last)
                    else None
                ),
            )
        )
    return AccessAuditListResponse(items=items, total=int(total))


@router.get("/{event_id}", response_model=RecognitionEventResponse)
def get_event(
    event_id: str,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> RecognitionEventResponse:
    repo = RecognitionRepository(db)
    row = repo.get_by_id(event_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return _event_to_response(row)


@router.get("/{event_id}/live-crop")
def get_live_crop(
    event_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> Response:
    repo = RecognitionRepository(db)
    row = repo.get_by_id(event_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return _serve_crop(
        row.live_crop_ref,
        request=request,
        background_tasks=background_tasks,
        current_user=current_user,
        event_id=event_id,
        crop_kind="live",
        filename=f"{event_id}-live.jpg",
    )


@router.get("/{event_id}/registered-crop")
def get_registered_crop(
    event_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> Response:
    repo = RecognitionRepository(db)
    row = repo.get_by_id(event_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return _serve_crop(
        row.registered_crop_ref,
        request=request,
        background_tasks=background_tasks,
        current_user=current_user,
        event_id=event_id,
        crop_kind="registered",
        filename=f"{event_id}-reg.jpg",
    )
