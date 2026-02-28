# Edge Device Integration Guide

**Version:** 1.0
**Last Updated:** 2026-02-07
**Target Audience:** Edge device developers (Raspberry Pi)

---

## Table of Contents

1. [Overview](#overview)
2. [API Endpoint](#api-endpoint)
3. [Request Format](#request-format)
4. [Response Format](#response-format)
5. [Error Handling](#error-handling)
6. [Retry Logic](#retry-logic)
7. [Idempotency](#idempotency)
8. [Best Practices](#best-practices)
9. [Code Examples](#code-examples)
10. [Testing](#testing)
11. [Troubleshooting](#troubleshooting)

---

## Overview

The Edge API (`POST /api/v1/face/process`) is the primary interface for Raspberry Pi edge devices to send detected faces to the backend for recognition and presence tracking.

**Key Features:**
- Batch face processing (1-10 faces per request)
- Idempotent requests (safe retries)
- Detailed error codes for retry decisions
- Performance metrics in response
- No authentication required (trusted network)

**Flow:**
```
RPi Camera → MediaPipe (detect) → Crop faces → Base64 encode → POST to backend → Response
```

---

## API Endpoint

**URL:** `POST http://<backend-url>/api/v1/face/process`

**Content-Type:** `application/json`

**Authentication:** None (MVP - trusted network)

**Rate Limits:**
- Recommended interval: 60 seconds between scans (during class)
- Burst allowance: 20 requests (for queue draining)
- Max batch size: 10 faces per request

---

## Request Format

### Schema

```json
{
  "request_id": "optional-idempotency-key",
  "room_id": "room-identifier",
  "timestamp": "2024-01-15T10:30:00Z",
  "faces": [
    {
      "image": "base64_encoded_jpeg",
      "bbox": [100, 150, 112, 112]
    }
  ]
}
```

### Field Specifications

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `request_id` | string | No | Max 100 chars | Idempotency key for retries |
| `room_id` | string | Yes | Max 100 chars, alphanumeric + hyphens | Room identifier |
| `timestamp` | string | Yes | ISO 8601 format | When faces were detected |
| `faces` | array | Yes | 1-10 items | Array of detected faces |
| `faces[].image` | string | Yes | Base64 JPEG, max 10MB encoded | Face image data |
| `faces[].bbox` | array | No | [x, y, w, h], non-negative integers | Bounding box coordinates |

### Image Requirements

**Format:**
- JPEG or PNG
- Base64 encoded
- Max size: 10MB (encoded)

**Dimensions:**
- Minimum: 10x10 pixels
- Maximum: 4096x4096 pixels
- Recommended: 112x112 pixels (MediaPipe face crop size)

**Quality:**
- JPEG quality: 70-85%
- Clear face visible
- Good lighting

### Bounding Box (Optional)

Format: `[x, y, width, height]`

- `x`, `y`: Top-left corner coordinates (non-negative)
- `width`, `height`: Face dimensions (positive)
- Coordinates relative to original frame

**Note:** bbox is optional for backward compatibility. MediaPipe may not always provide it.

---

## Response Format

### Success Response

```json
{
  "success": true,
  "data": {
    "processed": 3,
    "matched": [
      {
        "user_id": "uuid-1",
        "confidence": 0.85
      },
      {
        "user_id": "uuid-2",
        "confidence": 0.92
      }
    ],
    "unmatched": 1,
    "processing_time_ms": 450,
    "presence_logged": 2
  }
}
```

### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Always `true` for successfully processed requests |
| `data.processed` | integer | Number of faces successfully processed |
| `data.matched` | array | Faces that matched registered users |
| `data.matched[].user_id` | string | UUID of matched user |
| `data.matched[].confidence` | float | Match confidence (0.0-1.0) |
| `data.unmatched` | integer | Faces that didn't match any user |
| `data.processing_time_ms` | integer | Total processing time in milliseconds |
| `data.presence_logged` | integer | Number of presence logs created |

### Error Response

```json
{
  "success": false,
  "error": {
    "code": "INVALID_IMAGE_FORMAT",
    "message": "Face 1: Unsupported image format: BMP (expected JPEG or PNG)",
    "retry": false
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Always `false` for errors |
| `error.code` | string | Error code (see Error Codes section) |
| `error.message` | string | Human-readable error message |
| `error.retry` | boolean | Whether retry makes sense |

---

## Error Handling

### HTTP Status Codes

| Code | Meaning | Action |
|------|---------|--------|
| 200 | Success | Process response |
| 422 | Validation Error | Fix request format, don't retry |
| 500 | Server Error | Retry with backoff |
| 503 | Service Unavailable | Retry with longer backoff |

### Error Codes

| Code | HTTP | Retry? | Description |
|------|------|--------|-------------|
| `INVALID_IMAGE_FORMAT` | 200 | No | Image format not supported (BMP, TIFF, etc.) |
| `IMAGE_TOO_LARGE` | 200 | No | Image exceeds 10MB limit |
| `IMAGE_TOO_SMALL` | 200 | No | Image smaller than 10x10 pixels |
| `INVALID_BASE64` | 200 | No | Base64 decoding failed |
| `RECOGNITION_FAILED` | 200 | Yes | Face recognition service error |
| `DATABASE_UNAVAILABLE` | 200 | Yes | Database connection lost |
| `FAISS_INDEX_UNAVAILABLE` | 200 | Yes | FAISS index not loaded |
| `ValidationError` | 422 | No | Request schema validation failed |
| `InternalServerError` | 500 | Yes | Unexpected server error |

### Partial Failures

The API processes faces individually. If some faces fail, the response still returns `success: true` with details:

```json
{
  "success": true,
  "data": {
    "processed": 2,
    "matched": [{"user_id": "uuid-1", "confidence": 0.85}],
    "unmatched": 2  // Includes 1 invalid + 1 unmatched
  }
}
```

Check logs for detailed error messages about which faces failed.

---

## Retry Logic

### RPi Queue Policy

When the backend is unreachable or returns an error:

1. **Queue Locally:** Add request to in-memory queue (max 500 items)
2. **TTL:** Discard items older than 5 minutes
3. **Retry Interval:** Retry every 10 seconds
4. **Max Attempts:** 3 attempts per request
5. **After Max Attempts:** Re-queue and try again later

### Retry Decision Tree

```
Response Status
├─ 200 OK
│  ├─ success: true → Done (don't retry)
│  └─ success: false
│     ├─ error.retry: true → Retry with backoff
│     └─ error.retry: false → Drop (permanent failure)
├─ 422 Validation Error → Drop (fix code, don't retry)
├─ 500 Server Error → Retry with exponential backoff
└─ 503 Service Unavailable → Retry with longer backoff
```

### Backoff Strategy

**Exponential Backoff:**
- 1st retry: 10 seconds
- 2nd retry: 20 seconds
- 3rd retry: 40 seconds
- After 3 attempts: re-queue with 5-minute delay

**Jitter:** Add random jitter (0-2 seconds) to prevent thundering herd.

---

## Idempotency

### Why It Matters

Network timeouts can cause duplicate requests:

1. RPi sends request at 10:30:00
2. Backend processes, writes to DB, but response times out
3. RPi retries same request at 10:30:10
4. Without idempotency: **Duplicate presence log created**

### How to Use

**Include `request_id` in every request:**

```python
import uuid
from datetime import datetime

request_id = str(uuid.uuid4())  # Generate unique ID per scan

payload = {
    "request_id": request_id,
    "room_id": "room-101",
    "timestamp": datetime.utcnow().isoformat() + "Z",
    "faces": faces_data
}
```

**Retry Logic:**

```python
def send_with_retry(payload, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data["success"]:
                    return data
                elif not data["error"]["retry"]:
                    # Permanent error, don't retry
                    logger.error(f"Permanent error: {data['error']}")
                    return None
            # Retry
            time.sleep(10 * (2 ** attempt))  # Exponential backoff
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout on attempt {attempt + 1}")
            time.sleep(10 * (2 ** attempt))

    logger.error("Max retries exceeded")
    return None
```

**Deduplication Window:** 5 minutes

- Same `request_id` + `room_id` + `timestamp` within 5 minutes → Ignored
- After 5 minutes: Cache entry expires, request processed normally

---

## Best Practices

### 1. Image Optimization

**Resize before encoding:**
```python
from PIL import Image

# Resize to 112x112 (MediaPipe default crop size)
face_img = Image.fromarray(face_crop)
face_img = face_img.resize((112, 112), Image.BILINEAR)

# Compress JPEG
img_bytes = io.BytesIO()
face_img.save(img_bytes, format='JPEG', quality=80)
image_base64 = base64.b64encode(img_bytes.getvalue()).decode('utf-8')
```

**Benefits:**
- Faster upload (smaller payload)
- Faster backend processing
- Lower network costs

### 2. Batch Processing

**Send multiple faces per request:**
```python
# Good: Batch 5 faces
payload = {
    "room_id": "room-101",
    "timestamp": timestamp,
    "faces": [face1, face2, face3, face4, face5]
}

# Bad: Send individually
for face in faces:
    payload = {"room_id": "room-101", "timestamp": timestamp, "faces": [face]}
    send_request(payload)  # 5 HTTP requests instead of 1
```

**Batch Size Guidelines:**
- Minimum: 1 face (no empty batches)
- Maximum: 10 faces (API limit)
- Optimal: 3-5 faces (balance between latency and throughput)

### 3. Timestamp Handling

**Use UTC timestamps:**
```python
from datetime import datetime, timezone

# Good: UTC
timestamp = datetime.now(timezone.utc).isoformat()

# Bad: Local time (ambiguous)
timestamp = datetime.now().isoformat()
```

**Format:** ISO 8601 with timezone
- Correct: `2024-01-15T10:30:00+00:00` or `2024-01-15T10:30:00Z`
- Incorrect: `2024-01-15 10:30:00`

### 4. Error Logging

**Log all errors with context:**
```python
try:
    response = send_request(payload)
except Exception as e:
    logger.error(
        f"Edge API error: {e}",
        extra={
            "room_id": payload["room_id"],
            "timestamp": payload["timestamp"],
            "face_count": len(payload["faces"]),
            "request_id": payload.get("request_id")
        }
    )
```

### 5. Queue Management

**Monitor queue depth:**
```python
from collections import deque

request_queue = deque(maxlen=500)

def monitor_queue():
    depth = len(request_queue)
    if depth > 400:
        logger.warning(f"Queue nearly full: {depth}/500")
    if depth == 500:
        logger.error("Queue full! Dropping oldest requests.")
```

**Prioritize recent requests:**
- FIFO queue: Oldest requests sent first
- TTL: Drop requests older than 5 minutes

### 6. Network Resilience

**Handle network errors gracefully:**
```python
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

def create_session():
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session
```

---

## Code Examples

### Python Example (Complete)

```python
import base64
import io
import uuid
import time
import logging
from datetime import datetime, timezone
from PIL import Image
import requests

logger = logging.getLogger(__name__)

BACKEND_URL = "http://localhost:8000/api/v1/face/process"
ROOM_ID = "room-101"

def encode_face_image(face_crop):
    """
    Encode face crop to Base64 JPEG

    Args:
        face_crop: numpy array (H, W, 3)

    Returns:
        Base64 encoded string
    """
    # Convert to PIL Image
    img = Image.fromarray(face_crop)

    # Resize to 112x112 (optimal size)
    img = img.resize((112, 112), Image.BILINEAR)

    # Compress to JPEG
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='JPEG', quality=80)

    # Encode to Base64
    return base64.b64encode(img_bytes.getvalue()).decode('utf-8')


def send_faces_to_backend(face_crops, bboxes=None):
    """
    Send detected faces to backend for recognition

    Args:
        face_crops: List of face images (numpy arrays)
        bboxes: Optional list of bounding boxes

    Returns:
        Response data or None on error
    """
    # Generate unique request ID for idempotency
    request_id = str(uuid.uuid4())

    # Current timestamp (UTC)
    timestamp = datetime.now(timezone.utc).isoformat()

    # Prepare faces data
    faces_data = []
    for i, face_crop in enumerate(face_crops):
        face_entry = {
            "image": encode_face_image(face_crop)
        }

        # Add bbox if available
        if bboxes and i < len(bboxes):
            x, y, w, h = bboxes[i]
            face_entry["bbox"] = [int(x), int(y), int(w), int(h)]

        faces_data.append(face_entry)

    # Prepare request
    payload = {
        "request_id": request_id,
        "room_id": ROOM_ID,
        "timestamp": timestamp,
        "faces": faces_data
    }

    # Send with retry logic
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(
                BACKEND_URL,
                json=payload,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()

                if data["success"]:
                    logger.info(
                        f"Faces processed: {data['data']['processed']}, "
                        f"Matched: {len(data['data']['matched'])}, "
                        f"Time: {data['data']['processing_time_ms']}ms"
                    )
                    return data["data"]
                else:
                    # Error returned in response
                    error = data["error"]
                    logger.error(f"Backend error: {error['code']} - {error['message']}")

                    if not error.get("retry", False):
                        # Permanent error, don't retry
                        return None

            elif response.status_code == 422:
                # Validation error, don't retry
                logger.error(f"Validation error: {response.json()}")
                return None

            # Retry with exponential backoff
            if attempt < max_retries - 1:
                backoff = 10 * (2 ** attempt)
                logger.warning(f"Attempt {attempt + 1} failed, retrying in {backoff}s")
                time.sleep(backoff)

        except requests.exceptions.Timeout:
            logger.warning(f"Request timeout on attempt {attempt + 1}")
            if attempt < max_retries - 1:
                time.sleep(10 * (2 ** attempt))

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error: {e}")
            if attempt < max_retries - 1:
                time.sleep(10 * (2 ** attempt))

    logger.error(f"Max retries exceeded for request {request_id}")
    return None


# Usage example
if __name__ == "__main__":
    # Simulate detected faces from MediaPipe
    import numpy as np

    # Create dummy face crops (replace with actual MediaPipe output)
    face1 = np.random.randint(0, 255, (112, 112, 3), dtype=np.uint8)
    face2 = np.random.randint(0, 255, (112, 112, 3), dtype=np.uint8)

    face_crops = [face1, face2]
    bboxes = [[100, 150, 112, 112], [300, 200, 112, 112]]

    # Send to backend
    result = send_faces_to_backend(face_crops, bboxes)

    if result:
        print(f"Success! Matched {len(result['matched'])} faces")
    else:
        print("Failed to process faces")
```

---

## Testing

### Unit Tests (Edge Device)

```python
import unittest
from unittest.mock import Mock, patch

class TestEdgeAPI(unittest.TestCase):

    @patch('requests.post')
    def test_successful_request(self, mock_post):
        """Test successful API call"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "data": {
                "processed": 2,
                "matched": [{"user_id": "uuid-1", "confidence": 0.85}],
                "unmatched": 1
            }
        }
        mock_post.return_value = mock_response

        # Your send function
        result = send_faces_to_backend([face1, face2])

        self.assertIsNotNone(result)
        self.assertEqual(result["processed"], 2)

    @patch('requests.post')
    def test_retry_on_timeout(self, mock_post):
        """Test retry logic on timeout"""
        mock_post.side_effect = [
            requests.exceptions.Timeout(),
            Mock(status_code=200, json=lambda: {"success": True, "data": {...}})
        ]

        result = send_faces_to_backend([face1])

        self.assertIsNotNone(result)
        self.assertEqual(mock_post.call_count, 2)
```

### Integration Tests

Use the provided test images in `/docs/test-images/`:
- `valid_face.jpg` - Valid face image (should recognize)
- `invalid_format.bmp` - Invalid format (should reject)
- `oversized.jpg` - >10MB (should reject)

```bash
# Test with cURL
curl -X POST http://localhost:8000/api/v1/face/process \
  -H "Content-Type: application/json" \
  -d @test_request.json
```

---

## Troubleshooting

### Common Issues

#### 1. "Invalid Base64 encoding"

**Cause:** Base64 string malformed or truncated

**Solution:**
```python
# Ensure proper encoding
image_base64 = base64.b64encode(image_bytes).decode('utf-8')

# Verify it's valid
try:
    base64.b64decode(image_base64, validate=True)
except Exception as e:
    print(f"Invalid Base64: {e}")
```

#### 2. "Image too large" (>10MB)

**Cause:** Image not resized/compressed before encoding

**Solution:**
```python
# Resize and compress
img = img.resize((112, 112), Image.BILINEAR)
img.save(buffer, format='JPEG', quality=70)  # Lower quality
```

#### 3. "Validation error: faces min_length 1"

**Cause:** Empty faces array sent

**Solution:**
```python
# Only send if faces detected
if len(faces) > 0:
    send_faces_to_backend(faces)
```

#### 4. "Validation error: faces max_length 10"

**Cause:** Too many faces in one request

**Solution:**
```python
# Split into batches of 10
for i in range(0, len(faces), 10):
    batch = faces[i:i+10]
    send_faces_to_backend(batch)
```

#### 5. Processing time > 5 seconds

**Cause:** Large images or CPU overload

**Solution:**
- Resize images to 112x112
- Reduce JPEG quality
- Check backend CPU usage
- Consider GPU acceleration

#### 6. "No active schedule found"

**Cause:** Request sent outside class hours or wrong room_id

**Solution:**
```python
# Verify room_id matches database
# Check timestamp is during class hours (e.g., 8:00-17:00)
# Presence won't be logged outside class, but recognition still works
```

### Debug Checklist

- [ ] Base64 encoding is valid
- [ ] Image size < 10MB (encoded)
- [ ] Image format is JPEG or PNG
- [ ] Faces array has 1-10 items
- [ ] room_id is alphanumeric + hyphens only
- [ ] Timestamp is ISO 8601 format
- [ ] bbox values are non-negative (if provided)
- [ ] Network connectivity to backend
- [ ] Backend service is running
- [ ] Check backend logs for detailed errors

### Logs to Check

**Edge Device:**
```
[INFO] Sending 3 faces to backend (request_id=abc-123)
[ERROR] Edge API error: Connection timeout
[WARNING] Retry attempt 1/3 in 10s
```

**Backend:**
```
[INFO] Processing 3 faces from room room-101 at 2024-01-15T10:30:00Z
[WARNING] Face 2: Invalid Base64 encoding
[INFO] Edge API results - Processed: 2, Matched: 1, Unmatched: 2, Time: 450ms
```

---

## Appendix

### API Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-02-07 | Initial release with idempotency and validation |

### Related Documentation

- [API Reference](api-reference.md) - Full API documentation
- [Edge API Validation Report](edge-api-validation-report.md) - Technical analysis
- [Architecture](architecture.md) - System design

### Support

**Issues:** Report to backend team via GitHub Issues
**Questions:** Contact technical lead

---

**Document Version:** 1.0
**Last Updated:** 2026-02-07
