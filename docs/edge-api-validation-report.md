# Edge Device API Integration Validation Report

**Date:** 2026-02-07
**Endpoint:** `POST /api/v1/face/process`
**Version:** v1
**Status:** ⚠️ NEEDS ENHANCEMENTS

---

## Executive Summary

The Edge API endpoint (`POST /face/process`) is **functional but requires critical enhancements** for production deployment. The current implementation handles basic face recognition but lacks:

1. **Robust error handling** for edge device retry logic
2. **Image validation** (size limits, format validation)
3. **Rate limiting** for multi-device deployments
4. **Performance metrics** for monitoring
5. **Comprehensive test coverage**
6. **Request idempotency** for safe retries

**Recommendation:** Implement enhancements before RPi deployment to prevent edge device queue overflows and ensure reliable continuous presence tracking.

---

## Current API Contract Analysis

### Request Schema (EdgeProcessRequest)

```json
{
  "room_id": "uuid-or-identifier",
  "timestamp": "2024-01-15T10:30:00Z",
  "faces": [
    {
      "image": "base64_encoded_jpeg",
      "bbox": [100, 150, 112, 112]
    }
  ]
}
```

**✅ STRENGTHS:**
- Schema is well-documented in code
- Supports batch face processing (multiple faces per request)
- Includes timestamp for temporal tracking
- BBox data available for future DeepSORT integration

**❌ WEAKNESSES:**
- No max size constraint on `image` field (DoS risk)
- No validation of Base64 format before processing
- `bbox` is required but not validated for reasonable values
- No `request_id` for idempotency/deduplication
- No `session_id` field (mentioned in CLAUDE.md but not in schema)

### Response Schema (EdgeProcessResponse)

```json
{
  "success": true,
  "data": {
    "processed": 3,
    "matched": [
      {"user_id": "uuid", "confidence": 0.85}
    ],
    "unmatched": 1
  }
}
```

**✅ STRENGTHS:**
- Clear success indicator
- Separates matched vs unmatched faces
- Returns confidence scores for matched faces

**❌ WEAKNESSES:**
- No error codes for retry decisions (e.g., `FAISS_INDEX_UNAVAILABLE` vs `INVALID_IMAGE`)
- No `processing_time_ms` metric
- No `retry_after` header for rate limiting
- No partial failure reporting (which specific faces failed?)
- Missing `faces_detected` count (different from `processed`)

---

## Error Handling Analysis

### Current Error Handling

**Code Review (face.py:256-289):**
```python
for i, face_data in enumerate(request.faces):
    try:
        # Decode Base64 image
        image = face_service.facenet.decode_base64_image(face_data.image)
        # ... processing ...
    except Exception as e:
        logger.error(f"Failed to process face {i+1}: {e}")
        processed_count += 1
        unmatched_count += 1
```

**✅ STRENGTHS:**
- Catches exceptions per-face (batch processing resilience)
- Logs errors for debugging
- Continues processing remaining faces after failure

**❌ WEAKNESSES:**
- Generic `Exception` catch - no error type differentiation
- No error codes returned to edge device
- Edge device can't distinguish:
  - Corrupted image (permanent failure - don't retry)
  - FAISS index loading (transient - retry makes sense)
  - Database timeout (transient - retry with backoff)
- No HTTP status code differentiation (always 200 OK)
- No validation of Base64 before expensive decode operation

### Base64 Decoding (face_recognition.py:178-206)

```python
def decode_base64_image(self, base64_string: str) -> Image.Image:
    try:
        if ',' in base64_string:
            base64_string = base64_string.split(',')[1]
        image_bytes = base64.b64decode(base64_string)
        image = Image.open(io.BytesIO(image_bytes))
        return image
    except Exception as e:
        logger.error(f"Failed to decode Base64 image: {e}")
        raise ValueError(f"Invalid Base64 image: {e}")
```

**❌ CRITICAL ISSUES:**
- No size limit check on `base64_string` before decode
- A 50MB Base64 string would be decoded into memory before validation
- No image format validation (could be PNG, BMP, etc. instead of JPEG)
- No dimension validation (could be 10x10 or 10000x10000)

---

## Rate Limiting Analysis

**Current Implementation:** ❌ NONE

**Requirements:**
- RPi queue policy: Retry every 10 seconds on failure
- Scan interval: 60 seconds during class (normal operation)
- Multi-device scenario: 10+ edge devices per deployment

**Risk:** Without rate limiting:
- A malfunctioning edge device retrying every 10s could overload backend
- 10 devices × 6 req/min = 60 req/min baseline
- During retry storms: 10 devices × 10 sec interval = 6 req/sec (acceptable)
- But if queue drains: 500 faces × 10 devices = 5000 requests in burst

**Recommendation:** Implement per-device rate limiting:
- 10 requests per minute per `room_id` (normal operation)
- Burst allowance: 20 requests (for queue draining)
- Return `429 Too Many Requests` with `Retry-After` header

---

## Idempotency Analysis

**Current Implementation:** ❌ NONE

**RPi Retry Scenario:**
1. RPi sends face at 10:30:00
2. Backend processes, writes to DB, but response times out
3. RPi retries same face at 10:30:10
4. Backend processes again → **DUPLICATE presence_log entry**

**Impact:**
- Inflated presence scores (student detected twice for same scan)
- Skewed attendance analytics
- Early-leave detection false negatives (consecutive miss counter reset)

**Recommendation:** Add `request_id` field to schema:
```python
class EdgeProcessRequest(BaseModel):
    request_id: Optional[str] = Field(None, description="Idempotency key for retries")
    room_id: str
    timestamp: datetime
    faces: List[FaceData]
```

Backend should deduplicate based on `(request_id, room_id, timestamp)` within 5-minute window.

---

## Performance Analysis

### Current Metrics: ❌ INSUFFICIENT

**What's Logged:**
```python
logger.info(f"Processing {len(request.faces)} faces from room {request.room_id}")
logger.info(f"Edge API results - Processed: {processed_count}, Matched: {len(matched_users)}")
```

**What's Missing:**
- Base64 decode time
- Face recognition time (per face)
- FAISS search time
- Database operation time
- Total request processing time
- Queue depth (if queuing implemented)

**Recommendation:** Add structured metrics:
```python
{
  "processing_time_ms": 450,
  "breakdown": {
    "decode_ms": 50,
    "recognition_ms": 350,
    "db_ms": 50
  },
  "faces_detected": 3,
  "faces_recognized": 2
}
```

---

## Authentication Analysis

**Current Implementation:**
```python
async def process_faces(
    request: EdgeProcessRequest,
    db: Session = Depends(get_db)
):
```

**Status:** ❌ NO AUTHENTICATION

**Documentation (face.py:239-242):**
> No authentication required (trusted network)
> In production: Use API key or service account token

**Risk:**
- Any device on network can POST to `/face/process`
- Potential for spam/DoS attacks
- No audit trail of which device sent which request
- Can't disable specific malfunctioning devices

**Recommendation:** Implement API key auth:
```python
async def process_faces(
    request: EdgeProcessRequest,
    api_key: str = Depends(verify_edge_api_key),
    db: Session = Depends(get_db)
):
```

Store per-device API keys in database with metadata:
- Device ID
- Room assignment
- Last seen timestamp
- Request count (for rate limiting)

---

## Integration Testing Analysis

**Current Coverage:** ❌ NONE

**Search Results:**
```
No files found matching **/test_face*.py
```

**Missing Test Scenarios:**

### Happy Path
- [ ] Single face recognition
- [ ] Batch face recognition (3-5 faces)
- [ ] No faces detected (empty array)
- [ ] All faces unmatched

### Error Cases
- [ ] Invalid Base64 format
- [ ] Corrupted JPEG data
- [ ] Oversized image (>10MB)
- [ ] Empty image string
- [ ] Missing required fields
- [ ] Invalid room_id format
- [ ] Future timestamp
- [ ] Invalid bbox values

### Edge Device Scenarios
- [ ] Retry with same request_id (idempotency)
- [ ] Concurrent requests from multiple devices
- [ ] Offline queue drain (burst of requests)
- [ ] Malformed Base64 with valid structure

### Performance Tests
- [ ] 10 concurrent devices
- [ ] 10 faces per request (max batch)
- [ ] Response time < 500ms (target)
- [ ] Memory usage under load

---

## Backward Compatibility Analysis

**Schema Version:** v1 (implicit)
**Deployment Model:** Raspberry Pi devices in classrooms (physical access required for updates)

**Breaking Change Risk:** 🔴 HIGH

**Current Schema Changes Needed:**
1. Add `request_id` field (Optional - backward compatible ✅)
2. Add `session_id` field (Optional - backward compatible ✅)
3. Change `bbox` from required to optional (Breaking ❌)
4. Add image size validation (Behavior change - could reject previously accepted requests ❌)

**Recommendation:**
- Make all new fields optional with defaults
- Add image size validation gradually:
  - Week 1: Log oversized images but process
  - Week 2: Return warnings in response
  - Week 3: Reject oversized images (after verifying RPi code compliance)
- Version the API explicitly: `/api/v1/face/process` (already done ✅)

---

## Data Model Validation

### FaceData Schema

```python
class FaceData(BaseModel):
    image: str = Field(..., description="Base64-encoded JPEG image")
    bbox: List[int] = Field(..., min_items=4, max_items=4, description="Bounding box [x, y, w, h]")
```

**Issues:**
1. `bbox` is required but may not always be available from MediaPipe
2. No validation on bbox values (could be negative, zero, or exceeding frame dimensions)
3. No image format constraint (accepts any Base64 string)

**Recommended Schema:**

```python
class FaceData(BaseModel):
    image: str = Field(
        ...,
        description="Base64-encoded JPEG image",
        max_length=15_000_000  # ~10MB Base64 encoded
    )
    bbox: Optional[List[int]] = Field(
        None,
        min_items=4,
        max_items=4,
        description="Bounding box [x, y, w, h]. Optional for MediaPipe compatibility."
    )

    @validator('bbox')
    def validate_bbox(cls, v):
        if v is not None:
            if any(val < 0 for val in v):
                raise ValueError("bbox values must be non-negative")
            if v[2] <= 0 or v[3] <= 0:  # width and height
                raise ValueError("bbox width and height must be positive")
        return v
```

---

## Database Integration Review

**Presence Logging (face.py:291-330):**

```python
if matched_users:
    try:
        current_schedule = schedule_repo.get_current_schedule(request.room_id, scan_day, scan_time)
        if current_schedule:
            for matched_user in matched_users:
                await presence_service.log_detection(
                    schedule_id=schedule_id,
                    user_id=matched_user.user_id,
                    confidence=matched_user.confidence
                )
```

**✅ STRENGTHS:**
- Validates schedule exists before logging
- Logs each matched user individually
- Graceful degradation (face recognition succeeds even if presence logging fails)

**❌ WEAKNESSES:**
- No transaction management (partial failures possible)
- No duplicate detection (same user detected multiple times in one scan)
- Error logging only - edge device not notified of presence logging failures
- Potential N+1 query problem (one query per matched user)

**Recommendation:**
- Batch insert presence logs (single query)
- Add unique constraint: `UNIQUE(schedule_id, user_id, scan_time, scan_number)`
- Return presence logging status in response:
  ```json
  {
    "success": true,
    "data": {
      "processed": 3,
      "matched": [...],
      "unmatched": 1,
      "presence_logged": 2,
      "presence_failed": 0
    }
  }
  ```

---

## WebSocket Notification Analysis

**Current Implementation (face.py:294):**
```python
presence_service = PresenceService(db)  # No WebSocket manager for Edge API
```

**Status:** ❌ DISABLED FOR EDGE API

**Impact:**
- Faculty app won't receive real-time updates during class
- Students won't see live attendance confirmation
- Mobile apps must poll `/attendance/live/{schedule_id}` endpoint

**Recommendation:** Add WebSocket notification support:
```python
from app.services.websocket_service import websocket_manager

if matched_users and current_schedule:
    # Log presence
    await presence_service.log_detection(...)

    # Notify connected clients
    await websocket_manager.broadcast_to_schedule(
        schedule_id=schedule_id,
        message={
            "type": "presence_detected",
            "data": {
                "users": [u.user_id for u in matched_users],
                "timestamp": request.timestamp.isoformat()
            }
        }
    )
```

---

## Security Analysis

### Input Validation

**Current:** Minimal (Pydantic schema validation only)

**Vulnerabilities:**

1. **DoS via Large Payloads:**
   - No limit on `faces` array size
   - Could send 1000 faces in one request
   - Each face decoded and processed → memory exhaustion

2. **Resource Exhaustion:**
   - No timeout on face recognition
   - Malformed images could cause FaceNet to hang
   - No max processing time per request

3. **Database Injection:**
   - `room_id` not validated before DB query
   - SQL injection risk if room_id used in raw query (mitigated by SQLAlchemy ORM ✅)

**Recommendations:**

```python
class EdgeProcessRequest(BaseModel):
    room_id: str = Field(..., max_length=100, pattern=r'^[a-zA-Z0-9\-]+$')
    timestamp: datetime
    faces: List[FaceData] = Field(..., min_items=1, max_items=10)  # Limit batch size
```

Add request timeout:
```python
@router.post("/process", response_model=EdgeProcessResponse)
async def process_faces(
    request: EdgeProcessRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    # Timeout after 10 seconds
    async with timeout(10):
        # ... processing ...
```

### Data Privacy

**Current:** No PII in response ✅

**Observation:** Response only includes `user_id` and `confidence`, not names or student IDs. Good practice for edge device API.

---

## Performance Benchmarks

### Current Performance (Estimated)

**Assumptions:**
- CPU inference (no GPU on production server yet)
- FAISS IndexFlatIP (exact search)
- PostgreSQL on Supabase (network latency)

**Per-Face Processing:**
- Base64 decode: ~10ms
- FaceNet embedding generation: ~200ms (CPU) / ~50ms (GPU)
- FAISS search: ~5ms (for 100 users)
- Database write: ~20ms (network + query)
- **Total: ~235ms per face**

**Batch Processing (5 faces):**
- Sequential: 5 × 235ms = 1175ms ❌ (exceeds 500ms target)
- Parallel (if implemented): ~250ms ✅

**Recommendation:** Implement parallel face processing:
```python
import asyncio

# Process faces in parallel
tasks = [
    face_service.recognize_face(img_bytes)
    for img_bytes in face_images
]
results = await asyncio.gather(*tasks, return_exceptions=True)
```

### Database Optimization

**Current:** N+1 query pattern
```python
for matched_user in matched_users:
    await presence_service.log_detection(...)  # One INSERT per user
```

**Optimized:** Bulk insert
```python
await presence_service.log_detections_batch(
    schedule_id=schedule_id,
    detections=[
        {"user_id": u.user_id, "confidence": u.confidence}
        for u in matched_users
    ]
)
```

Expected improvement: 50ms total vs 20ms × N

---

## RPi Queue Policy Compliance

**RPi Requirements (from CLAUDE.md):**
- Max 500 items in queue
- 5-minute TTL for queued items
- Retry every 10 seconds on failure
- Max 3 retry attempts per batch

**Backend Requirements:**

1. **Fast Response Times:**
   - Target: <500ms per request
   - Current: ~1200ms for 5 faces (needs optimization)

2. **Clear Error Signals:**
   - 5xx errors → Retry (transient failure)
   - 4xx errors → Drop (permanent failure)
   - Current: Returns 200 OK even on errors ❌

3. **Idempotency:**
   - RPi may retry same request within 5-minute window
   - Current: No deduplication ❌

4. **Rate Limit Guidance:**
   - Should return `Retry-After` header if rate limited
   - Current: No rate limiting ❌

**Compliance Score:** 25% (1/4 requirements met)

---

## Recommendations Summary

### Priority 1: Critical (Pre-Deployment)

1. **Add Image Size Validation**
   - Max 10MB Base64 encoded (~7.5MB decoded)
   - Validate before decode to prevent memory attacks

2. **Implement Error Codes**
   - Return structured error codes for retry logic
   - Map exceptions to error codes:
     - `INVALID_IMAGE_FORMAT` → 400 (don't retry)
     - `RECOGNITION_FAILED` → 500 (retry)
     - `DATABASE_UNAVAILABLE` → 503 (retry with backoff)

3. **Add Request Idempotency**
   - Add optional `request_id` field
   - Deduplicate within 5-minute window
   - Prevent duplicate presence logs

4. **Optimize Batch Processing**
   - Process faces in parallel (asyncio.gather)
   - Target <500ms for 5 faces

### Priority 2: High (Week 1)

5. **Add Integration Tests**
   - Test all error scenarios
   - Test retry behavior
   - Test concurrent requests

6. **Implement Rate Limiting**
   - 10 req/min per room_id
   - Burst allowance: 20 requests
   - Return `Retry-After` header

7. **Add Performance Metrics**
   - Log processing time breakdown
   - Return metrics in response
   - Set up monitoring alerts

### Priority 3: Medium (Week 2)

8. **Add API Key Authentication**
   - Per-device API keys
   - Rotation mechanism
   - Audit logging

9. **Enable WebSocket Notifications**
   - Real-time updates to mobile apps
   - Reduce polling load

10. **Database Optimizations**
    - Bulk insert for presence logs
    - Add unique constraints
    - Index optimization

### Priority 4: Low (Future)

11. **API Versioning Strategy**
    - Document migration process
    - Deprecation timeline
    - Support v1 and v2 simultaneously

12. **Advanced Monitoring**
    - Prometheus metrics export
    - Grafana dashboards
    - Alert rules

---

## Conclusion

The current Edge API implementation provides a **solid foundation** but requires **critical enhancements** before production deployment. The highest risks are:

1. **DoS vulnerability** (no image size validation)
2. **Poor retry behavior** (no error codes, no idempotency)
3. **Performance issues** (sequential processing, N+1 queries)

**Estimated Enhancement Effort:**
- Priority 1 (Critical): 2-3 days
- Priority 2 (High): 2-3 days
- Priority 3 (Medium): 3-4 days
- **Total: 7-10 days**

**Recommended Timeline:**
- Week 1: Priority 1 + Priority 2 (deployment ready)
- Week 2: Priority 3 (production hardening)
- Week 3+: Priority 4 (optimization)

---

**Reviewed By:** Edge API Integration Specialist
**Next Steps:** Implement Priority 1 enhancements and integration test suite
