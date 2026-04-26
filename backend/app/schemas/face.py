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

    ``per_room`` maps the canonical room key (``room.stream_key``,
    lowercase) to the number of CCTV embeddings that user already has
    captured in that room. ``cctv_legacy`` is the count of pre-Phase-2
    room-agnostic ``cctv_<idx>`` rows; legacy captures contribute to
    the global ``cctv_count`` but do not satisfy any specific room's
    enrolment for the bulk-enrollment UI's "missing in EB227" filter.
    """

    user_id: str
    student_id: str | None
    full_name: str
    cctv_count: int
    phone_only: bool
    per_room: dict[str, int] = {}
    cctv_legacy: int = 0


class CctvEnrollmentRoomOption(BaseModel):
    """A room exposed by the bulk-enrollment UI as a target.

    ``stream_key`` is the canonical key used to label new CCTV
    embeddings (``cctv_<stream_key>_<idx>``) and to address the WHEP
    stream from the admin live-feed player. Falls back to the lowercased
    ``name`` for legacy rooms whose ``stream_key`` was never populated.
    """

    id: str
    name: str
    stream_key: str
    has_camera: bool


class CctvEnrollmentStatusResponse(BaseModel):
    """Aggregate CCTV enrolment posture across all students with active
    face registrations.

    ``rooms`` (legacy) enumerates known room stream-keys for backward
    compatibility with the live-feed banner that already consumes this
    endpoint. ``room_options`` is the structured form used by the new
    bulk-enrollment admin page so it can render the room dropdown
    without a second round-trip to /api/v1/rooms.
    """

    students: list[CctvEnrollmentStatusEntry]
    rooms: list[str]
    room_options: list[CctvEnrollmentRoomOption] = []
    threshold: float
    phone_only_threshold: float
    phone_only_count: int
    total_registered: int


class CctvEnrollPreviewRequest(BaseModel):
    """Single-frame preview before committing a 5-capture batch.

    Lets the bulk-enrollment UI confirm visually that the right student
    is in front of the camera (and that the face is being detected with
    reasonable confidence) before the operator pulls the trigger on a
    full ``cctv_enroll``.
    """

    room: str = Field(
        ...,
        description=(
            "Room identifier — accepts UUID, ``stream_key`` (e.g. ``eb226``), "
            "or ``name`` (e.g. ``EB226``). Resolved server-side."
        ),
    )
    min_face_size_px: int = 60
    min_det_score: float = 0.65


class CctvEnrollPreviewFace(BaseModel):
    """One detected face from a preview frame.

    Multi-face frames are handled by ranking every face by cosine
    similarity to the target user's registered phone embedding; the
    UI surfaces all of them so the operator can verify the system
    picked the right one.

    The ``best_match_*`` fields are the result of cross-identifying
    this face against EVERY enrolled student's phone embedding (not
    just the selected target). When the auto-selected face's
    ``best_match_user_id`` differs from the user the operator is
    enrolling, the UI surfaces a "Did you mean to enroll [Name]?"
    suggestion so the operator can switch with one click instead of
    enrolling the wrong person silently.
    """

    crop_b64: str  # JPEG, base64-encoded, no data URI prefix
    det_score: float
    bbox: list[int]  # [x, y, w, h] in source frame coords
    self_similarity_to_phone: float  # cosine sim vs registered phone embedding
    is_best_match: bool  # True if this face is the highest-sim face in the frame
    # Cross-identification: which enrolled student does THIS face look
    # most like, regardless of the selected target? None when no
    # enrolled students have phone embeddings (test/empty DB).
    best_match_user_id: str | None = None
    best_match_full_name: str | None = None
    best_match_student_id: str | None = None
    best_match_sim: float | None = None


class CctvIdentifyRequest(BaseModel):
    """Bulk identify-everyone-in-frame request.

    No ``user_id`` — this is the camera-first workflow: grab a frame,
    detect every face, identify each against every enrolled student,
    return the lot. The admin UI uses this for the "Scan Classroom"
    tab where the operator can click Enroll directly on each visible
    student that still needs CCTV captures, instead of picking one
    student at a time from a queue.
    """

    room: str = Field(
        ...,
        description=(
            "Room identifier — accepts UUID, ``stream_key`` (e.g. ``eb226``), "
            "or ``name`` (e.g. ``EB226``). Resolved server-side."
        ),
    )
    min_face_size_px: int = 60
    min_det_score: float = 0.65
    # Confidence floor for surfacing an identification. Faces with a
    # best cross-ID sim below this are returned as "Unknown" so the
    # UI doesn't suggest an enrollment for a stranger or a misdetect.
    min_identify_sim: float = 0.40


class CctvIdentifiedFace(BaseModel):
    """One face from a Scan-Classroom request, with cross-ID metadata."""

    crop_b64: str  # JPEG, base64-encoded, no data URI prefix
    det_score: float
    bbox: list[int]  # [x, y, w, h] in source frame coords
    # Identification (None when no enrolled student is a confident match)
    identified_user_id: str | None = None
    identified_full_name: str | None = None
    identified_student_id: str | None = None
    identified_sim: float | None = None
    # Per-room CCTV capture counts for the identified student. Keyed by
    # room.stream_key (lowercased). Empty if face is unidentified.
    per_room: dict[str, int] = {}
    # True iff the identified student already has the per-room cap of
    # CCTV captures for the requested room. The UI uses this to gray
    # out the Enroll button so an operator can't double-enroll.
    already_enrolled_in_room: bool = False


class CctvIdentifyResponse(BaseModel):
    """All faces from one camera scan, ranked by det_score (largest first).

    ``identified_count`` is how many faces had a confident cross-ID
    above ``min_identify_sim``; the remainder are "Unknown" and don't
    have user metadata attached.
    """

    ok: bool
    message: str
    face_count: int
    identified_count: int
    faces: list[CctvIdentifiedFace] = []
    frame_size: list[int] | None = None  # [width, height] of the source frame


class CctvEnrollPreviewResponse(BaseModel):
    """All detected faces from one preview frame, ranked by similarity
    to the selected student.

    Designed for the realistic classroom case where multiple students
    share the camera. The capture loop auto-picks the highest-sim face
    each frame, so the operator just has to make sure the right student
    is in the picture — they don't have to clear the room.

    ``ok=False`` means no face passed the gates at all; the UI surfaces
    ``message`` so the operator knows to adjust framing / lighting /
    student position before retrying.
    """

    ok: bool
    message: str
    face_count: int
    faces: list[CctvEnrollPreviewFace] = []
    frame_size: list[int] | None = None  # [width, height] of the source frame
    # The highest-sim face's score, exposed at top level for quick gating
    # in the UI without iterating ``faces``. None when face_count == 0.
    best_self_similarity_to_phone: float | None = None


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
