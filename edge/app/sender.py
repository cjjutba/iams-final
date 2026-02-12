"""
HTTP Sender for Backend Communication

Handles HTTP POST requests to backend API with retry logic and error handling.

Features:
- Async HTTP client using httpx
- Automatic retry with exponential backoff
- Connection pooling and timeout management
- Error classification and logging
- Response validation
"""

import asyncio
import httpx
from typing import List, Optional, Dict, Any
from datetime import datetime

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
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """
        Get or create HTTP client.

        Returns:
            Async HTTP client instance
        """
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
            )
        return self._client

    async def send_faces(
        self,
        faces: List[FaceData],
        room_id: str,
        timestamp: Optional[datetime] = None
    ) -> Dict[str, Any]:
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
            "faces": [face.to_dict() for face in faces]
        }

        # Get endpoint URL
        url = config.get_api_endpoint(self.endpoint)

        logger.debug(f"Sending {len(faces)} faces to {url}")

        try:
            client = await self._get_client()

            # Send POST request
            response = await client.post(url, json=payload)

            # Raise for HTTP errors
            response.raise_for_status()

            # Parse response
            result = response.json()

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

    async def send_with_retry(
        self,
        faces: List[FaceData],
        room_id: str,
        timestamp: Optional[datetime] = None,
        max_attempts: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
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
            response = await client.get(
                f"{self.base_url}/",
                timeout=5.0
            )
            is_healthy = response.status_code < 500
            return is_healthy

        except Exception as e:
            logger.debug(f"Backend health check failed: {e}")
            return False

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
            "client_active": self._client is not None and not self._client.is_closed
        }


# Synchronous wrapper for backward compatibility
class SyncBackendSender:
    """
    Synchronous wrapper for BackendSender.

    Provides synchronous interface by running async methods in event loop.
    """

    def __init__(self):
        self._async_sender = BackendSender()

    def send_faces(
        self,
        faces: List[FaceData],
        room_id: str,
        timestamp: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Synchronous send_faces"""
        return asyncio.run(self._async_sender.send_faces(faces, room_id, timestamp))

    def send_with_retry(
        self,
        faces: List[FaceData],
        room_id: str,
        timestamp: Optional[datetime] = None,
        max_attempts: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Synchronous send_with_retry"""
        return asyncio.run(
            self._async_sender.send_with_retry(faces, room_id, timestamp, max_attempts)
        )

    def check_backend_health(self) -> bool:
        """Synchronous health check"""
        return asyncio.run(self._async_sender.check_backend_health())

    def close(self) -> None:
        """Synchronous close"""
        asyncio.run(self._async_sender.close())

    def get_status(self) -> dict:
        """Get status"""
        return self._async_sender.get_status()
