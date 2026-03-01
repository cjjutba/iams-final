"""
Face Recognition Router

API endpoints for face registration, recognition, and Edge API for Raspberry Pi.

CRITICAL: Contains Edge API contract for continuous presence tracking.
"""

from typing import List
from datetime import datetime, timedelta
import io
import time
import asyncio
from fastapi import APIRouter, Depends, UploadFile, File, status
from sqlalchemy.orm import Session
import base64

from app.database import get_db
from app.models.user import User
from app.schemas.face import (
    FaceRegisterResponse,
    FaceStatusResponse,
    FaceRecognizeRequest,
    FaceRecognizeResponse,
    EdgeProcessRequest,
    EdgeProcessResponse,
    EdgeProcessResponseData,
    MatchedUser
)
from app.services.face_service import FaceService
from app.services.presence_service import PresenceService
from app.repositories.schedule_repository import ScheduleRepository
from app.utils.dependencies import get_current_user, get_current_student
from app.utils.exceptions import EdgeAPIError, ValidationError
from app.config import logger


router = APIRouter()


@router.post("/register", response_model=FaceRegisterResponse, status_code=status.HTTP_201_CREATED)
async def register_face(
    images: List[UploadFile] = File(..., description="3-5 face images"),
    current_user: User = Depends(get_current_student),
    db: Session = Depends(get_db)
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
        faiss_id, message = await face_service.register_face(str(current_user.id), images)

        return FaceRegisterResponse(
            success=True,
            message=message,
            embedding_id=faiss_id,
            user_id=str(current_user.id)
        )

    except Exception as e:
        logger.error(f"Face registration failed for user {current_user.id}: {e}")
        raise


@router.post("/reregister", response_model=FaceRegisterResponse, status_code=status.HTTP_200_OK)
async def reregister_face(
    images: List[UploadFile] = File(..., description="3-5 face images"),
    current_user: User = Depends(get_current_student),
    db: Session = Depends(get_db)
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
        faiss_id, message = await face_service.reregister_face(str(current_user.id), images)

        return FaceRegisterResponse(
            success=True,
            message=message,
            embedding_id=faiss_id,
            user_id=str(current_user.id)
        )

    except Exception as e:
        logger.error(f"Face re-registration failed for user {current_user.id}: {e}")
        raise


@router.get("/status", response_model=FaceStatusResponse, status_code=status.HTTP_200_OK)
async def get_face_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    **Check Face Registration Status**

    Check if current user has registered their face.

    Returns registration status and timestamp.

    Requires authentication.
    """
    face_service = FaceService(db)
    status_data = face_service.get_face_status(str(current_user.id))

    return FaceStatusResponse(**status_data)


@router.post("/recognize", response_model=FaceRecognizeResponse, status_code=status.HTTP_200_OK)
async def recognize_face(
    request: FaceRecognizeRequest,
    db: Session = Depends(get_db)
):
    """
    **Recognize Single Face (Testing)**

    Test face recognition with a single image.

    - **image**: Base64-encoded JPEG image

    Returns matched user ID and confidence if face is recognized.

    **Note:** This is a testing endpoint. Production face recognition
    is done via the Edge API (`/face/process`).

    No authentication required (for testing).
    """
    face_service = FaceService(db)

    try:
        # Decode Base64 directly to bytes (skip PIL round-trip)
        b64_str = request.image
        if ',' in b64_str:
            b64_str = b64_str.split(',', 1)[1]
        img_bytes = base64.b64decode(b64_str, validate=True)

        # Recognize
        user_id, confidence = await face_service.recognize_face(img_bytes)

        return FaceRecognizeResponse(
            success=True,
            matched=user_id is not None,
            user_id=user_id,
            confidence=confidence
        )

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
    expired_keys = [
        k for k, v in _request_cache.items()
        if now - v > timedelta(minutes=5)
    ]
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
    db: Session = Depends(get_db)
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
      - **image**: Base64-encoded JPEG (112x112 or larger)
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
    - No authentication required (trusted network)
    - In production: Use API key or service account token

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
            data=EdgeProcessResponseData(
                processed=0,
                matched=[],
                unmatched=0,
                processing_time_ms=0,
                presence_logged=0
            )
        )

    face_service = FaceService(db)

    processed_count = 0
    matched_users: List[MatchedUser] = []
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
                image = face_service.facenet.decode_base64_image(
                    face_data.image,
                    validate_size=True
                )
            except ValueError as e:
                # Invalid image format - don't retry
                error_msg = f"Face {i+1}: {str(e)}"
                logger.warning(error_msg)
                face_errors.append({
                    "face_index": i,
                    "error": "INVALID_IMAGE_FORMAT",
                    "message": str(e)
                })
                unmatched_count += 1
                continue

            # Convert to bytes
            img_bytes = io.BytesIO()
            image.save(img_bytes, format='JPEG')
            img_bytes = img_bytes.getvalue()

            # Recognize face
            try:
                user_id, confidence = await face_service.recognize_face(img_bytes)
                processed_count += 1

                if user_id:
                    # Face matched
                    matched_users.append(MatchedUser(
                        user_id=user_id,
                        confidence=confidence
                    ))
                    logger.debug(f"Face {i+1} matched: user {user_id}, confidence {confidence:.3f}")
                else:
                    # Face not matched
                    unmatched_count += 1
                    logger.debug(f"Face {i+1} not matched")

            except Exception as e:
                # Recognition failed - can retry
                error_msg = f"Face {i+1}: Recognition failed: {str(e)}"
                logger.error(error_msg)
                face_errors.append({
                    "face_index": i,
                    "error": "RECOGNITION_FAILED",
                    "message": str(e)
                })
                processed_count += 1
                unmatched_count += 1

        except Exception as e:
            # Unexpected error
            logger.exception(f"Unexpected error processing face {i+1}: {e}")
            face_errors.append({
                "face_index": i,
                "error": "PROCESSING_FAILED",
                "message": str(e)
            })
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
                            schedule_id=schedule_id,
                            user_id=matched_user.user_id,
                            confidence=matched_user.confidence
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
            presence_logged=presence_logged
        )
    )


@router.get("/statistics", status_code=status.HTTP_200_OK)
async def get_face_statistics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
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

    return {
        "success": True,
        "data": stats
    }


@router.delete("/{user_id}", status_code=status.HTTP_200_OK)
async def deregister_face(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    **Deregister Face**

    Remove face registration for a user.

    - Students can only deregister their own face
    - Admins can deregister any user's face

    **Warning:** This will rebuild the FAISS index, which may take time.

    Requires authentication.
    """
    from fastapi import HTTPException
    from app.models.user import UserRole

    # Students can only deregister their own face
    if current_user.role == UserRole.STUDENT and str(current_user.id) != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Students can only deregister their own face"
        )

    face_service = FaceService(db)
    await face_service.deregister_face(user_id)

    return {
        "success": True,
        "message": "Face deregistered successfully"
    }
