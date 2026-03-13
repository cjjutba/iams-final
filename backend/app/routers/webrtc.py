# backend/app/routers/webrtc.py
"""
WebRTC Router

Secure signaling proxy between the mobile app and mediamtx.
Mobile clients never talk to mediamtx directly — FastAPI validates
the JWT token and proxies the WHEP offer/answer.

Endpoints:
    GET  /api/v1/webrtc/config                — ICE server list (STUN/TURN)
    POST /api/v1/webrtc/{schedule_id}/offer   — WHEP signaling proxy
"""

import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import logger
from app.database import get_db
from app.models.enrollment import Enrollment
from app.models.user import User, UserRole
from app.repositories.schedule_repository import ScheduleRepository
from app.schemas.webrtc import WebRTCOfferRequest
from app.services.camera_config import get_camera_url
from app.services.webrtc_service import webrtc_service
from app.utils.dependencies import get_current_user

router = APIRouter()


@router.get("/config")
async def get_webrtc_config():
    """
    Get ICE server configuration for WebRTC peer connections.

    Returns STUN and optional TURN server details from backend config.
    Mobile app calls this before creating RTCPeerConnection.
    No authentication required (ICE config is not sensitive).
    """
    ice_servers = webrtc_service.get_ice_servers()
    return {
        "success": True,
        "data": {"ice_servers": ice_servers},
    }


@router.post("/{schedule_id}/offer")
async def create_webrtc_offer(
    schedule_id: uuid.UUID,
    body: WebRTCOfferRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Forward WebRTC SDP offer to mediamtx WHEP endpoint.

    Flow:
      1. Validate schedule exists
      2. Authorize: students must be enrolled, faculty must own the schedule
      3. Resolve room → RTSP camera URL
      4. Ensure mediamtx path exists for this room
      5. Forward SDP offer to mediamtx WHEP endpoint
      6. Return SDP answer to mobile app

    The mobile app then calls setRemoteDescription(answer) to complete
    the WebRTC handshake and start streaming.

    Requires: valid JWT token; role-based access (student=enrolled, faculty=owns schedule)
    """
    # 1. Validate schedule
    schedule_repo = ScheduleRepository(db)
    schedule = schedule_repo.get_by_id(str(schedule_id))
    if schedule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule not found: {schedule_id}",
        )

    # 2. Authorization
    if current_user.role == UserRole.STUDENT:
        enrollment = (
            db.query(Enrollment)
            .filter(
                Enrollment.student_id == current_user.id,
                Enrollment.schedule_id == schedule.id,
            )
            .first()
        )
        if not enrollment:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enrolled in this schedule",
            )
    elif current_user.role == UserRole.FACULTY:
        if str(schedule.faculty_id) != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not own this schedule",
            )
    # ADMIN: no restriction

    # 3. Resolve camera RTSP URL (may be None in push mode)
    room_id = str(schedule.room_id)
    rtsp_url = get_camera_url(room_id, db)

    # 4. Ensure mediamtx path exists
    if rtsp_url:
        # Pull mode: tell mediamtx to pull from camera RTSP URL
        path_ok = await webrtc_service.ensure_path(room_id, rtsp_url)
    else:
        # Push mode: RPi pushes RTSP to mediamtx, just check path exists
        path_ok = await webrtc_service.check_path_exists(room_id)

    if not path_ok:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WebRTC stream unavailable — is the edge device streaming?",
        )

    # 5. Forward SDP offer to mediamtx WHEP
    try:
        answer_sdp, _ = await webrtc_service.forward_whep_offer(room_id, body.sdp)
    except httpx.HTTPStatusError as exc:
        logger.error(f"WHEP offer failed for room {room_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WebRTC stream unavailable — camera may be offline",
        ) from exc
    except Exception as exc:
        logger.error(f"Unexpected WHEP error for room {room_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error during WebRTC setup",
        ) from exc

    # 6. Return SDP answer
    logger.info(f"WebRTC offer forwarded: schedule={schedule_id}, room={room_id}, user={current_user.id}")
    return {
        "success": True,
        "data": {
            "sdp": answer_sdp,
            "type": "answer",
        },
    }
