# Function Specifications

## Function Categories
- **User-Facing:** FUN-08-01 (WebSocket connect), FUN-08-05 (reconnect/cleanup) — require Supabase JWT.
- **System-Internal:** FUN-08-02, FUN-08-03, FUN-08-04 — backend service functions, no JWT.

---

## FUN-08-01 Open Authenticated WebSocket Connections

**Type:** User-facing

**Auth:** Supabase JWT (query parameter `token`). JWT `sub` must match path `user_id`.

**Goal:**
Accept only authenticated clients and bind each connection to a verified user identity.

**Inputs:**
- Path param: `user_id` (UUID)
- Query param: `token` (Supabase JWT string)

**Process:**
1. Parse and validate `user_id` (must be valid UUID format).
2. Extract JWT from `token` query parameter.
3. Verify JWT signature and expiration using `JWT_SECRET_KEY`.
4. Extract `sub` claim from JWT and compare with path `user_id`.
5. If mismatch, close with code 4003 (Forbidden).
6. If invalid/expired JWT, close with code 4001 (Unauthorized).
7. Evict any stale entries for same `user_id` from connection map.
8. Register socket in connection map with `connected_at` timestamp.

**Outputs:**
- Active WebSocket session bound to authenticated user.

**Validation Rules:**
- Reject missing/invalid/expired token → close code 4001.
- Reject user mismatch → close code 4003.
- Evict stale entry before registering new socket (idempotent reconnect).

---

## FUN-08-02 Publish Attendance Update Events

**Type:** System-internal

**Auth:** None (invoked by MOD-06 attendance service via direct function call).

**Caller Context:**
- Called by: `attendance_service.py` (MOD-06) on attendance status transitions (mark_present, mark_late, etc.).
- Call pattern: Synchronous in-line call from attendance service after status persistence.

**Goal:**
Push attendance changes to relevant connected clients.

**Inputs:**
- `student_id` (UUID) — target student
- `schedule_id` (UUID) — schedule context
- `status` (string) — new attendance status (`present`, `late`, `absent`, `early_leave`)
- `timestamp` (ISO-8601 datetime with timezone offset)

**Process:**
1. Build event envelope: `{ "type": "attendance_update", "data": { ... } }`.
2. Resolve target recipients (faculty assigned to schedule, the student themselves).
3. Send payload to all active sockets for resolved recipients.
4. Log delivery outcome if `WS_ENABLE_DELIVERY_LOGS` is enabled.

**Outputs:**
- Delivered `attendance_update` events to connected clients.

**Validation Rules:**
- Payload must include `student_id`, `status`, `timestamp` (required fields).
- Silent drop is not allowed; send failures must be logged with `user_id` and `event_type`.

---

## FUN-08-03 Publish Early-Leave Events

**Type:** System-internal

**Auth:** None (invoked by MOD-07 presence service via direct function call).

**Caller Context:**
- Called by: `presence_service.py` (MOD-07) when early-leave threshold is reached (3 consecutive misses).
- Call pattern: Synchronous in-line call after early-leave event creation and attendance status update.

**Goal:**
Push early-leave alerts as soon as threshold logic flags a student.

**Inputs:**
- `student_id` (UUID) — target student
- `student_name` (string, optional) — display name
- `schedule_id` (UUID) — schedule context
- `detected_at` (ISO-8601 datetime with timezone offset)
- `consecutive_misses` (integer, optional) — miss count at detection

**Process:**
1. Build event envelope: `{ "type": "early_leave", "data": { ... } }`.
2. Resolve faculty recipients for the schedule.
3. Send to active connections for resolved recipients.
4. Log delivery outcome if enabled.

**Outputs:**
- Delivered `early_leave` alert events to connected clients.

**Validation Rules:**
- Event must contain `student_id`, `schedule_id`, `detected_at` (required fields).
- Duplicate emission for same `(attendance_id)` context should be prevented when dedup key exists (dedup responsibility is in MOD-07, but MOD-08 should not re-emit if called twice for same event).

---

## FUN-08-04 Publish Session-End Summary Events

**Type:** System-internal

**Auth:** None (invoked by session finalization flow).

**Caller Context:**
- Called by: Session finalization logic (triggered when schedule end time is reached or session is manually closed).
- Call pattern: Called once per schedule/date session at session end.

**Goal:**
Push summary counts when a class session ends.

**Inputs:**
- `schedule_id` (UUID) — schedule context
- `date` (DATE) — session date in configured timezone
- `summary` (object) — `{ present: int, late: int, early_leave: int, absent: int }`

**Process:**
1. Build event envelope: `{ "type": "session_end", "data": { ... } }`.
2. Resolve recipients: faculty assigned to schedule + enrolled students.
3. Send summary to active clients for resolved recipients.

**Outputs:**
- Delivered `session_end` summary events to connected clients.

**Validation Rules:**
- Summary must include `present`, `late`, `early_leave`, `absent` count fields.
- Session end should be emitted once per schedule/date session (idempotent).

---

## FUN-08-05 Handle Reconnect and Stale Connection Cleanup

**Type:** User-facing

**Auth:** Supabase JWT (reconnect follows same auth flow as FUN-08-01).

**Goal:**
Maintain healthy connection map across disconnects, app backgrounding, and network loss.

**Inputs:**
- Disconnect signals (WebSocket close events).
- Send failures (failed message delivery attempts).
- Heartbeat timeouts (no pong response within `WS_STALE_TIMEOUT`).
- Reconnect attempts (new connection from same `user_id`).

**Process:**
1. On disconnect/error: remove socket entry from connection map.
2. On heartbeat timeout (no pong within `WS_STALE_TIMEOUT` seconds): mark as stale and close.
3. On reconnect: follow FUN-08-01 auth flow, evict stale entry, register new socket.
4. Resume event fanout to latest active socket.

**Outputs:**
- Clean connection map and stable reconnect behavior.

**Validation Rules:**
- Cleanup must not remove active healthy sockets.
- Reconnect must be idempotent — no unbounded duplicate entries.
- Periodic sweeper may remove old inactive entries beyond `WS_STALE_TIMEOUT`.
