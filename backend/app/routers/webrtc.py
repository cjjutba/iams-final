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
from app.models.room import Room
from app.repositories.schedule_repository import ScheduleRepository
from app.schemas.webrtc import WebRTCOfferRequest
from app.services.camera_config import get_camera_url
from app.services.webrtc_service import webrtc_service

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
    db: Session = Depends(get_db),
):
    """
    Forward WebRTC SDP offer to mediamtx WHEP endpoint.

    Flow:
      1. Validate schedule exists
      2. Resolve room → RTSP camera URL
      3. Ensure mediamtx path exists for this room
      4. Forward SDP offer to mediamtx WHEP endpoint
      5. Return SDP answer to mobile app

    Auth is not required — the live stream WebSocket endpoint is also
    unauthenticated, and this is just a signaling proxy to mediamtx.
    """
    # 1. Validate schedule
    schedule_repo = ScheduleRepository(db)
    schedule = schedule_repo.get_by_id(str(schedule_id))
    if schedule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule not found: {schedule_id}",
        )

    # 2. Resolve room → annotated stream path on mediamtx
    #    The video pipeline publishes to {room_id}/annotated with bounding boxes
    #    burned in. Fall back to {room_id}/raw if annotated isn't available.
    room_id = str(schedule.room_id)
    room = db.query(Room).filter(Room.id == schedule.room_id).first()
    base_key = room.stream_key if room and room.stream_key else room_id

    # Prefer the annotated stream (has bounding boxes), fall back to raw
    annotated_key = f"{base_key}/annotated"
    raw_key = f"{base_key}/raw"

    # 3. Check which stream is available on mediamtx
    #    Always prefer annotated (H.264, has bounding boxes).
    #    Raw stream is H.265 which WebRTC doesn't support — never use it.
    path_ok = await webrtc_service.check_path_exists(annotated_key)
    if path_ok:
        stream_key = annotated_key
    else:
        logger.warning(
            f"WebRTC: annotated stream '{annotated_key}' not ready. "
            f"Pipeline may be starting up. Client should retry."
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Video pipeline is starting up — please retry in a few seconds",
        )

    # 4. Forward SDP offer to mediamtx WHEP
    try:
        answer_sdp, _ = await webrtc_service.forward_whep_offer(stream_key, body.sdp)
    except httpx.HTTPStatusError as exc:
        logger.error(f"WHEP offer failed for room {stream_key}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WebRTC stream unavailable — camera may be offline",
        ) from exc
    except Exception as exc:
        logger.error(f"Unexpected WHEP error for room {stream_key}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error during WebRTC setup",
        ) from exc

    # 5. Return SDP answer
    logger.info(f"WebRTC offer forwarded: schedule={schedule_id}, stream_key={stream_key}")
    return {
        "success": True,
        "data": {
            "sdp": answer_sdp,
            "type": "answer",
        },
    }
