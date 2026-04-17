# Session 05 — Backend WebSocket Protocol Additions

**Deliverable:** add `server_time_ms` + `frame_sequence` to `frame_update` broadcasts and a new `GET /api/v1/health/time` endpoint.
**Blocks:** session 04 integration-test, session 06.
**Blocked by:** nothing.
**Est. effort:** 1 hour.

Read [00-master-plan.md](00-master-plan.md) §5.3.

---

## 1. Scope

Two additive backend changes:

1. Broadcast `server_time_ms` (UTC epoch milliseconds) and `frame_sequence` (monotonic int) on every `frame_update` message.
2. Add a tiny health endpoint `GET /api/v1/health/time` returning `{"server_time_ms": <long>}` for Session 04's clock-sync.

Both are **backwards-compatible additions** — the legacy overlay ignores extra keys, legacy clients don't call the new endpoint. No protocol version bump needed.

## 2. Files

| Path | New? |
|------|------|
| `backend/app/services/realtime_pipeline.py` | MODIFIED |
| `backend/app/routers/health.py` | MODIFIED (or create if missing; check first) |
| `backend/tests/test_websocket_protocol.py` | NEW (or extend existing) |

## 3. Implementation steps

### Step 1 — `realtime_pipeline.py::_broadcast_frame_update`

Locate lines ~278-309 ([source](../../../backend/app/services/realtime_pipeline.py#L278)). Add a class attribute `self._frame_sequence = 0` in `__init__`. Increment at the top of `_broadcast_frame_update`. Add two keys to the payload:

```python
import time as _time

self._frame_sequence += 1
payload = {
    "type": "frame_update",
    "timestamp": track_frame.timestamp,
    "server_time_ms": int(_time.time() * 1000),        # NEW
    "frame_sequence": self._frame_sequence,             # NEW
    "frame_size": [settings.FRAME_GRABBER_WIDTH, settings.FRAME_GRABBER_HEIGHT],
    "tracks": tracks_data,
    "fps": round(track_frame.fps, 1),
    "processing_ms": round(track_frame.processing_ms, 1),
}
await ws_manager.broadcast_attendance(self.schedule_id, payload)
```

Nothing else in this method changes.

### Step 2 — `health.py` — new endpoint

Check whether `backend/app/routers/health.py` exists (look for `main.py` registering a router at `/api/v1/health`). If it exists, extend. If not, create with:

```python
import time
from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["health"])

@router.get("/time")
async def server_time() -> dict:
    """Return current UTC epoch milliseconds. Used by Android clock-sync."""
    return {"server_time_ms": int(time.time() * 1000)}
```

Wire the router in `app/main.py` under the `/api/v1` prefix if the existing health router isn't already included.

### Step 3 — `test_websocket_protocol.py`

Two test cases. Use pytest + pytest-asyncio + existing test fixtures.

```python
async def test_frame_update_contains_server_time_ms(active_pipeline_fixture):
    """Every frame_update payload must include server_time_ms as UTC epoch ms."""
    # Capture one broadcast message, assert 'server_time_ms' key present and within ±5s of now

async def test_frame_sequence_monotonic(active_pipeline_fixture):
    """frame_sequence must strictly increase within a session."""
    # Capture 5 consecutive broadcasts, assert sequence is strictly increasing
```

For the health endpoint, use `TestClient`:

```python
def test_health_time_returns_epoch_ms(client):
    r = client.get("/api/v1/health/time")
    assert r.status_code == 200
    j = r.json()
    assert "server_time_ms" in j
    assert abs(j["server_time_ms"] - int(time.time() * 1000)) < 5000
```

## 4. Acceptance criteria

- [ ] `docker compose exec api-gateway python -m pytest tests/test_websocket_protocol.py -q` green.
- [ ] `curl http://localhost:8000/api/v1/health/time` returns `{"server_time_ms": 1744876543210}` (example).
- [ ] Live WS session in a browser dev-tools panel shows `server_time_ms` + `frame_sequence` on every `frame_update`.
- [ ] Legacy client (old Android APK without Session 05 changes) still decodes the message without crashing (the extra keys are ignored).
- [ ] `frame_sequence` resets to 0 on new `SessionPipeline` start (i.e., restarts when a schedule session restarts — expected behaviour).
- [ ] No change to `broadcast_attendance_summary`, `broadcast_stream_status`, `_handle_event` payloads (unscoped).

## 5. Anti-goals

- Do not add protocol versioning (`v2` etc.). The additions are backward compatible.
- Do not change the pipeline's processing cadence.
- Do not rename existing fields.
- Do not add authentication to `/health/time` (it's a trivial public endpoint by design).
- Do not add CORS logic (the existing middleware covers it).

## 6. Handoff notes

**For Session 04:** endpoint is `GET /api/v1/health/time` returning `{"server_time_ms": <int>}`.

**For Session 06:** the ViewModel reads `server_time_ms` off incoming WS messages and passes to `matcher.onBackendFrame(tracks, serverTimeMs, System.nanoTime())`.

## 7. Risks

- **NTP drift on VPS:** DigitalOcean droplets sync via `systemd-timesyncd` by default. Good enough (± 50 ms). No extra config.
- **Non-monotonic time jump:** if the VPS clock jumps backwards (rare but possible), `server_time_ms` decreases. Matcher tolerates ±1.5 s skew per master §5.1, so a small backward jump is harmless.
- **frame_sequence across restarts:** documented; not a bug.

## 8. Commit message template

```
hybrid(05): add server_time_ms + frame_sequence to frame_update; add /health/time

Backwards-compatible additions to the realtime WebSocket payload so the
Android FaceIdentityMatcher can align backend track timestamps with the
device's wallclock via session 04's TimeSyncClient.

Also exposes a tiny GET /api/v1/health/time endpoint for clock-skew
estimation. Legacy clients ignore the new fields.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

## 9. Lessons

- Backwards-compatible JSON extensions beat a v2 endpoint for purely additive changes.
- The WS payload already carries `timestamp` as monotonic float; adding epoch-ms made the contract explicit for cross-device sync.
