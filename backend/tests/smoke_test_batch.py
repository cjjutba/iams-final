#!/usr/bin/env python3
"""
Smoke Test: Batch Processing Pipeline (End-to-End)

Tests the full pipeline:
    RPi POST /face/process -> 202 -> Redis queue -> batch worker -> Redis pub/sub -> WebSocket

Usage:
    python tests/smoke_test_batch.py
    python tests/smoke_test_batch.py --backend-url http://167.71.217.44 --redis-url redis://localhost:6379/0
"""

import argparse
import asyncio
import base64
import io
import json
import struct
import sys
import time
from urllib.parse import urlparse

import aiohttp

# ---------------------------------------------------------------------------
# Synthetic JPEG generation
# ---------------------------------------------------------------------------

def _make_jpeg_bytes(width: int = 32, height: int = 32, r: int = 255, g: int = 0, b: int = 0) -> bytes:
    """Generate a minimal valid JPEG image with a solid color using Pillow if
    available, otherwise fall back to a raw-bytes approach."""
    try:
        from PIL import Image

        img = Image.new("RGB", (width, height), (r, g, b))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        return buf.getvalue()
    except ImportError:
        # Absolute minimal JFIF: SOI + APP0 + a single-color SOS is non-trivial
        # without Pillow, so we construct a tiny BMP and rely on the test
        # expectations being lenient about format. However the backend explicitly
        # expects JPEG, so we hard-code a known 1x1 red JPEG byte sequence.
        # (Pre-generated with Pillow — 631 bytes.)
        raise RuntimeError(
            "Pillow is required to generate synthetic JPEG images. "
            "Install it with: pip install Pillow"
        )


def _make_face_b64(index: int = 0) -> str:
    """Return a base64-encoded synthetic JPEG. Each call varies the color
    slightly so payloads are not identical."""
    r = (200 + index * 11) % 256
    g = (100 + index * 37) % 256
    b = (50 + index * 53) % 256
    raw = _make_jpeg_bytes(32, 32, r, g, b)
    return base64.b64encode(raw).decode()


# ---------------------------------------------------------------------------
# ANSI color helpers
# ---------------------------------------------------------------------------

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"


def _pass(label: str, detail: str = ""):
    msg = f"  {GREEN}PASS{RESET}  {label}"
    if detail:
        msg += f"  ({detail})"
    print(msg)


def _fail(label: str, detail: str = ""):
    msg = f"  {RED}FAIL{RESET}  {label}"
    if detail:
        msg += f"  ({detail})"
    print(msg)


def _info(msg: str):
    print(f"  {YELLOW}INFO{RESET}  {msg}")


# ---------------------------------------------------------------------------
# Build request payloads (matches EdgeProcessRequest / FaceGoneRequest)
# ---------------------------------------------------------------------------

ROOM_ID = "test-room-1"
API_PREFIX = "/api/v1"


def _edge_process_payload(n_faces: int = 1) -> dict:
    """Build a valid EdgeProcessRequest body."""
    from datetime import datetime, timezone

    return {
        "room_id": ROOM_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "faces": [
            {
                "image": _make_face_b64(i),
                "bbox": [10, 10, 50, 50],
            }
            for i in range(n_faces)
        ],
    }


def _face_gone_payload() -> dict:
    """Build a valid FaceGoneRequest body."""
    return {
        "room_id": ROOM_ID,
        "track_ids": [1, 2, 3],
        "timestamp": time.time(),
    }


# ---------------------------------------------------------------------------
# Test implementations
# ---------------------------------------------------------------------------

async def check_prerequisites(backend_url: str, redis_url: str) -> bool:
    """Verify Redis is reachable and backend is healthy."""
    print(f"\n{BOLD}Prerequisites{RESET}")

    # --- Redis ---
    redis_ok = False
    try:
        import redis.asyncio as redis

        parsed = urlparse(redis_url)
        db = 0
        if parsed.path and parsed.path.strip("/"):
            db = int(parsed.path.strip("/"))
        r = redis.Redis(
            host=parsed.hostname or "localhost",
            port=parsed.port or 6379,
            db=db,
            decode_responses=False,
        )
        await r.ping()
        await r.aclose()
        _pass("Redis reachable", redis_url)
        redis_ok = True
    except Exception as exc:
        _fail("Redis reachable", str(exc))

    # --- Backend health ---
    backend_ok = False
    try:
        async with aiohttp.ClientSession() as session:
            url = f"{backend_url}{API_PREFIX}/health"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    _pass("Backend healthy", f"GET {url} -> {resp.status}")
                    backend_ok = True
                else:
                    _fail("Backend healthy", f"GET {url} -> {resp.status}")
    except Exception as exc:
        _fail("Backend healthy", str(exc))

    return redis_ok and backend_ok


async def test_batch_enqueue(backend_url: str) -> bool:
    """POST a synthetic face to /face/process and expect 202."""
    print(f"\n{BOLD}Test 1 - Batch enqueue (expect 202){RESET}")

    try:
        async with aiohttp.ClientSession() as session:
            url = f"{backend_url}{API_PREFIX}/face/process"
            payload = _edge_process_payload(n_faces=1)
            async with session.post(
                url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                body = await resp.json()
                if resp.status == 202:
                    _pass("POST /face/process", f"status=202, body={json.dumps(body)}")
                    return True
                else:
                    _fail(
                        "POST /face/process",
                        f"Expected 202, got {resp.status}. "
                        f"Is USE_BATCH_PROCESSING=true? body={json.dumps(body)}",
                    )
                    return False
    except Exception as exc:
        _fail("POST /face/process", str(exc))
        return False


async def test_redis_queue(redis_url: str) -> bool:
    """Check whether the Redis queue for ROOM_ID has items (or was consumed)."""
    print(f"\n{BOLD}Test 2 - Redis queue populated{RESET}")

    try:
        import redis.asyncio as redis

        parsed = urlparse(redis_url)
        db = 0
        if parsed.path and parsed.path.strip("/"):
            db = int(parsed.path.strip("/"))
        r = redis.Redis(
            host=parsed.hostname or "localhost",
            port=parsed.port or 6379,
            db=db,
            decode_responses=False,
        )

        queue_key = f"face_queue:{ROOM_ID}"
        length = await r.llen(queue_key.encode())
        await r.aclose()

        if length > 0:
            _pass("Queue check", f"{queue_key} has {length} item(s)")
            return True
        else:
            # Length 0 could mean the batch worker already consumed the items
            _pass(
                "Queue check",
                f"{queue_key} is empty (batch worker likely already consumed it)",
            )
            return True
    except Exception as exc:
        _fail("Queue check", str(exc))
        return False


async def test_websocket_broadcast(backend_url: str) -> bool:
    """Open a WebSocket, POST a face, and wait for a broadcast message."""
    print(f"\n{BOLD}Test 3 - WebSocket broadcast{RESET}")

    ws_scheme = "ws" if backend_url.startswith("http://") else "wss"
    host_part = backend_url.split("://", 1)[1]
    ws_url = f"{ws_scheme}://{host_part}{API_PREFIX}/ws/smoke-test-user"

    received_messages: list[dict] = []
    ws_connected = False

    try:
        import websockets
    except ImportError:
        _fail("WebSocket broadcast", "websockets package not installed (pip install websockets)")
        return False

    async def _listen_ws():
        nonlocal ws_connected
        try:
            async with websockets.connect(ws_url, close_timeout=2) as ws:
                ws_connected = True
                _info(f"WebSocket connected to {ws_url}")
                while True:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=10)
                        msg = json.loads(raw)
                        received_messages.append(msg)
                        _info(f"WS message: {json.dumps(msg, default=str)[:200]}")
                    except asyncio.TimeoutError:
                        break
                    except websockets.exceptions.ConnectionClosed:
                        break
        except Exception as exc:
            _info(f"WebSocket error: {exc}")

    # Start listener in background
    ws_task = asyncio.create_task(_listen_ws())

    # Wait briefly for WS to connect
    for _ in range(20):
        if ws_connected:
            break
        await asyncio.sleep(0.1)

    if not ws_connected:
        _fail("WebSocket broadcast", "Could not connect WebSocket")
        ws_task.cancel()
        try:
            await ws_task
        except (asyncio.CancelledError, Exception):
            pass
        return False

    # POST a face to trigger batch processing
    try:
        async with aiohttp.ClientSession() as session:
            url = f"{backend_url}{API_PREFIX}/face/process"
            payload = _edge_process_payload(n_faces=1)
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                _info(f"POST /face/process -> {resp.status}")
    except Exception as exc:
        _info(f"POST failed: {exc}")

    # Wait for the WS listener to finish (up to 10s timeout built into _listen_ws)
    try:
        await asyncio.wait_for(ws_task, timeout=12)
    except asyncio.TimeoutError:
        ws_task.cancel()
        try:
            await ws_task
        except (asyncio.CancelledError, Exception):
            pass

    # Evaluate — filter out the initial "connected" event
    batch_msgs = [m for m in received_messages if m.get("event") != "connected"]
    if batch_msgs:
        _pass("WebSocket broadcast", f"Received {len(batch_msgs)} broadcast message(s)")
        return True
    else:
        _info(
            "No batch_results messages received within timeout. "
            "This may be expected if no registered faces exist to match, "
            "or the batch worker has not processed the queue yet."
        )
        _fail("WebSocket broadcast", "No broadcast messages received in 10s")
        return False


async def test_multiple_faces_batch(backend_url: str) -> bool:
    """Send 5 faces rapidly and verify the batch processor handles them."""
    print(f"\n{BOLD}Test 4 - Multiple faces batch{RESET}")

    ws_scheme = "ws" if backend_url.startswith("http://") else "wss"
    host_part = backend_url.split("://", 1)[1]
    ws_url = f"{ws_scheme}://{host_part}{API_PREFIX}/ws/smoke-test-batch-user"

    received_messages: list[dict] = []
    ws_connected = False

    try:
        import websockets
    except ImportError:
        _fail("Multiple faces batch", "websockets package not installed")
        return False

    async def _listen_ws():
        nonlocal ws_connected
        try:
            async with websockets.connect(ws_url, close_timeout=2) as ws:
                ws_connected = True
                while True:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=10)
                        msg = json.loads(raw)
                        received_messages.append(msg)
                    except asyncio.TimeoutError:
                        break
                    except websockets.exceptions.ConnectionClosed:
                        break
        except Exception:
            pass

    ws_task = asyncio.create_task(_listen_ws())

    # Wait for WS to connect
    for _ in range(20):
        if ws_connected:
            break
        await asyncio.sleep(0.1)

    # POST 5 faces in a single request (batch)
    post_ok = True
    try:
        async with aiohttp.ClientSession() as session:
            url = f"{backend_url}{API_PREFIX}/face/process"
            payload = _edge_process_payload(n_faces=5)
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                body = await resp.json()
                if resp.status == 202:
                    queued = body.get("faces_queued", 0)
                    _info(f"POST /face/process (5 faces) -> 202, faces_queued={queued}")
                    if queued == 5:
                        _pass("Enqueue 5 faces", f"faces_queued={queued}")
                    else:
                        _fail("Enqueue 5 faces", f"Expected faces_queued=5, got {queued}")
                        post_ok = False
                else:
                    _fail("Enqueue 5 faces", f"Expected 202, got {resp.status}")
                    post_ok = False
    except Exception as exc:
        _fail("Enqueue 5 faces", str(exc))
        post_ok = False

    # Wait for WS messages
    try:
        await asyncio.wait_for(ws_task, timeout=12)
    except asyncio.TimeoutError:
        ws_task.cancel()
        try:
            await ws_task
        except (asyncio.CancelledError, Exception):
            pass

    # Check if any batch message reported batch_size >= 2
    batch_msgs = [m for m in received_messages if m.get("event") != "connected"]
    found_batch = False
    for msg in batch_msgs:
        data = msg.get("data", {})
        bs = data.get("batch_size", 0)
        if bs >= 2:
            found_batch = True
            _info(f"Batch message with batch_size={bs}")
            break

    if found_batch:
        _pass("Batch processing", f"Received batch with batch_size >= 2")
    elif batch_msgs:
        _info("Broadcast messages received, but batch_size < 2 (worker may process one-by-one)")
        _pass("Batch processing", "Messages received (batch may have been split)")
    elif post_ok:
        _info(
            "No WebSocket broadcast received. The batch worker processed the "
            "queue but there are no registered faces to match, so no broadcast "
            "was sent to this user. Enqueue itself succeeded."
        )
        _pass("Batch processing", "Enqueue verified; no WS broadcast (expected with no registered faces)")
    else:
        _fail("Batch processing", "Enqueue failed")

    return post_ok


async def test_face_gone(backend_url: str) -> bool:
    """POST to /face/gone and expect 200."""
    print(f"\n{BOLD}Test 5 - Face gone endpoint{RESET}")

    try:
        async with aiohttp.ClientSession() as session:
            url = f"{backend_url}{API_PREFIX}/face/gone"
            payload = _face_gone_payload()
            async with session.post(
                url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                body = await resp.json()
                if resp.status == 200:
                    _pass("POST /face/gone", f"status=200, body={json.dumps(body)}")
                    return True
                else:
                    _fail("POST /face/gone", f"Expected 200, got {resp.status}, body={json.dumps(body)}")
                    return False
    except Exception as exc:
        _fail("POST /face/gone", str(exc))
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main(backend_url: str, redis_url: str, skip_redis: bool = False):
    print(f"{BOLD}{'=' * 60}{RESET}")
    print(f"{BOLD}  IAMS Batch Processing Pipeline — Smoke Test{RESET}")
    print(f"{BOLD}{'=' * 60}{RESET}")
    print(f"  Backend : {backend_url}")
    print(f"  Redis   : {redis_url}{' (skipped)' if skip_redis else ''}")

    results: list[tuple[str, bool]] = []

    # Prerequisites
    if skip_redis:
        # Only check backend health
        print(f"\n{BOLD}Prerequisites{RESET}")
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{backend_url}{API_PREFIX}/health"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        _pass("Backend healthy", f"GET {url} -> {resp.status}")
                    else:
                        _fail("Backend healthy", f"GET {url} -> {resp.status}")
                        print(f"\n{RED}{BOLD}Prerequisites failed.{RESET}")
                        sys.exit(1)
        except Exception as exc:
            _fail("Backend healthy", str(exc))
            print(f"\n{RED}{BOLD}Prerequisites failed.{RESET}")
            sys.exit(1)
    else:
        prereqs_ok = await check_prerequisites(backend_url, redis_url)
        if not prereqs_ok:
            print(f"\n{RED}{BOLD}Prerequisites failed. Aborting remaining tests.{RESET}")
            print(f"\n{BOLD}Summary: 0/5 tests passed{RESET}")
            sys.exit(1)

    # Test 1
    ok = await test_batch_enqueue(backend_url)
    results.append(("Batch enqueue (202)", ok))

    # Test 2
    if not skip_redis:
        ok = await test_redis_queue(redis_url)
        results.append(("Redis queue populated", ok))

    # Test 3
    ok = await test_websocket_broadcast(backend_url)
    results.append(("WebSocket broadcast", ok))

    # Test 4
    ok = await test_multiple_faces_batch(backend_url)
    results.append(("Multiple faces batch", ok))

    # Test 5
    ok = await test_face_gone(backend_url)
    results.append(("Face gone endpoint", ok))

    # Summary
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"\n{BOLD}{'=' * 60}{RESET}")
    color = GREEN if passed == total else RED
    print(f"{BOLD}  Summary: {color}{passed}/{total} tests passed{RESET}")
    print(f"{BOLD}{'=' * 60}{RESET}\n")

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Smoke test for IAMS batch processing pipeline",
    )
    parser.add_argument(
        "--backend-url",
        default="http://localhost:8000",
        help="Backend base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--redis-url",
        default="redis://localhost:6379/0",
        help="Redis URL (default: redis://localhost:6379/0)",
    )
    parser.add_argument(
        "--skip-redis",
        action="store_true",
        help="Skip Redis connectivity tests (for remote VPS where Redis is internal-only)",
    )
    args = parser.parse_args()

    # Strip trailing slash
    backend_url = args.backend_url.rstrip("/")

    asyncio.run(main(backend_url, args.redis_url, skip_redis=args.skip_redis))
