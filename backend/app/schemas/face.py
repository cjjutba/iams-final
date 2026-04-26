"""
Face Recognition Schemas

Request and response models for face registration and recognition.
CRITICAL: Includes Edge API contract for Raspberry Pi integration.
"""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

# ===== Face Registration (Mobile App) =====


class QualityScoreResponse(BaseModel):
    """Quality assessment scores for a single registration image."""

    blur_score: float
    brightness: float
    face_size_ratio: float
    det_score: float
    passed: bool


class ImageQualityResponse(BaseModel):
    """Per-image quality validation result (used by mobile pre-upload check)."""

    passed: bool
    blur_score: float
    brightness: float
    face_size_ratio: float
    det_score: float
    rejection_reasons: list[str] = []


class FaceRegisterResponse(BaseModel):
    """Face registration response"""

    success: bool
    message: str
    embedding_id: int | None = None
    user_id: str
    quality_scores: list[QualityScoreResponse] | None = None


class FaceStatusResponse(BaseModel):
    """Face registration status"""

    registered: bool
    registered_at: datetime | None = None
    embedding_id: int | None = None


class CctvEnrollRequest(BaseModel):
    """Operator-driven CCTV-side enrolment request.

    Augments an existing phone-registered student with N embeddings drawn
    from the live CCTV stream so recognition can close the cross-domain
    gap. See FaceService.cctv_enroll for the algorithm.
    """

    room_code_or_id: str
    num_captures: int = 5
    capture_interval_s: float = 1.0
    min_face_size_px: int = 60
    min_det_score: float = 0.65


class CctvEnrollCapture(BaseModel):
    faiss_id: int
    label: str
    det_score: float
    bbox: list[int]


class CctvEnrollResponse(BaseModel):
    success: bool
    user_id: str
    added: int
    faiss_ids: list[int]
    labels: list[str]
    attempts: int
    skipped_reasons: dict[str, int]
    self_similarity_to_phone_mean: float
    self_similarity_to_phone_min: float
    self_similarity_to_phone_max: float
    per_capture: list[CctvEnrollCapture]


class CctvEnrollmentStatusEntry(BaseModel):
    """Per-student CCTV enrolment posture for the admin gap report.

    A student with ``cctv_count == 0`` is recognised entirely off
    cross-domain phone embeddings — sim values land in the noise band
    where two students can flip labels frame-to-frame. The realtime
    tracker applies ``RECOGNITION_PHONE_ONLY_THRESHOLD_BONUS`` for
    these users so the overlay refuses to commit a wrong name; the
    operator should run ``scripts.cctv_enroll`` (or ``POST /api/v1/face/
    cctv-enroll/{user_id}``) for each affected user × room pair to lift
    them out of phone-only state.
    """

    user_id: str
    student_id: str | None
    full_name: str
    cctv_count: int
    phone_only: bool


class CctvEnrollmentStatusResponse(BaseModel):
    """Aggregate CCTV enrolment posture across all students with active
    face registrations.

    ``rooms`` enumerates known rooms so the admin UI can render a
    "needs cctv_enroll in EB226 / EB227" matrix. CCTV embeddings are
    not currently labelled with a room (the angle_label is ``cctv_<idx>``
    rather than ``cctv_<room>_<idx>``) so room-specific status is not
    surfaced here — see the per-user enrolment runs.
    """

    students: list[CctvEnrollmentStatusEntry]
    rooms: list[str]
    threshold: float
    phone_only_threshold: float
    phone_only_count: int
    total_registered: int


# ===== Admin Face Comparison (Live-Feed Detail Sheet) =====


class FaceAngleMetadataResponse(BaseModel):
    """Per-angle embedding metadata for the admin face-comparison sheet.

    `image_url` is None in Phase 1 (images not persisted yet). Phase 2 populates
    it with a URL pointing at the image-bytes endpoint for angles whose
    `image_storage_key` is non-null.
    """

    id: str
    angle_label: str | None
    quality_score: float | None
    created_at: datetime
    image_url: str | None = None


class FaceRegistrationDetailResponse(BaseModel):
    """Admin-only registration detail for a single student.

    `available=false` means either no active registration exists or (in Phase 2+)
    the registration has no persisted images and the caller should render the
    metadata-only fallback.
    """

    user_id: str
    available: bool
    registered_at: datetime | None = None
    embedding_dim: int = 512
    angles: list[FaceAngleMetadataResponse] = []


class LiveCropResponse(BaseModel):
    """One server-captured live crop entry from the Phase-3 Redis ring buffer."""

    crop_b64: str
    captured_at: datetime
    confidence: float
    track_id: int
    bbox: list[float]


class LiveCropsListResponse(BaseModel):
    """Admin-only response for the Phase-3 live-crops endpoint.

    `available=false` when Redis is disabled (VPS), no key exists, or the
    list is empty — the admin UI then falls back to the Phase-1 client-side
    canvas crop of the WHEP video element.
    """

    schedule_id: str
    user_id: str
    available: bool
    crops: list[LiveCropResponse] = []


# ===== Edge API Contract (Raspberry Pi → Backend) =====


class FaceData(BaseModel):
    """
    Single face data from edge device

    CRITICAL: This is the contract between Raspberry Pi and backend.
    Do not change without updating edge code.
    """

    image: str = Field(
        ...,
        description="Base64-encoded JPEG image",
        min_length=1,  # Prevent empty strings
        max_length=15_000_000,  # ~10MB Base64 encoded (prevents DoS)
    )
    bbox: list[int] | None = Field(
        None, min_length=4, max_length=4, description="Bounding box [x, y, w, h]. Optional for MediaPipe compatibility."
    )

    @field_validator("bbox")
    @classmethod
    def validate_bbox(cls, v):
        """Validate bounding box values are reasonable"""
        if v is not None and len(v) == 4:
            if any(val < 0 for val in v):
                raise ValueError("bbox values must be non-negative")
            if v[2] <= 0 or v[3] <= 0:  # width and height
                raise ValueError("bbox width and height must be positive")
        return v


class EdgeProcessRequest(BaseModel):
    """
    Edge API request from Raspberry Pi

    CRITICAL: This is the primary interface for continuous presence tracking.
    """

    request_id: str | None = Field(
        None, description="Idempotency key for retries. Prevents duplicate processing.", max_length=100
    )
    room_id: str = Field(..., description="Room UUID or identifier", max_length=100, pattern=r"^[a-zA-Z0-9\-]+$")
    timestamp: datetime = Field(..., description="Scan timestamp (ISO format)")
    faces: list[FaceData] = Field(
        ...,
        description="List of detected faces",
        min_length=1,
        max_length=10,  # Limit batch size to prevent resource exhaustion
    )


class MatchedUser(BaseModel):
    """Matched user from face recognition"""

    user_id: str
    confidence: float = Field(..., ge=0.0, le=1.0)


class EdgeProcessResponseData(BaseModel):
    """Processing results data"""

    processed: int = Field(..., description="Number of faces processed")
    matched: list[dict] = Field(..., description="Matched users with confidence")
    unmatched: int = Field(..., description="Number of unmatched faces")
    processing_time_ms: int | None = Field(None, description="Total processing time in milliseconds")
    presence_logged: int | None = Field(None, description="Number of presence logs created")


class EdgeProcessResponse(BaseModel):
    """
    Edge API response to Raspberry Pi

    Returns processing results including matched users and metrics.
    """

    success: bool
    data: EdgeProcessResponseData | None = None
    error: dict | None = Field(
        None,
        description="Error details if success=false",
        example={"code": "INVALID_IMAGE_FORMAT", "message": "Face 1: Invalid Base64 encoding", "retry": False},
    )


# ===== Face Recognition (Single Image) =====


class FaceRecognizeRequest(BaseModel):
    """Single face recognition request"""

    image: str = Field(..., description="Base64-encoded JPEG image")


class FaceRecognizeResponse(BaseModel):
    """Single face recognition response"""

    success: bool
    matched: bool
    user_id: str | None = None
    confidence: float | None = None


# ===== Camera Diagnostic =====


class CameraDiagnosticFace(BaseModel):
    """Quality metrics for a single detected face."""

    bbox: list[float] = Field(description="[x1, y1, x2, y2] pixel coordinates")
    size_ratio: float = Field(description="Face area / frame area")
    blur_score: float = Field(description="Laplacian variance (higher = sharper)")
    brightness: float = Field(description="Mean pixel intensity (0-255)")
    det_score: float = Field(description="SCRFD detection confidence")


class CameraDiagnosticResponse(BaseModel):
    """Camera setup diagnostic report."""

    frame_size: list[int] = Field(description="[width, height]")
    face_count: int
    faces: list[CameraDiagnosticFace]
    avg_face_size_ratio: float
    avg_brightness: float
    recommendation: str


# ===== Face Gone (RPi Smart Sampler) =====


class FaceGoneRequest(BaseModel):
    """Request from RPi when tracked faces leave the frame."""

    room_id: str = Field(..., description="Room where faces were lost")
    track_ids: list[int] = Field(default_factory=list, description="IDs of lost face tracks")
    timestamp: float | None = Field(None, description="Unix timestamp of the event")
