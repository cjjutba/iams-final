# Edge API Specialist Memory

## Critical Edge API Patterns

### 1. Base64 Image Validation (CRITICAL)
- **ALWAYS validate Base64 size BEFORE decode** to prevent memory attacks
- Max size: 15MB encoded (~10MB decoded)
- Validate image format (JPEG/PNG only) AFTER decode
- Validate dimensions (10x10 min, 4096x4096 max)
- Location: `backend/app/services/ml/face_recognition.py:decode_base64_image()`

### 2. Idempotency Pattern
- Use `request_id` field for deduplication
- Cache window: 5 minutes (in-memory for MVP, Redis for production)
- Cache key: `{request_id}:{room_id}:{timestamp}`
- Clean expired entries on each request
- Location: `backend/app/routers/face.py:_is_duplicate_request()`

### 3. Error Code Design for Retry Logic
- `success: false` + `error.retry: true` → Transient failure (retry)
- `success: false` + `error.retry: false` → Permanent failure (don't retry)
- Edge devices use this to decide queue/drop
- HTTP 200 for business errors, 4xx/5xx for protocol errors

### 4. Partial Batch Failure Handling
- Process faces individually in try-except blocks
- Continue processing on single face failure
- Return `success: true` even if some faces failed
- Log errors per-face for debugging
- Never fail entire batch for single bad image

### 5. Schema Validation Evolution
- Use Pydantic `field_validator` for custom validation (Pydantic v2 syntax)
- Make new fields Optional for backward compatibility
- Use `max_length` on string fields to prevent DoS
- Use `pattern` on IDs to restrict characters
- Constrain array sizes (min_length=1, max_length=10)

## Common Integration Issues

### Issue: Base64 Decode Memory Exhaustion
**Symptom:** Server crashes on large POST requests
**Root Cause:** Decoding multi-MB Base64 before size check
**Fix:** Validate `len(base64_string)` before `base64.b64decode()`
**Prevention:** Add `max_length` to Pydantic schema field

### Issue: Duplicate Presence Logs
**Symptom:** Student detected twice in same scan
**Root Cause:** RPi timeout → retry → backend processes twice
**Fix:** Check `request_id` in cache before processing
**Prevention:** Always generate `request_id` in edge device

### Issue: BMP/TIFF Images Crash FaceNet
**Symptom:** Face recognition fails with format error
**Root Cause:** Edge device sending non-JPEG formats
**Fix:** Validate `image.format in ['JPEG', 'PNG']` after decode
**Prevention:** Document supported formats clearly

### Issue: Negative Bbox Values
**Symptom:** Validation error on valid MediaPipe output
**Root Cause:** Bbox validation too strict
**Fix:** Made bbox Optional (MediaPipe doesn't always provide it)
**Prevention:** Test with real MediaPipe edge data

## Performance Optimization Patterns

### 1. Avoid N+1 Database Queries
- **Bad:** Loop over matched_users, call `log_detection()` each
- **Good:** Batch insert presence logs in single query
- **Implementation:** `presence_service.log_detections_batch()`

### 2. Parallel Face Processing (Future)
```python
# Sequential (current): 5 faces × 235ms = 1175ms
# Parallel (future): asyncio.gather() → ~250ms
tasks = [face_service.recognize_face(img) for img in images]
results = await asyncio.gather(*tasks, return_exceptions=True)
```

### 3. Processing Time Metrics
- Track start_time before processing
- Calculate `(time.time() - start_time) * 1000` for ms
- Return in response for monitoring
- Log for performance analysis

## Testing Patterns

### Test Image Generation
```python
from PIL import Image
import io, base64

img = Image.new('RGB', (112, 112), color='red')
img_bytes = io.BytesIO()
img.save(img_bytes, format='JPEG')
base64_str = base64.b64encode(img_bytes.getvalue()).decode('utf-8')
```

### Idempotency Test Pattern
1. Send request with `request_id`
2. Verify `processed >= 1`
3. Send same request again
4. Verify `processed == 0` (duplicate ignored)

### Error Test Pattern
- **Don't** expect HTTP 4xx/5xx for business errors
- **Do** check `response.json()["success"]` field
- **Do** check `error.code` for specific error type
- **Do** verify `error.retry` flag guides retry logic

## API Contract Backward Compatibility

### Breaking Changes (Require Edge Device Update)
- Removing required fields
- Changing field types
- Changing validation rules (stricter)
- Changing response structure

### Non-Breaking Changes (Safe)
- Adding optional fields with defaults
- Relaxing validation (e.g., bbox optional)
- Adding new response fields
- Adding error codes

### Migration Strategy
1. Add new field as Optional
2. Log warnings when old format used
3. Wait 2 weeks (allow edge device updates)
4. Make required if needed
5. Document in changelog

## RPi Queue Policy Compliance

**Backend Requirements:**
- Fast response (<500ms target, <2s max)
- Clear retry signals (error.retry flag)
- Idempotent requests (request_id support)
- Graceful degradation (partial failures OK)

**Edge Device Expectations:**
- Retry every 10 seconds on failure
- Queue max 500 items (5-min TTL)
- Burst traffic during queue drain
- May have clock drift (accept future timestamps)

## File Locations Reference

- Schema: `backend/app/schemas/face.py`
- Router: `backend/app/routers/face.py`
- Service: `backend/app/services/face_service.py`
- FaceNet: `backend/app/services/ml/face_recognition.py`
- Tests: `backend/tests/integration/test_edge_api.py`
- Docs: `docs/edge-api-validation-report.md`, `docs/edge-device-integration-guide.md`

## Next Enhancements (Priority Order)

1. ✅ Image size validation (DONE)
2. ✅ Error codes for retry logic (DONE)
3. ✅ Request idempotency (DONE)
4. ✅ Integration test suite (DONE)
5. 🔲 Parallel face processing (asyncio.gather)
6. 🔲 Bulk presence log insertion
7. 🔲 Rate limiting per room_id
8. 🔲 API key authentication
9. 🔲 WebSocket notifications
10. 🔲 Prometheus metrics export
