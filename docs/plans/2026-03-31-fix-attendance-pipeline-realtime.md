# Fix Attendance Pipeline + Real-Time Faculty Home Updates

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix the broken attendance recording pipeline so face detections become attendance records, and add real-time WebSocket updates to the faculty home screen hero card.

**Architecture:** The backend `presence.py:start_session` endpoint must also start a `SessionPipeline` (same as APScheduler auto-start). The `end_session` endpoint must also stop the pipeline. The faculty home ViewModel must use WebSocket for real-time stats instead of 15-second REST polling.

**Tech Stack:** FastAPI (backend), Kotlin/Compose (Android), WebSocket (OkHttp), APScheduler

---

## Root Cause

When faculty taps "Start Class", the `presence.py:start_session` endpoint:
1. Calls `PresenceService.start_session()` — creates legacy session + attendance records
2. Creates a `FrameGrabber` for the room
3. **Does NOT start a `SessionPipeline`** — so `TrackPresenceService` is never initialized, no frames are processed for attendance, and `attendance_summary` WebSocket messages have `total_enrolled=0`

The APScheduler auto-start (every 30s) DOES create pipelines, but it skips schedules that are already in `active_session_ids` — so manually-started sessions never get a pipeline.

Similarly, the `end_session` endpoint stops the legacy session and FrameGrabber but **does NOT stop the `SessionPipeline`**.

---

### Task 1: Backend — Start SessionPipeline in manual start_session endpoint

**Files:**
- Modify: `backend/app/routers/presence.py:75-129`

**Step 1: Add SessionPipeline startup to start_session endpoint**

After the FrameGrabber creation block (line 115), add pipeline startup logic. The logic mirrors `main.py:289-295` (APScheduler auto-start):

```python
# In start_session(), after FrameGrabber creation block, before the return:

            # Start real-time SessionPipeline
            session_pipelines = getattr(http_request.app.state, "session_pipelines", None)
            if session_pipelines is not None and body.schedule_id not in session_pipelines:
                grabber = frame_grabbers.get(room_id) if frame_grabbers else None
                if grabber:
                    try:
                        # Self-heal FAISS before starting pipeline
                        from app.services.ml.faiss_manager import faiss_manager

                        if faiss_manager.index is None or faiss_manager.index.ntotal == 0:
                            faiss_manager.load_or_create_index()
                        if not faiss_manager.user_map:
                            from app.services.face_service import FaceService
                            FaceService.reconcile_faiss_index(db)

                        from app.services.realtime_pipeline import SessionPipeline
                        pipeline = SessionPipeline(
                            schedule_id=body.schedule_id,
                            grabber=grabber,
                            db_factory=lambda: next(get_db()),
                        )
                        await pipeline.start()
                        session_pipelines[body.schedule_id] = pipeline
                        logger.info(f"SessionPipeline started for schedule {body.schedule_id}")
                    except Exception as pipe_err:
                        logger.error(f"Failed to start SessionPipeline: {pipe_err}")
```

Note: `get_db` yields a session from a generator. For `db_factory`, we need `SessionLocal` directly. Import it:

```python
from app.database import SessionLocal
```

And use `db_factory=SessionLocal` instead of the lambda.

**Step 2: Verify by testing manually — start a session, check logs for "SessionPipeline started"**

**Step 3: Commit**

```
feat(backend): start SessionPipeline on manual session start
```

---

### Task 2: Backend — Stop SessionPipeline in manual end_session endpoint

**Files:**
- Modify: `backend/app/routers/presence.py:138-206`

**Step 1: Add pipeline shutdown to end_session endpoint**

In `end_session()`, before the FrameGrabber stop block (line 169), stop the pipeline:

```python
        # Stop SessionPipeline if running
        session_pipelines = getattr(http_request.app.state, "session_pipelines", None)
        if session_pipelines is not None and schedule_id in session_pipelines:
            try:
                pipeline = session_pipelines.pop(schedule_id)
                await pipeline.stop()
                logger.info(f"SessionPipeline stopped for schedule {schedule_id}")
            except Exception as pipe_err:
                logger.error(f"Failed to stop SessionPipeline: {pipe_err}")
```

**Step 2: Commit**

```
feat(backend): stop SessionPipeline on manual session end
```

---

### Task 3: Backend — Prevent APScheduler from duplicating manually-started pipelines

**Files:**
- Modify: `backend/app/main.py:200-206`

The APScheduler lifecycle check already skips schedules in `all_active = active_session_ids | pipeline_ids`. Since Task 1 now adds the pipeline to `app.state.session_pipelines`, the schedule_id will be in `pipeline_ids` and the APScheduler will skip it. **No change needed** — verify this logic is correct by reading lines 200-206.

The existing guard:
```python
all_active = active_session_ids | pipeline_ids
for schedule in should_be_active:
    sid = str(schedule.id)
    if sid in all_active or PresenceService.was_session_ended_today(sid):
        continue
```

This correctly prevents duplication. **No code change needed for this task.**

---

### Task 4: Backend — Ensure auto-end also stops SessionPipeline (already works)

Verify the auto-end logic in `main.py:309-339` already stops pipelines:
```python
pipeline = app.state.session_pipelines.pop(sid, None)
if pipeline:
    await pipeline.stop()
```

This is already correct. **No code change needed.**

---

### Task 5: Android — Add WebSocket to FacultyHomeViewModel for real-time hero card stats

**Files:**
- Modify: `android/app/src/main/java/com/iams/app/ui/faculty/FacultyHomeViewModel.kt`

**Step 1: Add WebSocket client to the ViewModel**

The ViewModel currently uses REST polling every 15 seconds. Replace this with WebSocket for real-time updates:

1. Add `OkHttpClient` and `TokenManager` constructor params (already available via Hilt)
2. Create an `AttendanceWebSocketClient` when a session is active
3. Observe `attendanceSummary` flow for real-time stat updates
4. Update `liveAttendance` in `_uiState` from WebSocket messages
5. Keep REST poll as fallback (once on connect, not continuous)

Key changes:
- Add `AttendanceWebSocketClient` as a nullable field
- In `startLiveAttendancePolling()`, create the WS client, connect, and observe
- In `stopLiveAttendancePolling()`, disconnect the WS client
- Map `AttendanceSummaryMessage` → update `liveAttendance` fields in uiState
- Add `okHttpClient: OkHttpClient` and `tokenManager: TokenManager` to constructor

The `FacultyHomeUiState.liveAttendance` is already a `LiveAttendanceResponse?`. The hero card reads `liveAttendance?.presentCount`, `liveAttendance?.absentCount`, etc. We need to either:
- Create a `LiveAttendanceResponse` from the WS summary data, OR
- Add individual fields to `FacultyHomeUiState` for present/absent/late counts

Approach: Add individual fields since the WebSocket summary has counts directly:

```kotlin
data class FacultyHomeUiState(
    // ... existing fields ...
    val liveAttendance: LiveAttendanceResponse? = null,
    // New fields for real-time WS updates (override liveAttendance when available)
    val wsPresentCount: Int? = null,
    val wsAbsentCount: Int? = null,
    val wsLateCount: Int? = null,
    val wsEarlyLeaveCount: Int? = null,
    val wsTotalEnrolled: Int? = null,
)
```

Actually, simpler approach: just build a `LiveAttendanceResponse` from the WS data and set it as `liveAttendance`. The hero card already reads from `liveAttendance`.

**Step 2: Commit**

```
feat(android): add WebSocket real-time updates to faculty home hero card
```

---

### Task 6: Android — Update FacultyHomeScreen hero card to use real-time data

**Files:**
- Modify: `android/app/src/main/java/com/iams/app/ui/faculty/FacultyHomeScreen.kt`

The `ActiveSessionHeroCard` already reads from `uiState.liveAttendance`. Since Task 5 updates `liveAttendance` via WebSocket, the UI should auto-update via Compose recomposition.

Verify the hero card reads:
- `liveAttendance?.presentCount` → Present stat
- `liveAttendance?.absentCount` → Absent stat
- `liveAttendance?.lateCount` → Late stat
- `liveAttendance?.totalEnrolled` → denominator

If these fields match, **no UI change needed** — the Compose state flow handles recomposition.

---

### Task 7: Verify end-to-end flow

**Manual testing checklist:**
1. Faculty logs in, sees home screen
2. Faculty taps "Start Class" → hero card appears with SESSION ACTIVE
3. Backend logs show: "Session started with N students" + "SessionPipeline started"
4. Student walks in front of camera → face detected → backend logs "Student X checked in"
5. Hero card stats update in real-time (Present count goes from 0 to 1)
6. Open Live Feed → Attendance tab shows student as Present
7. Faculty taps "End Class" → session ends, pipeline stops
8. Auto-start: class scheduled for current time auto-starts (wait for 30s lifecycle check)
9. Auto-end: class past end_time auto-ends (wait for 30s lifecycle check)

---

## Lessons

- The `start_session` REST endpoint only started the legacy PresenceService but not the real-time SessionPipeline. Both must be started together.
- WebSocket token auth must use query params, not HTTP headers (fixed in prior commit).
- The faculty home screen polled REST every 15s — WebSocket gives instant updates.
