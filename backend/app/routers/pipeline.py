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


class PipelineStatusResponse(BaseModel):
    room_id: str
    alive: bool
    pid: int | None = None


@router.post("/start")
async def start_pipeline(req: PipelineStartRequest, request: Request):
    mgr = getattr(request.app.state, "pipeline_manager", None)
    if mgr is None:
        raise HTTPException(503, "Pipeline manager not initialized")

    config = {
        "room_id": req.room_id,
        "rtsp_source": f"{settings.MEDIAMTX_RTSP_URL}/{req.room_id}/raw",
        "rtsp_target": f"{settings.MEDIAMTX_RTSP_URL}/{req.room_id}/annotated",
        "width": settings.PIPELINE_WIDTH,
        "height": settings.PIPELINE_HEIGHT,
        "fps": settings.PIPELINE_FPS,
        "room_name": req.room_name,
        "subject": req.subject,
        "professor": req.professor,
        "total_enrolled": req.total_enrolled,
        "det_model": settings.PIPELINE_DET_MODEL,
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
