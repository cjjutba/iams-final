"""
Face Recognition Router

API endpoints for face registration, recognition, and Edge API for Raspberry Pi.

CRITICAL: Contains Edge API contract for continuous presence tracking.
"""

import base64
import io
import time
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, File, Header, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import logger, settings
from app.database import get_db
from app.models.user import User
from app.repositories.schedule_repository import ScheduleRepository
from app.repositories.face_repository import FaceRepository
from app.schemas.face import (
    CameraDiagnosticFace,
    CameraDiagnosticResponse,
    CctvEnrollRequest,
    CctvEnrollResponse,
    EdgeProcessRequest,
    EdgeProcessResponse,
    EdgeProcessResponseData,
    FaceAngleMetadataResponse,
    FaceGoneRequest,
    FaceRecognizeRequest,
    FaceRecognizeResponse,
    FaceRegisterResponse,
    FaceRegistrationDetailResponse,
    FaceStatusResponse,
    ImageQualityResponse,
    LiveCropResponse,
    LiveCropsListResponse,
    MatchedUser,
    QualityScoreResponse,
)
from app.services.face_service import FaceService
from app.services.ml.face_quality import assess_quality, compute_blur_score, compute_brightness
from app.services.ml.insightface_model import insightface_model
from app.services.presence_service import PresenceService
from app.utils.audit import log_audit
from app.utils.dependencies import get_current_admin, get_current_student, get_current_user, get_optional_user
from app.utils.face_image_storage import FaceImageStorage

router = APIRouter()


async def verify_edge_api_key(x_api_key: str = Header(..., alias="X-API-Key")):
    """Validate the API key sent by edge devices (Raspberry Pi)."""
    if x_api_key != settings.EDGE_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


@router.post("/register", response_model=FaceRegisterResponse, status_code=status.HTTP_201_CREATED)
async def register_face(
    images: list[UploadFile] = File(..., description="3-5 face images"),
    current_user: User = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """
    **Register Face (Step 3 of Student Registration)**

    Upload 3-5 face images to register your face for attendance tracking.

    **Requirements:**
    - Minimum 3 images, maximum 5 images
    - Clear face visible in each image
    - Different angles recommended
    - Max file size: 10MB per image

    **Process:**
    1. Validates images
    2. Generates face embeddings
    3. Stores in FAISS index for recognition
    4. Saves registration to database

    Requires student authentication.
    """
    face_service = FaceService(db)

    try:
        faiss_id, message, quality_reports = await face_service.register_face(str(current_user.id), images)

        quality_scores = None
        if quality_reports:
            quality_scores = [
                QualityScoreResponse(
                    blur_score=q.blur_score,
                    brightness=q.brightness,
                    face_size_ratio=q.face_size_ratio,
                    det_score=q.det_score,
                    passed=q.passed,
                )
                for q in quality_reports
            ]

        return FaceRegisterResponse(
            success=True,
            message=message,
            embedding_id=faiss_id,
            user_id=str(current_user.id),
            quality_scores=quality_scores,
        )

    except Exception as e:
        logger.error(f"Face registration failed for user {current_user.id}: {e}")
        raise


@router.post("/reregister", response_model=FaceRegisterResponse, status_code=status.HTTP_200_OK)
async def reregister_face(
    images: list[UploadFile] = File(..., description="3-5 face images"),
    current_user: User = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """
    **Re-register Face (Update)**

    Replace existing face registration with new images.

    Useful if:
    - Face recognition accuracy is low
    - Physical appearance changed significantly
    - Previous registration had poor quality images

    Same requirements as initial registration.

    Requires student authentication.
    """
    face_service = FaceService(db)

    try:
        faiss_id, message, quality_reports = await face_service.reregister_face(str(current_user.id), images)

        quality_scores = None
        if quality_reports:
            quality_scores = [
                QualityScoreResponse(
                    blur_score=q.blur_score,
                    brightness=q.brightness,
                    face_size_ratio=q.face_size_ratio,
                    det_score=q.det_score,
                    passed=q.passed,
                )
                for q in quality_reports
            ]

        return FaceRegisterResponse(
            success=True,
            message=message,
            embedding_id=faiss_id,
            user_id=str(current_user.id),
            quality_scores=quality_scores,
        )

    except Exception as e:
        logger.error(f"Face re-registration failed for user {current_user.id}: {e}")
        raise


@router.get("/status", response_model=FaceStatusResponse, status_code=status.HTTP_200_OK)
async def get_face_status(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    **Check Face Registration Status**

    Check if current user has registered their face.

    Returns registration status and timestamp.

    Requires authentication.
    """
    face_service = FaceService(db)
    status_data = face_service.get_face_status(str(current_user.id))

    return FaceStatusResponse(**status_data)


@router.get(
    "/registrations/{user_id}",
    response_model=FaceRegistrationDetailResponse,
    status_code=status.HTTP_200_OK,
)
async def get_registration_detail(
    user_id: str,
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    **Admin-only: Registration Detail for Face-Comparison Sheet**

    Returns per-angle embedding metadata for a student's active face
    registration. Used by the admin live-feed page to populate the
    side-by-side comparison sheet.

    In Phase 1 every `image_url` is null (images not persisted yet).
    Phase 2 populates it for angles whose `image_storage_key` is set.
    """
    face_repo = FaceRepository(db)
    registration = face_repo.get_by_user(user_id)

    if registration is None:
        return FaceRegistrationDetailResponse(user_id=user_id, available=False)

    embeddings = face_repo.get_embeddings_by_registration(str(registration.id))

    # Surface real phone-captured angles AND CCTV-captured enrolment crops
    # to the admin sheet. The `sim_*` CCTV-degraded derivatives written by
    # the registration-time augmentation step are FAISS-only and have no
    # image to render — those stay filtered out.
    from app.utils.face_image_storage import _is_allowed_angle_label

    storage = FaceImageStorage()
    angles: list[FaceAngleMetadataResponse] = []
    for emb in embeddings:
        if not emb.angle_label or not _is_allowed_angle_label(emb.angle_label):
            continue
        image_url: str | None = None
        if emb.image_storage_key and storage.exists(emb.image_storage_key):
            image_url = (
                f"/api/v1/face/registrations/{user_id}/images/{emb.angle_label}"
            )
        angles.append(
            FaceAngleMetadataResponse(
                id=str(emb.id),
                angle_label=emb.angle_label,
                quality_score=emb.quality_score,
                created_at=emb.created_at,
                image_url=image_url,
            )
        )

    return FaceRegistrationDetailResponse(
        user_id=user_id,
        available=True,
        registered_at=registration.registered_at,
        embedding_dim=512,
        angles=angles,
    )


@router.get(
    "/registrations/{user_id}/images/{angle_label}",
    status_code=status.HTTP_200_OK,
    include_in_schema=True,
)
async def get_registration_image(
    user_id: str,
    angle_label: str,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    **Admin-only: Registration Image Bytes**

    Returns the stored JPEG for a specific registration angle. Used by the
    admin live-feed face-comparison sheet to render `<img>` tags.

    - 404 if there is no active registration or no embedding row for the
      given angle.
    - 410 Gone when the DB row points at a file that is no longer on disk
      (distinct from 404 — useful signal for backfill / storage drift).
    - Cache-Control is 5 min, `private` — files never change once written.
    """
    from app.utils.face_image_storage import _is_allowed_angle_label

    if not _is_allowed_angle_label(angle_label):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown angle")

    face_repo = FaceRepository(db)
    registration = face_repo.get_by_user(user_id)
    if registration is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no registration")

    embeddings = face_repo.get_embeddings_by_registration(str(registration.id))
    match = next(
        (e for e in embeddings if e.angle_label == angle_label and e.image_storage_key),
        None,
    )
    if match is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="angle not stored")

    storage = FaceImageStorage()
    try:
        path = storage.resolve_path(match.image_storage_key)
    except FileNotFoundError:
        # DB row points at a missing file — distinct state from "never had one".
        logger.warning(
            f"Registration image missing on disk for user {user_id} angle {angle_label} "
            f"(key={match.image_storage_key})"
        )
        raise HTTPException(
            status_code=status.HTTP_410_GONE, detail="image_missing_on_disk"
        )

    # Audit the byte fetch (not the index call — would flood audit on a poll).
    try:
        log_audit(
            db,
            admin_id=current_user.id,
            action="face.registered_images.view",
            target_type="user",
            target_id=user_id,
            details=f"angle={angle_label}",
        )
    except Exception:
        # Audit failures should not break the read.
        logger.warning("log_audit failed for face.registered_images.view", exc_info=True)

    return FileResponse(
        path=str(path),
        media_type="image/jpeg",
        headers={"Cache-Control": "private, max-age=300"},
    )


@router.get(
    "/live-crops/{schedule_id}/{user_id}",
    response_model=LiveCropsListResponse,
    status_code=status.HTTP_200_OK,
)
async def get_live_crops(
    schedule_id: str,
    user_id: str,
    limit: int = 10,
    _admin: User = Depends(get_current_admin),
):
    """
    **Admin-only: Recent Server-Captured Live Crops**

    Returns the most recent JPEGs (base64-encoded) that the realtime pipeline
    captured on the ``warming_up → recognized`` transition for this
    (schedule, user) pair. Backs the Phase-3 source-swap in the admin
    live-feed face-comparison sheet (`LiveCropPanel` with
    ``source.kind === 'server'``).

    Returns ``available=false`` on the VPS (``ENABLE_REDIS=false``) or when
    no crop key exists — the admin UI transparently falls back to the
    Phase-1 client-side canvas grab.
    """
    import json

    capped_limit = max(1, min(50, int(limit)))

    if not settings.ENABLE_REDIS:
        return LiveCropsListResponse(
            schedule_id=schedule_id, user_id=user_id, available=False
        )

    try:
        from app.redis_client import get_redis

        r = await get_redis()
        key = f"live_crops:{schedule_id}:{user_id}"
        raw_entries = await r.lrange(key, 0, capped_limit - 1)
    except Exception:
        logger.warning("Failed to read live crops from Redis", exc_info=True)
        return LiveCropsListResponse(
            schedule_id=schedule_id, user_id=user_id, available=False
        )

    crops: list[LiveCropResponse] = []
    for raw in raw_entries:
        try:
            data = json.loads(raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw)
            crops.append(
                LiveCropResponse(
                    crop_b64=data["crop_b64"],
                    captured_at=data["captured_at"],
                    confidence=float(data["confidence"]),
                    track_id=int(data["track_id"]),
                    bbox=[float(v) for v in data["bbox"]],
                )
            )
        except Exception:
            # Malformed entry — skip. Shouldn't happen because we control the writer.
            logger.debug("Skipping malformed live-crop entry", exc_info=True)

    return LiveCropsListResponse(
        schedule_id=schedule_id,
        user_id=user_id,
        available=bool(crops),
        crops=crops,
    )


@router.post("/validate-image", response_model=ImageQualityResponse, status_code=status.HTTP_200_OK)
async def validate_image(
    image: UploadFile = File(..., description="Single face image to validate"),
    current_user: User | None = Depends(get_optional_user),
):
    """
    **Validate a single face image quality (mobile pre-upload check)**

    Runs quality gating (blur, brightness, face size, detection confidence)
    on a single image using the mobile-calibrated blur threshold.

    Returns quality scores and pass/fail so the mobile app can prompt a
    retake *before* the user finishes all 5 captures.

    Works for both authenticated and unauthenticated users (initial registration).
    """
    image_bytes = await image.read()

    if len(image_bytes) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        return ImageQualityResponse(
            passed=False,
            blur_score=0.0,
            brightness=0.0,
            face_size_ratio=0.0,
            det_score=0.0,
            rejection_reasons=["Image exceeds maximum file size"],
        )

    try:
        face_data = insightface_model.get_face_with_quality(image_bytes)
    except ValueError as e:
        return ImageQualityResponse(
            passed=False,
            blur_score=0.0,
            brightness=0.0,
            face_size_ratio=0.0,
            det_score=0.0,
            rejection_reasons=[str(e)],
        )

    quality = assess_quality(
        image_bgr=face_data["image_bgr"],
        det_score=face_data["det_score"],
        bbox=face_data["bbox"],
        image_shape=face_data["image_bgr"].shape,
        blur_threshold_override=settings.QUALITY_BLUR_THRESHOLD_MOBILE,
    )

    return ImageQualityResponse(
        passed=quality.passed,
        blur_score=quality.blur_score,
        brightness=quality.brightness,
        face_size_ratio=quality.face_size_ratio,
        det_score=quality.det_score,
        rejection_reasons=quality.rejection_reasons,
    )


@router.post("/recognize", response_model=FaceRecognizeResponse, status_code=status.HTTP_200_OK)
async def recognize_face(
    request: FaceRecognizeRequest,
    db: Session = Depends(get_db),
    _api_key: None = Depends(verify_edge_api_key),
):
    """
    **Recognize Single Face (Testing)**

    Test face recognition with a single image.

    - **image**: Base64-encoded JPEG image

    Returns matched user ID and confidence if face is recognized.

    **Note:** This is a testing endpoint. Production face recognition
    is done via the Edge API (`/face/process`).

    Requires Edge API key (`X-API-Key` header).
    """
    face_service = FaceService(db)

    try:
        # Decode Base64 directly to bytes (skip PIL round-trip)
        b64_str = request.image
        if "," in b64_str:
            b64_str = b64_str.split(",", 1)[1]
        img_bytes = base64.b64decode(b64_str, validate=True)

        # Recognize
        user_id, confidence = await face_service.recognize_face(img_bytes)

        return FaceRecognizeResponse(success=True, matched=user_id is not None, user_id=user_id, confidence=confidence)

    except Exception as e:
        logger.error(f"Face recognition failed: {e}")
        raise


# ===== CRITICAL: Edge API for Raspberry Pi =====

# In-memory cache for request deduplication (simple implementation)
# In production: use Redis with TTL
_request_cache = {}


def _is_duplicate_request(request_id: str, room_id: str, timestamp: datetime) -> bool:
    """
    Check if this request was already processed (idempotency)

    Uses in-memory cache with 5-minute TTL.
    In production, use Redis for distributed deduplication.
    """
    if not request_id:
        return False

    cache_key = f"{request_id}:{room_id}:{timestamp.isoformat()}"

    # Clean expired entries (older than 5 minutes)
    now = datetime.now()
    expired_keys = [k for k, v in _request_cache.items() if now - v > timedelta(minutes=5)]
    for k in expired_keys:
        del _request_cache[k]

    # Check if already processed
    if cache_key in _request_cache:
        logger.info(f"Duplicate request detected: {cache_key}")
        return True

    # Mark as processed
    _request_cache[cache_key] = now
    return False


@router.post("/process", response_model=EdgeProcessResponse, status_code=status.HTTP_200_OK)
async def process_faces(
    request: EdgeProcessRequest,
    db: Session = Depends(get_db),
    _api_key: None = Depends(verify_edge_api_key),
):
    """
    **Edge API: Process Faces from Raspberry Pi**

    ⚠️ **CRITICAL ENDPOINT** - This is the primary interface for continuous presence tracking.

    **Purpose:**
    - Raspberry Pi sends detected faces for recognition
    - Backend recognizes faces and logs presence
    - Used for continuous attendance monitoring and early-leave detection

    **Request:**
    - **room_id**: Room UUID or identifier
    - **timestamp**: Scan timestamp (ISO format)
    - **faces**: Array of face data:
      - **image**: Base64-encoded JPEG (160x160 or larger)
      - **bbox**: Bounding box [x, y, w, h] (optional, for tracking)

    **Response:**
    - **processed**: Number of faces processed
    - **matched**: Array of matched users with confidence scores
    - **unmatched**: Number of faces that didn't match

    **Example Request:**
    ```json
    {
      "room_id": "uuid-room-101",
      "timestamp": "2024-01-15T10:30:00Z",
      "faces": [
        {
          "image": "base64_encoded_jpeg_data",
          "bbox": [100, 150, 112, 112]
        }
      ]
    }
    ```

    **Example Response:**
    ```json
    {
      "success": true,
      "data": {
        "processed": 5,
        "matched": [
          {"user_id": "uuid-1", "confidence": 0.85},
          {"user_id": "uuid-2", "confidence": 0.92}
        ],
        "unmatched": 3
      }
    }
    ```

    **Authentication:**
    - Requires Edge API key (`X-API-Key` header)

    **Rate Limiting:**
    - Recommended: 60-second intervals between scans
    - Maximum: 1 request per second per room

    **Idempotency:**
    - Use request_id to prevent duplicate processing
    - Same request_id within 5 minutes returns cached result

    **Error Handling:**
    - Returns success=true for successfully processed requests (even if no faces matched)
    - Returns success=false with error code for failures
    - Error codes guide retry logic:
      - INVALID_IMAGE_FORMAT: Don't retry (permanent failure)
      - RECOGNITION_FAILED: Retry (transient failure)
      - DATABASE_UNAVAILABLE: Retry with backoff
    """
    start_time = time.time()

    # Check for duplicate request (idempotency)
    if _is_duplicate_request(request.request_id, request.room_id, request.timestamp):
        logger.warning(f"Duplicate request ignored: request_id={request.request_id}")
        return EdgeProcessResponse(
            success=True,
            data=EdgeProcessResponseData(processed=0, matched=[], unmatched=0, processing_time_ms=0, presence_logged=0),
        )

    # --- Synchronous path ---
    face_service = FaceService(db)

    processed_count = 0
    matched_users: list[MatchedUser] = []
    unmatched_count = 0
    face_errors = []

    logger.info(
        f"Processing {len(request.faces)} faces from room {request.room_id} "
        f"at {request.timestamp} (request_id={request.request_id})"
    )

    # Process each face (sequential for now, can be parallelized later)
    for i, face_data in enumerate(request.faces):
        try:
            # Decode Base64 image with validation
            try:
                image = face_service.facenet.decode_base64_image(face_data.image, validate_size=True)
            except ValueError as e:
                # Invalid image format - don't retry
                error_msg = f"Face {i + 1}: {str(e)}"
                logger.warning(error_msg)
                face_errors.append({"face_index": i, "error": "INVALID_IMAGE_FORMAT", "message": str(e)})
                unmatched_count += 1
                continue

            # Convert to bytes
            img_bytes = io.BytesIO()
            image.save(img_bytes, format="JPEG")
            img_bytes = img_bytes.getvalue()

            # Recognize face using margin-aware search
            processed_count += 1
            try:
                embedding = face_service.facenet.get_embedding(img_bytes)
                match_result = face_service.faiss.search_with_margin(
                    embedding,
                    k=settings.RECOGNITION_TOP_K,
                    threshold=settings.RECOGNITION_THRESHOLD,
                    margin=settings.RECOGNITION_MARGIN,
                )

                if match_result["user_id"]:
                    # Face matched
                    matched_users.append(
                        MatchedUser(
                            user_id=match_result["user_id"],
                            confidence=match_result["confidence"],
                        )
                    )
                    if match_result["is_ambiguous"]:
                        logger.warning(f"Ambiguous match for face {i + 1} in room {request.room_id}")
                    logger.debug(
                        f"Face {i + 1} matched: user {match_result['user_id']}, "
                        f"confidence {match_result['confidence']:.3f}"
                    )
                else:
                    # Face not matched
                    unmatched_count += 1
                    logger.debug(f"Face {i + 1} not matched")

            except Exception as e:
                # Recognition failed - can retry
                error_msg = f"Face {i + 1}: Recognition failed: {str(e)}"
                logger.error(error_msg)
                face_errors.append({"face_index": i, "error": "RECOGNITION_FAILED", "message": str(e)})
                unmatched_count += 1

        except Exception as e:
            # Unexpected error
            logger.exception(f"Unexpected error processing face {i + 1}: {e}")
            face_errors.append({"face_index": i, "error": "PROCESSING_FAILED", "message": str(e)})
            unmatched_count += 1

    # Log presence to attendance system for matched users
    presence_logged = 0
    if matched_users:
        try:
            schedule_repo = ScheduleRepository(db)
            presence_service = PresenceService(db)  # No WebSocket manager for Edge API

            # Get current schedule for this room at the given timestamp
            scan_time = request.timestamp.time()
            scan_day = request.timestamp.weekday()

            # Find schedule that matches room and time
            try:
                current_schedule = schedule_repo.get_current_schedule(request.room_id, scan_day, scan_time)
            except (ValueError, Exception) as e:
                logger.warning(f"Invalid room_id format or schedule lookup failed: {e}")
                current_schedule = None

            if current_schedule:
                schedule_id = str(current_schedule.id)

                # Log each detected user to presence system
                for matched_user in matched_users:
                    try:
                        await presence_service.feed_detection(
                            schedule_id=schedule_id, user_id=matched_user.user_id, confidence=matched_user.confidence
                        )
                        presence_logged += 1
                        logger.debug(
                            f"Logged presence: user {matched_user.user_id}, "
                            f"schedule {schedule_id}, confidence {matched_user.confidence:.3f}"
                        )
                    except Exception as e:
                        logger.error(f"Failed to log presence for user {matched_user.user_id}: {e}")

                logger.info(f"Logged {presence_logged}/{len(matched_users)} detections to schedule {schedule_id}")
            else:
                logger.warning(
                    f"No active schedule found for room {request.room_id} at {scan_time}. "
                    "Face recognition completed but presence not logged."
                )

        except Exception as e:
            logger.error(f"Failed to log presence to attendance system: {e}")
            # Continue with response even if presence logging fails

    # Calculate processing time
    processing_time_ms = int((time.time() - start_time) * 1000)

    logger.info(
        f"Edge API results - Processed: {processed_count}, "
        f"Matched: {len(matched_users)}, Unmatched: {unmatched_count}, "
        f"Presence logged: {presence_logged}, Time: {processing_time_ms}ms"
    )

    # Log any errors that occurred
    if face_errors:
        logger.warning(f"Face processing errors: {face_errors}")

    return EdgeProcessResponse(
        success=True,
        data=EdgeProcessResponseData(
            processed=processed_count,
            matched=[user.model_dump() for user in matched_users],
            unmatched=unmatched_count,
            processing_time_ms=processing_time_ms,
            presence_logged=presence_logged,
        ),
    )


@router.post("/gone", status_code=200)
async def face_gone(
    request: FaceGoneRequest,
    db: Session = Depends(get_db),
    _api_key: None = Depends(verify_edge_api_key),
):
    """Receive face_gone events from RPi smart sampler."""
    if request.room_id and request.track_ids:
        presence_service = PresenceService(db)
        await presence_service.handle_face_gone(request.room_id, request.track_ids, request.timestamp)

    return {"status": "ok", "processed": len(request.track_ids)}


@router.get("/statistics", status_code=status.HTTP_200_OK)
async def get_face_statistics(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    **Get Face Recognition Statistics**

    Get statistics about face registrations and FAISS index.

    Returns:
    - Number of active registrations
    - FAISS index status
    - Total vectors in index

    Requires authentication.
    """
    face_service = FaceService(db)
    stats = face_service.get_statistics()

    return {"success": True, "data": stats}


@router.delete("/{user_id}", status_code=status.HTTP_200_OK)
async def deregister_face(user_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    **Deregister Face**

    Remove face registration for a user.

    - Students can only deregister their own face
    - Admins can deregister any user's face

    **Warning:** This will rebuild the FAISS index, which may take time.

    Requires authentication.
    """
    from app.models.user import UserRole

    # Students can only deregister their own face
    if current_user.role == UserRole.STUDENT and str(current_user.id) != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Students can only deregister their own face")

    face_service = FaceService(db)
    await face_service.deregister_face(user_id)

    return {"success": True, "message": "Face deregistered successfully"}


@router.post(
    "/cctv-enroll/{user_id}",
    response_model=CctvEnrollResponse,
    status_code=status.HTTP_201_CREATED,
)
async def cctv_enroll_user(
    user_id: str,
    body: CctvEnrollRequest,
    request: Request,
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """**Admin-only: CCTV-side enrolment for an existing student**

    Captures `num_captures` (default 5) high-quality face crops from the
    chosen room's live CCTV stream and adds them as canonical embeddings
    on top of the student's existing phone-captured registration. Closes
    the phone→CCTV cross-domain gap that otherwise causes mass false
    matches near the recognition threshold.

    Operator workflow:
      1. Stand the target student alone in front of the chosen camera so
         exactly one face is visible.
      2. POST this endpoint. The backend grabs frames at 1 s intervals,
         skipping frames that have 0 or >1 faces or that are too small /
         blurry.
      3. Inspect the response — `self_similarity_to_phone_mean` should be
         > 0.30 (0.50+ is good). If it isn't, the wrong student was in
         frame.

    Reuses the always-on FrameGrabber for the room when one exists; falls
    back to spinning up a dedicated grabber if not (e.g. when the room's
    grabber wasn't preloaded at boot).
    """
    face_service = FaceService(db)

    # Reuse the always-on FrameGrabber for this room if one exists in app
    # state (preloaded at boot — see backend/app/main.py). Falling back to
    # a dedicated grabber works but spawns a second ffmpeg subprocess and
    # competes with the always-on grabber for the publisher's frames.
    provided_grabber = None
    try:
        room_id_str: str | None = None
        # body.room_code_or_id may be either a Room.code or Room.id
        from app.models.room import Room
        try:
            import uuid as _u
            r = db.query(Room).filter(Room.id == _u.UUID(body.room_code_or_id)).first()
        except (ValueError, AttributeError):
            r = None
        if r is None:
            r = db.query(Room).filter(Room.code == body.room_code_or_id).first()
        if r is not None:
            room_id_str = str(r.id)

        grabbers = getattr(request.app.state, "frame_grabbers", None) or {}
        if room_id_str and room_id_str in grabbers:
            provided_grabber = grabbers[room_id_str]
            logger.info(
                "cctv_enroll: reusing always-on FrameGrabber for room %s", room_id_str
            )
    except Exception:
        # Defensive — if anything goes wrong with the reuse path, fall
        # through to spinning a dedicated grabber inside the service.
        logger.debug("cctv_enroll: grabber reuse lookup failed", exc_info=True)
        provided_grabber = None

    try:
        result = await face_service.cctv_enroll(
            user_id=user_id,
            room_code_or_id=body.room_code_or_id,
            num_captures=body.num_captures,
            capture_interval=body.capture_interval_s,
            min_face_size_px=body.min_face_size_px,
            min_det_score=body.min_det_score,
            provided_grabber=provided_grabber,
        )
    except Exception as exc:
        logger.error("cctv_enroll failed for user %s: %s", user_id, exc)
        raise

    # Audit — high-impact admin action that mutates the FAISS index.
    try:
        log_audit(
            db,
            admin_id=_admin.id,
            action="face.cctv_enroll",
            target_type="user",
            target_id=user_id,
            details=(
                f"room={body.room_code_or_id} added={result['added']} "
                f"sim_to_phone_mean={result['self_similarity_to_phone_mean']:.3f}"
            ),
        )
    except Exception:
        logger.warning("log_audit failed for face.cctv_enroll", exc_info=True)

    return CctvEnrollResponse(success=True, user_id=user_id, **result)


@router.get("/camera-diagnostic", response_model=CameraDiagnosticResponse)
async def camera_diagnostic(
    current_user: User = Depends(get_current_user),
):
    """Diagnose camera setup: check face detection, lighting, and distance.

    Grabs a single frame from the RTSP stream, runs face detection,
    and reports quality metrics for each detected face along with a
    human-readable recommendation.

    Use this before going live to verify camera placement is adequate.
    """
    import numpy as np

    from app.services.frame_grabber import FrameGrabber

    # Try to get RTSP URL from room or default
    rtsp_url = settings.DEFAULT_RTSP_URL
    if not rtsp_url:
        from app.database import SessionLocal
        from app.models.room import Room

        db = SessionLocal()
        try:
            room = db.query(Room).first()
            if room and room.rtsp_url:
                rtsp_url = room.rtsp_url
        finally:
            db.close()

    if not rtsp_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No RTSP URL configured. Set DEFAULT_RTSP_URL or add a room.",
        )

    # Grab a single frame — FrameGrabber auto-starts FFmpeg in __init__
    import asyncio

    def _grab_frame() -> np.ndarray | None:
        grabber = FrameGrabber(
            rtsp_url=rtsp_url,
            fps=10.0,
            width=settings.FRAME_GRABBER_WIDTH,
            height=settings.FRAME_GRABBER_HEIGHT,
        )
        try:
            import time

            time.sleep(2.0)
            return grabber.grab()
        finally:
            grabber.stop()

    loop = asyncio.get_event_loop()
    frame = await loop.run_in_executor(None, _grab_frame)

    if frame is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No frame received from RTSP stream. Check camera connection.",
        )

    frame_h, frame_w = frame.shape[:2]
    frame_area = frame_h * frame_w

    # Run face detection
    raw_faces = insightface_model.app.get(frame) if insightface_model.app else []

    faces_info: list[CameraDiagnosticFace] = []
    for face in raw_faces:
        x1, y1, x2, y2 = face.bbox.astype(float)
        face_w = x2 - x1
        face_h = y2 - y1
        size_ratio = (face_w * face_h) / frame_area

        # Extract crop for quality analysis
        cx1, cy1 = max(0, int(x1)), max(0, int(y1))
        cx2, cy2 = min(frame_w, int(x2)), min(frame_h, int(y2))
        crop = frame[cy1:cy2, cx1:cx2]

        blur = compute_blur_score(crop) if crop.size > 0 else 0.0
        brightness = compute_brightness(crop) if crop.size > 0 else 0.0

        faces_info.append(
            CameraDiagnosticFace(
                bbox=[float(x1), float(y1), float(x2), float(y2)],
                size_ratio=round(size_ratio, 4),
                blur_score=round(blur, 1),
                brightness=round(brightness, 1),
                det_score=round(float(face.det_score), 3),
            )
        )

    face_count = len(faces_info)
    avg_size = np.mean([f.size_ratio for f in faces_info]) if faces_info else 0.0
    avg_bright = np.mean([f.brightness for f in faces_info]) if faces_info else 0.0

    # Generate recommendation
    if face_count == 0:
        recommendation = "No faces detected. Check camera angle, distance, and make sure people are in view."
    elif avg_size < 0.005:
        recommendation = f"Faces too small (avg {avg_size:.3f} of frame). Move camera closer or zoom in."
    elif avg_bright < 50:
        recommendation = f"Too dark (avg brightness {avg_bright:.0f}/255). Improve lighting on faces."
    elif avg_bright > 200:
        recommendation = f"Overexposed (avg brightness {avg_bright:.0f}/255). Reduce direct lighting."
    else:
        recommendation = f"Camera setup looks good. {face_count} face(s) detected, avg size {avg_size:.1%} of frame."

    return CameraDiagnosticResponse(
        frame_size=[frame_w, frame_h],
        face_count=face_count,
        faces=faces_info,
        avg_face_size_ratio=round(float(avg_size), 4),
        avg_brightness=round(float(avg_bright), 1),
        recommendation=recommendation,
    )
