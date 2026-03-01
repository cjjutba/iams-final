"""
WebRTC Service

Manages mediamtx path lifecycle and proxies WebRTC WHEP signaling.
mediamtx is a single binary that bridges RTSP → WebRTC (WHEP protocol).

FastAPI calls this service to:
1. Create a mediamtx path for a room (source = camera RTSP URL)
2. Forward the mobile app's SDP offer to mediamtx's WHEP endpoint
3. Return the SDP answer to the mobile app
4. Clean up paths when no longer needed
"""

import httpx

from app.config import settings, logger


class WebRTCService:
    """Thin adapter over the mediamtx HTTP API and WHEP endpoint."""

    def get_ice_servers(self) -> list[dict]:
        """
        Build the ICE server list from settings.

        Returns a list ready to pass into RTCPeerConnection({ iceServers }).
        Always includes STUN; optionally includes TURN when configured.
        """
        stun_urls = [
            u.strip()
            for u in settings.WEBRTC_STUN_URLS.split(",")
            if u.strip()
        ]
        servers: list[dict] = [{"urls": stun_urls}]

        if settings.WEBRTC_TURN_URL:
            servers.append({
                "urls": [settings.WEBRTC_TURN_URL],
                "username": settings.WEBRTC_TURN_USERNAME,
                "credential": settings.WEBRTC_TURN_CREDENTIAL,
            })

        return servers

    async def ensure_path(self, room_id: str, rtsp_url: str) -> bool:
        """
        Create (or update) a mediamtx path that pulls from the camera RTSP URL.

        mediamtx will start pulling from rtsp_url on demand (when a viewer connects).

        Args:
            room_id:  Path name in mediamtx (matches the room UUID).
            rtsp_url: RTSP source URL of the camera.

        Returns:
            True on success, False if mediamtx is unreachable.
        """
        payload = {
            "source": rtsp_url,
            "sourceOnDemand": True,
        }
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    f"{settings.MEDIAMTX_API_URL}/v3/config/paths/add/{room_id}",
                    json=payload,
                )
                if resp.status_code == 400:
                    # Path already exists — patch it with the latest RTSP URL
                    resp = await client.patch(
                        f"{settings.MEDIAMTX_API_URL}/v3/config/paths/patch/{room_id}",
                        json=payload,
                    )
                ok = resp.status_code in (200, 201, 204)
                if not ok:
                    logger.error(
                        f"WebRTC: mediamtx path create/patch failed "
                        f"(room={room_id}, status={resp.status_code}): {resp.text}"
                    )
                return ok
        except httpx.ConnectError:
            logger.error(
                f"WebRTC: cannot reach mediamtx at {settings.MEDIAMTX_API_URL} "
                f"— is mediamtx running? (room={room_id})"
            )
            return False
        except Exception as exc:
            logger.error(f"WebRTC: unexpected error ensuring path for room {room_id}: {exc}")
            return False

    async def forward_whep_offer(
        self, room_id: str, sdp: str
    ) -> tuple[str, str]:
        """
        Forward the mobile app's SDP offer to mediamtx's WHEP endpoint.

        WHEP (WebRTC HTTP Egress Protocol) uses plain-text SDP bodies:
        - Request: POST /{path}/whep  Content-Type: application/sdp  body=offer_sdp
        - Response: 201 Created        Content-Type: application/sdp  body=answer_sdp
                    Location: <resource URL for teardown>

        Args:
            room_id: mediamtx path name (= room UUID).
            sdp:     SDP offer string from the mobile RTCPeerConnection.

        Returns:
            Tuple of (answer_sdp, resource_url).

        Raises:
            httpx.HTTPStatusError: if mediamtx rejects the offer.
        """
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{settings.MEDIAMTX_WEBRTC_URL}/{room_id}/whep",
                content=sdp,
                headers={"Content-Type": "application/sdp"},
            )
            resp.raise_for_status()
            resource_url = resp.headers.get("Location", "")
            return resp.text, resource_url

    async def delete_path(self, room_id: str) -> None:
        """
        Remove a mediamtx path. Called when the last viewer disconnects.

        Errors are swallowed — cleanup failures are non-fatal.
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.delete(
                    f"{settings.MEDIAMTX_API_URL}/v3/config/paths/delete/{room_id}"
                )
        except Exception as exc:
            logger.warning(f"WebRTC: failed to delete mediamtx path {room_id}: {exc}")


# Module-level singleton
webrtc_service = WebRTCService()
