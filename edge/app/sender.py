"""
HTTP Sender for Backend Communication

Handles HTTP POST requests to backend API with retry logic and error handling.

Features:
- Async HTTP client using httpx
- Automatic retry with exponential backoff
- Connection pooling and timeout management
- Error classification and logging
- Response validation
- Session status polling for session-aware scanning
"""

import asyncio
from datetime import datetime
from typing import Any

import httpx

from app.config import config, logger
from app.processor import FaceData


class BackendSender:
    """
    Sends processed faces to backend API.

    Implements robust HTTP communication with retry logic and error handling.
    """

    def __init__(self):
        self.base_url = config.BACKEND_URL
        self.endpoint = "/api/v1/face/process"
        self.timeout = config.HTTP_TIMEOUT
        self.max_retries = config.HTTP_MAX_RETRIES

        # HTTP client (created on first use)
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """
        Get or create HTTP client.

        Returns:
            Async HTTP client instance
        """
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            )
        return self._client

    async def send_faces(
        self, faces: list[FaceData], room_id: str, timestamp: datetime | None = None
    ) -> dict[str, Any]:
        """
        Send detected faces to backend API.

        Args:
            faces: List of processed face data
            room_id: Room identifier
            timestamp: Scan timestamp (defaults to now)

        Returns:
            API response as dictionary

        Raises:
            httpx.HTTPError: On HTTP error
            Exception: On other errors

        Notes:
            - Uses POST /api/v1/face/process endpoint
            - Payload matches EdgeProcessRequest schema
            - Returns EdgeProcessResponse
        """
        if timestamp is None:
            timestamp = datetime.utcnow()

        # Build request payload
        payload = {
            "room_id": room_id,
            "timestamp": timestamp.isoformat() + "Z",
            "faces": [face.to_dict() for face in faces],
        }

        # Get endpoint URL
        url = config.get_api_endpoint(self.endpoint)

        logger.debug(f"Sending {len(faces)} faces to {url}")

        try:
            client = await self._get_client()

            # Send POST request
            response = await client.post(url, json=payload)

            # Accept both 200 (immediate) and 202 (batch-queued) as success
            if response.status_code not in (200, 202):
                response.raise_for_status()

            # Parse response
            result = response.json()

            if response.status_code == 202:
                logger.info(f"Backend accepted batch (202): {len(faces)} faces queued for processing")
            else:
                logger.info(
                    f"Backend response: processed={result.get('data', {}).get('processed', 0)}, "
                    f"matched={len(result.get('data', {}).get('matched', []))}, "
                    f"unmatched={result.get('data', {}).get('unmatched', 0)}"
                )

            return result

        except httpx.TimeoutException as e:
            logger.error(f"Backend request timeout after {self.timeout}s: {e}")
            raise

        except httpx.HTTPStatusError as e:
            logger.error(f"Backend HTTP error {e.response.status_code}: {e}")
            raise

        except httpx.RequestError as e:
            logger.error(f"Backend request error: {e}")
            raise

        except Exception as e:
            logger.error(f"Unexpected error sending faces: {e}")
            raise

    async def send_face_gone(self, room_id: str, track_ids: list):
        """Notify backend that tracked faces have disappeared."""
        payload = {
            "room_id": room_id,
            "event": "face_gone",
            "track_ids": track_ids,
            "timestamp": datetime.utcnow().isoformat(),
        }
        try:
            client = await self._get_client()
            await client.post(
                f"{self.base_url}/api/v1/face/gone",
                json=payload,
                timeout=5,
            )
        except Exception:
            pass  # Non-critical, presence service handles via timeout

    async def send_with_retry(
        self, faces: list[FaceData], room_id: str, timestamp: datetime | None = None, max_attempts: int | None = None
    ) -> dict[str, Any] | None:
        """
        Send faces with automatic retry on failure.

        Args:
            faces: List of processed face data
            room_id: Room identifier
            timestamp: Scan timestamp
            max_attempts: Maximum retry attempts (defaults to config)

        Returns:
            API response or None if all retries failed

        Notes:
            - Uses exponential backoff (1s, 2s, 4s, ...)
            - Returns None on permanent failure
            - Does not raise exceptions
        """
        if max_attempts is None:
            max_attempts = self.max_retries

        last_error = None

        for attempt in range(1, max_attempts + 1):
            try:
                result = await self.send_faces(faces, room_id, timestamp)
                return result

            except httpx.HTTPStatusError as e:
                # 4xx errors are permanent (bad request, auth error, etc.)
                if 400 <= e.response.status_code < 500:
                    logger.error(f"Permanent HTTP error {e.response.status_code}, not retrying")
                    return None

                last_error = e

            except Exception as e:
                last_error = e

            # Retry logic
            if attempt < max_attempts:
                # Exponential backoff: 1s, 2s, 4s, ...
                backoff = 2 ** (attempt - 1)
                logger.warning(f"Send failed (attempt {attempt}/{max_attempts}), retrying in {backoff}s...")
                await asyncio.sleep(backoff)
            else:
                logger.error(f"Send failed after {max_attempts} attempts: {last_error}")

        return None

    async def check_backend_health(self) -> bool:
        """
        Check if backend is reachable.

        Returns:
            True if backend is healthy, False otherwise

        Notes:
            - Uses a simple GET request to root endpoint
            - Does not require authentication
            - Fast timeout (5 seconds)
        """
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/", timeout=5.0)
            is_healthy = response.status_code < 500
            return is_healthy

        except Exception as e:
            logger.debug(f"Backend health check failed: {e}")
            return False

    async def check_session_status(self, room_id: str) -> tuple[bool, str | None]:
        """
        Check if there is an active attendance session for a given room.

        Polls GET /api/v1/presence/sessions/room-status?room_id={room_id}

        Args:
            room_id: Room UUID to check

        Returns:
            Tuple of (active, schedule_id):
                - active: True if there is an active session in this room
                - schedule_id: The schedule ID of the active session, or None
        """
        url = config.get_api_endpoint("/api/v1/presence/sessions/room-status")

        try:
            client = await self._get_client()
            response = await client.get(url, params={"room_id": room_id}, timeout=10.0)
            response.raise_for_status()

            data = response.json()
            active = data.get("active", False)
            schedule_id = data.get("schedule_id", None)

            return (active, schedule_id)

        except httpx.TimeoutException as e:
            logger.warning(f"Session status check timed out: {e}")
            return (False, None)

        except httpx.HTTPStatusError as e:
            logger.warning(f"Session status check HTTP error {e.response.status_code}: {e}")
            return (False, None)

        except httpx.RequestError as e:
            logger.warning(f"Session status check request error: {e}")
            return (False, None)

        except Exception as e:
            logger.warning(f"Session status check unexpected error: {e}")
            return (False, None)

    async def close(self) -> None:
        """
        Close HTTP client and release resources.
        """
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
            logger.debug("HTTP client closed")

    async def __aenter__(self):
        """Support async 'with' statement"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Support async 'with' statement"""
        await self.close()

    def get_status(self) -> dict:
        """
        Get sender status information.

        Returns:
            Dictionary with sender configuration
        """
        return {
            "base_url": self.base_url,
            "endpoint": self.endpoint,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "client_active": self._client is not None and not self._client.is_closed,
        }


# Synchronous sender using httpx.Client (no event-loop issues)
class SyncBackendSender:
    """
    Synchronous HTTP sender for the edge device.

    Uses httpx.Client directly to avoid asyncio.run() event-loop lifecycle
    issues that cause 'Event loop is closed' errors on repeated calls.
    """

    def __init__(self):
        self.base_url = config.BACKEND_URL
        self.endpoint = "/api/v1/face/process"
        self.timeout = config.HTTP_TIMEOUT
        self.max_retries = config.HTTP_MAX_RETRIES
        self._client: httpx.Client | None = None

    def _get_client(self) -> httpx.Client:
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(
                timeout=httpx.Timeout(self.timeout),
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            )
        return self._client

    def send_faces(
        self,
        faces: list[FaceData],
        room_id: str,
        timestamp: datetime | None = None,
    ) -> dict[str, Any]:
        if timestamp is None:
            timestamp = datetime.utcnow()

        payload = {
            "room_id": room_id,
            "timestamp": timestamp.isoformat() + "Z",
            "faces": [face.to_dict() for face in faces],
        }
        url = config.get_api_endpoint(self.endpoint)
        client = self._get_client()
        response = client.post(url, json=payload)
        # Accept both 200 (immediate) and 202 (batch-queued) as success
        if response.status_code not in (200, 202):
            response.raise_for_status()
        result = response.json()
        if response.status_code == 202:
            logger.info(f"Backend accepted batch (202): {len(faces)} faces queued for processing")
        else:
            logger.info(
                f"Backend response: processed={result.get('data', {}).get('processed', 0)}, "
                f"matched={len(result.get('data', {}).get('matched', []))}, "
                f"unmatched={result.get('data', {}).get('unmatched', 0)}"
            )
        return result

    def send_face_gone(self, room_id: str, track_ids: list):
        """Notify backend that tracked faces have disappeared."""
        payload = {
            "room_id": room_id,
            "event": "face_gone",
            "track_ids": track_ids,
            "timestamp": datetime.utcnow().isoformat(),
        }
        try:
            client = self._get_client()
            client.post(
                f"{self.base_url}/api/v1/face/gone",
                json=payload,
                timeout=5,
            )
        except Exception:
            pass  # Non-critical, presence service handles via timeout

    def send_with_retry(
        self,
        faces: list[FaceData],
        room_id: str,
        timestamp: datetime | None = None,
        max_attempts: int | None = None,
    ) -> dict[str, Any] | None:
        if max_attempts is None:
            max_attempts = self.max_retries

        import time as _time

        last_error = None
        for attempt in range(1, max_attempts + 1):
            try:
                return self.send_faces(faces, room_id, timestamp)
            except httpx.HTTPStatusError as e:
                if 400 <= e.response.status_code < 500:
                    logger.error(f"Permanent HTTP error {e.response.status_code}, not retrying")
                    return None
                last_error = e
            except Exception as e:
                last_error = e

            if attempt < max_attempts:
                backoff = 2 ** (attempt - 1)
                logger.warning(f"Send failed (attempt {attempt}/{max_attempts}), retrying in {backoff}s...")
                _time.sleep(backoff)
            else:
                logger.error(f"Send failed after {max_attempts} attempts: {last_error}")
        return None

    def check_backend_health(self) -> bool:
        try:
            client = self._get_client()
            response = client.get(f"{self.base_url}/", timeout=5.0)
            return response.status_code < 500
        except Exception as e:
            logger.debug(f"Backend health check failed: {e}")
            return False

    def check_session_status(self, room_id: str) -> tuple[bool, str | None]:
        url = config.get_api_endpoint("/api/v1/presence/sessions/room-status")
        try:
            client = self._get_client()
            response = client.get(url, params={"room_id": room_id}, timeout=10.0)
            response.raise_for_status()
            data = response.json()
            return (data.get("active", False), data.get("schedule_id", None))
        except httpx.TimeoutException as e:
            logger.warning(f"Session status check timed out: {e}")
            return (False, None)
        except httpx.HTTPStatusError as e:
            logger.warning(f"Session status check HTTP error {e.response.status_code}: {e}")
            return (False, None)
        except Exception as e:
            logger.warning(f"Session status check error: {e}")
            return (False, None)

    def close(self) -> None:
        if self._client and not self._client.is_closed:
            self._client.close()
            self._client = None

    def get_status(self) -> dict:
        return {
            "base_url": self.base_url,
            "endpoint": self.endpoint,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "client_active": self._client is not None and not self._client.is_closed,
        }
