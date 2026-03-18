"""Pipeline management API -- start/stop/status for video analytics pipelines."""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.config import settings

router = APIRouter()


class PipelineStartRequest(BaseModel):
    room_id: str
    room_name: str = ""
    subject: str = ""
    professor: str = ""
    total_enrolled: int = 0
    schedule_id: str | None = None
    rtsp_source: str | None = None  # Direct camera RTSP URL (bypasses mediamtx raw)


class PipelineStatusResponse(BaseModel):
    room_id: str
    alive: bool
    pid: int | None = None


@router.post("/start")
async def start_pipeline(req: PipelineStartRequest, request: Request):
    mgr = getattr(request.app.state, "pipeline_manager", None)
    if mgr is None:
        raise HTTPException(503, "Pipeline manager not initialized")

    # Resolve stream_key for mediamtx path (matches WebRTC router lookup)
    from app.database import get_db
    from app.models.room import Room
    db = next(get_db())
    try:
        room = db.query(Room).filter(Room.id == req.room_id).first()
        stream_key = room.stream_key if room and room.stream_key else req.room_id
    finally:
        db.close()

    config = {
        "room_id": req.room_id,
        "rtsp_source": req.rtsp_source or f"{settings.MEDIAMTX_RTSP_URL}/{stream_key}/raw",
        "rtsp_target": f"{settings.MEDIAMTX_RTSP_URL}/{stream_key}/annotated",
        "width": settings.PIPELINE_WIDTH,
        "height": settings.PIPELINE_HEIGHT,
        "fps": settings.PIPELINE_FPS,
        "room_name": req.room_name,
        "subject": req.subject,
        "professor": req.professor,
        "total_enrolled": req.total_enrolled,
        "det_model": settings.PIPELINE_DET_MODEL,
        "detector": settings.PIPELINE_DETECTOR,
    }
    mgr.start_pipeline(config)
    return {"status": "started", "room_id": req.room_id}


@router.post("/stop/{room_id}")
async def stop_pipeline(room_id: str, request: Request):
    mgr = getattr(request.app.state, "pipeline_manager", None)
    if mgr is None:
        raise HTTPException(503, "Pipeline manager not initialized")
    mgr.stop_pipeline(room_id)
    return {"status": "stopped", "room_id": room_id}


@router.get("/status", response_model=list[PipelineStatusResponse])
async def pipeline_status(request: Request):
    mgr = getattr(request.app.state, "pipeline_manager", None)
    if mgr is None:
        return []
    return mgr.get_status()
