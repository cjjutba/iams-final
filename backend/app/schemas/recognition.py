"""
Recognition Evidence schemas.

Request/response shapes for the ``/api/v1/recognitions`` admin router. See
docs/plans/2026-04-22-recognition-evidence/DESIGN.md for the wire contract.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class BBoxModel(BaseModel):
    x1: int
    y1: int
    x2: int
    y2: int


class CropUrls(BaseModel):
    """Relative URLs for lazy-fetch. The browser should resolve against the
    same origin it used for the API call (nginx reverse-proxies /api → backend)."""

    live: str
    registered: Optional[str] = None


class RecognitionEventResponse(BaseModel):
    """One row in the admin audit list / student Recent Detections feed."""

    event_id: str
    schedule_id: str
    schedule_subject: Optional[str] = None
    student_id: Optional[str] = None
    student_name: Optional[str] = None
    track_id: int
    camera_id: str
    frame_idx: int
    similarity: float
    threshold_used: float
    matched: bool
    is_ambiguous: bool
    det_score: float
    embedding_norm: float
    bbox: BBoxModel
    model_name: str
    crop_urls: CropUrls
    created_at: datetime

    class Config:
        from_attributes = True


class RecognitionListResponse(BaseModel):
    items: list[RecognitionEventResponse]
    next_cursor: Optional[str] = None  # "<iso_created_at>|<uuid>" or None


class EventBrief(BaseModel):
    event_id: str
    similarity: float
    timestamp: Optional[datetime]


class TimelineBucket(BaseModel):
    minute: str
    matches: int
    misses: int


class RecognitionSummaryResponse(BaseModel):
    """MatchEvidence payload for the attendance-detail sheet."""

    student_id: str
    schedule_id: Optional[str]
    match_count: int
    miss_count: int
    best_match: Optional[EventBrief]
    worst_accepted: Optional[EventBrief]
    first_match: Optional[EventBrief]
    last_match: Optional[EventBrief]
    histogram: list[int]
    timeline: list[TimelineBucket]
    threshold_at_session: Optional[float]


class AccessAuditEntry(BaseModel):
    """One row of the recognition_access_audit log."""

    id: int
    viewer_user_id: str
    viewer_name: Optional[str] = None
    event_id: str
    crop_kind: str
    viewed_at: datetime
    ip: Optional[str] = None
    user_agent: Optional[str] = None
    student_id: Optional[str] = None
    student_name: Optional[str] = None


class AccessAuditListResponse(BaseModel):
    items: list[AccessAuditEntry]
    total: int
