# backend/app/schemas/webrtc.py
"""Pydantic schemas for WebRTC signaling endpoints."""
from pydantic import BaseModel


class WebRTCOfferRequest(BaseModel):
    """SDP offer from the mobile RTCPeerConnection."""
    sdp: str
    type: str = "offer"
