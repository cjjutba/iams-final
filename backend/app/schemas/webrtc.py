# backend/app/schemas/webrtc.py
"""Pydantic schemas for WebRTC signaling endpoints."""
from pydantic import BaseModel, field_validator

_MAX_SDP_BYTES = 65_536  # 64 KB — real WHEP offers are 2-8 KB


class WebRTCOfferRequest(BaseModel):
    """SDP offer from the mobile RTCPeerConnection."""
    sdp: str
    type: str = "offer"

    @field_validator("sdp")
    @classmethod
    def sdp_max_length(cls, v: str) -> str:
        if len(v.encode()) > _MAX_SDP_BYTES:
            raise ValueError("SDP offer exceeds maximum allowed size (64 KB)")
        return v
