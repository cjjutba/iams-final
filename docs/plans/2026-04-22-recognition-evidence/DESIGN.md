# Recognition Evidence — Design

**Branch:** `feat/local-compute-split`
**Date:** 2026-04-22
**Builds on:** `docs/plans/2026-04-22-two-app-split/DESIGN.md`

---

## Problem

Today the recognition pipeline is a black box to anyone outside the code. A student walks into frame, the overlay turns green, and an `attendance_records` row flips to `PRESENT`. There is no evidence trail — no persisted similarity score, no paired registered-crop ↔ live-crop, no per-decision timestamp that an admin (or a thesis panelist) can audit after the fact. The aligned 112×112 crop that feeds ArcFace is computed once at [backend/app/services/realtime_tracker.py:311](../../../backend/app/services/realtime_tracker.py#L311) and discarded the instant the quality gate is done with it.

Three failures follow from this:

1. **Thesis-defense-grade empirical evidence is missing.** We claim `RECOGNITION_THRESHOLD=0.3` is the right tuning; we cannot show a histogram to back it up.
2. **Disputes are unarbitrable.** A parent contesting an early-leave event has nothing to look at — no timestamped crop that proves it was or wasn't their child.
3. **Admins cannot build trust in the system.** The demo is "it works" not "here is how it decided."

The fix is a first-class `recognition_events` record for every FAISS decision (match and miss), with paired crops, and two front-end views: a live streaming panel for demo + a per-attendance evidence drawer for audit. Then: retention, exports, signed URLs, access auditing — the things that distinguish a thesis artifact from an operable system.

## Constraints

Carried forward from the 2026-04-21 local-compute-split:

- All recognition runs on the on-prem Mac; all face PII (embeddings, crops) must remain on-prem. The VPS never sees a recognition event. `ENABLE_ML=false` on the VPS keeps the routers off.
- The real-time pipeline must stay within its frame budget (~0.5–1 fps at `buffalo_l` on CPU). **Evidence capture must never back-pressure the pipeline.** If the disk is slow or Postgres is unhappy, we drop events — we do not drop frames.
- Crops are biometric PII under the Philippine Data Privacy Act. Retention must be bounded and right-to-delete must cascade from `face_registrations`.

New constraints:

- Per-event disk cost must be bounded: JPEG quality tuned so a full classroom-day (8 hr × 2 cameras × ~3 tracked faces avg × 10 fps ≈ 1.7 M events worst-case) is storage-feasible. The write rate is the real pressure, not the steady state.
- Admin-only access, enforced at both the route guard and query layer.
- Threshold snapshot on every row. When we retune `RECOGNITION_THRESHOLD` or swap `INSIGHTFACE_MODEL`, historical decisions must remain auditable against the parameters that were in effect at decision time.

## Target architecture

```
┌── Mac (on-prem) ──────────────────────────────────────────────────┐
│                                                                    │
│  realtime_tracker._recognize_batch() @ realtime_tracker.py:740     │
│    ├─ produces: (track_id, user_id, similarity, crop, threshold)   │
│    └─ NEW: emits RecognitionEventDraft into evidence_writer queue  │
│                                                                    │
│  evidence_writer (new, backend/app/services/evidence_writer.py)    │
│    ├─ bounded asyncio.Queue(maxsize=1000)                          │
│    ├─ crop task:    JPEG-encode + write to disk (Docker volume)    │
│    ├─ db task:      batch INSERT every 500 ms or 50 rows           │
│    ├─ ws task:      emit `recognition_event` via ws_manager        │
│    └─ drop policy:  if queue full, drop row + metric++             │
│                                                                    │
│  Postgres:                                                         │
│    └─ recognition_events        (new, Phase 1)                     │
│    └─ recognition_access_audit  (new, Phase 5)                     │
│                                                                    │
│  Disk / MinIO:                                                     │
│    └─ /var/lib/iams/crops/{yyyy-mm-dd}/{event_id}-live.jpg         │
│    └─ /var/lib/iams/crops/{yyyy-mm-dd}/{event_id}-reg.jpg          │
│    └─ (Phase 5) migrated to MinIO bucket iams-recognition-evidence │
│                                                                    │
│  ws_manager.broadcast_attendance(schedule_id, {                    │
│      type: "recognition_event", ...payload, crop_urls: {...}       │
│  })  @ backend/app/routers/websocket.py:57                         │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
                                │
                                │ WebSocket + REST (admin-only)
                                v
┌── Admin portal (on-prem, nginx-served SPA) ───────────────────────┐
│                                                                    │
│  Phase 2: /schedules/[id]/live → <RecognitionPanel />              │
│     virtualized feed of recognition_event messages,                │
│     crop thumbnails, score bar w/ threshold marker                 │
│                                                                    │
│  Phase 3: /schedules/[id] → <AttendanceDetailSheet />              │
│     extended with <MatchEvidence student_id=... />                 │
│     best match / worst accepted / score histogram / timeline       │
│                                                                    │
│  Phase 4: /recognitions (new route) → <RecognitionAudit />         │
│     cross-schedule filter, date range, CSV export                  │
│                                                                    │
│  Phase 5: all three views honor signed-URL flow + log access       │
│     every crop fetch → POST /api/v1/recognitions/{id}/viewed       │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

## Data model

```sql
-- Phase 1
CREATE TABLE recognition_events (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    schedule_id       UUID NOT NULL REFERENCES schedules(id) ON DELETE CASCADE,
    session_id        UUID NULL,                   -- future: when a real sessions table exists
    student_id        UUID NULL REFERENCES users(id) ON DELETE SET NULL,
    track_id          INTEGER NOT NULL,
    camera_id         TEXT NOT NULL,               -- e.g. 'eb226'
    frame_idx         BIGINT NOT NULL,             -- RealtimeTracker frame counter
    similarity        REAL NOT NULL,               -- raw FAISS inner-product score
    threshold_used    REAL NOT NULL,               -- snapshot of settings.RECOGNITION_THRESHOLD at event time
    matched           BOOLEAN NOT NULL,            -- similarity >= threshold_used AND NOT ambiguous
    is_ambiguous      BOOLEAN NOT NULL DEFAULT FALSE,
    det_score         REAL NOT NULL,               -- SCRFD detection confidence
    embedding_norm    REAL NOT NULL,               -- ||e||_2 pre-normalization (QA signal)
    bbox              JSONB NOT NULL,              -- {x1,y1,x2,y2} in source-frame px
    live_crop_ref     TEXT NOT NULL,               -- relative path under CROP_ROOT
    registered_crop_ref TEXT NULL,                 -- null when matched=false
    model_name        TEXT NOT NULL,               -- e.g. 'buffalo_l'
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_recognition_events_schedule_created
    ON recognition_events (schedule_id, created_at DESC);
CREATE INDEX ix_recognition_events_student_created
    ON recognition_events (student_id, created_at DESC)
    WHERE student_id IS NOT NULL;
CREATE INDEX ix_recognition_events_matched
    ON recognition_events (schedule_id, created_at DESC)
    WHERE matched = TRUE;
CREATE INDEX ix_recognition_events_track
    ON recognition_events (schedule_id, track_id, created_at);

-- Phase 5
CREATE TABLE recognition_access_audit (
    id              BIGSERIAL PRIMARY KEY,
    viewer_user_id  UUID NOT NULL REFERENCES users(id),
    event_id        UUID NOT NULL REFERENCES recognition_events(id) ON DELETE CASCADE,
    crop_kind       TEXT NOT NULL CHECK (crop_kind IN ('live', 'registered')),
    viewed_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ip              INET NULL,
    user_agent      TEXT NULL
);
CREATE INDEX ix_recognition_access_viewer_time
    ON recognition_access_audit (viewer_user_id, viewed_at DESC);
```

Retention (Phase 4):
- Crops: default 30 days, configurable via `RECOGNITION_CROP_RETENTION_DAYS`.
- Rows: default 365 days, configurable via `RECOGNITION_EVENT_RETENTION_DAYS`.
- Access-audit rows: 3 years (no configurability — legal).

## Phase overview

| Phase | Scope | Risk | Shippable by itself? |
|---|---|---|---|
| **1 — Silent capture** | Alembic migration, `evidence_writer` service, crop writer, DB batcher, pipeline intercept. No UI. | Low. Pipeline change is additive; any failure short-circuits to "no event written" and is logged. | Yes (captures data; admin can query raw SQL) |
| **2 — Live panel** | WS contract extension, REST endpoint, admin-portal `RecognitionPanel`. | Medium. New WS type is additive. REST is new. Frontend virtualization is the unknown. | Yes (thesis-demo-grade) |
| **3 — Per-student evidence** | REST endpoint for per-attendance events, extend attendance details sheet. | Low. UI addition only. | Yes (adds audit view) |
| **4 — Global page + exports + retention** | New `/recognitions` route, CSV export, nightly retention job. | Low-medium. Retention job has delete blast radius — gated on feature flag. | Yes (production-ready) |
| **5 — Enterprise hardening** | Migrate crops to MinIO, signed URLs, `recognition_access_audit` table, view-logging on every crop fetch. | Medium. Storage migration touches live data; cutover must be zero-downtime. | Yes (enterprise-ready) |

All five phases ship on `feat/local-compute-split`. Phase commits are one-PR-per-phase.

---

## Phase 1 — Silent capture

**Goal:** every FAISS decision on the Mac pipeline persists to `recognition_events` + disk within 1 s of the event, without affecting pipeline fps. No UI.

### 1.1 Alembic migration

File: `backend/alembic/versions/c9d0e1f2a3b4_add_recognition_events_table.py`
Naming: follows the hex-prefix convention ([b8c9d0e1f2a3_notifications_utc_timestamps.py](../../../backend/alembic/versions/b8c9d0e1f2a3_notifications_utc_timestamps.py) was the last one).
`down_revision = "b8c9d0e1f2a3"`.

Upgrade creates the table + indexes shown in the Data Model section. Downgrade drops the table and indexes. No backfill — this is a forward-only feature.

### 1.2 SQLAlchemy model

File: `backend/app/models/recognition_event.py`

Uses the same declarative base as the rest of the models. Import it into `backend/app/models/__init__.py` so Alembic autogenerate stays honest for future migrations (even though this one is hand-written).

### 1.3 Evidence writer service

File: `backend/app/services/evidence_writer.py` (new)

- Owns two asyncio workers: one for crop I/O, one for DB inserts.
- Public API: `async def submit(draft: RecognitionEventDraft) -> None`.
- The draft carries pre-computed fields only — no numpy arrays — so encoding errors surface at the call site, not two hops deep.
- Bounded `asyncio.Queue(maxsize=1000)`. On `QueueFull`, drop the event, bump `iams_recognition_events_dropped_total` counter, log at WARNING no more than once per 30 s.
- DB worker batches: flush every 500 ms or on 50 rows, whichever comes first. One `executemany`/`INSERT ... VALUES (...), (...)` call per flush.
- Crop worker: serial JPEG encode (cv2.imencode, Q=75), filesystem write, fsync off. Filenames use the event UUID — uniqueness by construction, no coordination with the DB worker.

Lifecycle: service starts in `backend/app/main.py` lifespan block alongside the existing ML bootstrap, guarded by `ENABLE_ML` (same gate as the rest of the pipeline).

### 1.4 Pipeline intercept

Single edit point: [backend/app/services/realtime_tracker.py:740](../../../backend/app/services/realtime_tracker.py#L740) in `_recognize_batch`.

Inside the `for (identity, search_embedding), result in zip(pending, batch_results)` loop, after the match/miss decision is final (just before `identity.last_verified = now`), build a `RecognitionEventDraft` and fire-and-forget submit it:

```python
draft = RecognitionEventDraft(
    schedule_id=self.schedule_id,
    student_id=user_id if (user_id and not is_ambiguous) else None,
    track_id=identity.track_id,
    camera_id=self.camera_id,
    frame_idx=self._frame_counter,
    similarity=float(confidence),
    threshold_used=float(settings.RECOGNITION_THRESHOLD),
    matched=bool(user_id and not is_ambiguous),
    is_ambiguous=bool(is_ambiguous),
    det_score=float(identity.last_det_score),
    embedding_norm=float(np.linalg.norm(search_embedding)),
    bbox=identity.last_bbox,
    live_crop=identity.last_crop,           # new on TrackIdentity; set in process_frame
    model_name=settings.INSIGHTFACE_MODEL,
)
asyncio.create_task(evidence_writer.submit(draft))
```

Supporting edits:

- `TrackIdentity` gains three fields: `last_bbox`, `last_crop` (numpy ndarray), `last_det_score`. All populated at [realtime_tracker.py:308-313](../../../backend/app/services/realtime_tracker.py#L308-L313) where the crop already exists.
- On the first match for an identity, the writer resolves the registered-crop path from `face_registrations.crop_path` (schema unchanged — field already exists per [face_registration.py](../../../backend/app/models/face_registration.py)) and caches the path on the `TrackIdentity` so subsequent events reuse it.

### 1.5 Config

New settings in `backend/app/config.py`:

| Setting | Default | Notes |
|---|---|---|
| `ENABLE_RECOGNITION_EVIDENCE` | `True` on Mac, `False` on VPS | Master switch |
| `RECOGNITION_EVIDENCE_CROP_ROOT` | `/var/lib/iams/crops` | Inside the container; mapped to a Docker volume |
| `RECOGNITION_EVIDENCE_CROP_QUALITY` | `75` | JPEG Q |
| `RECOGNITION_EVIDENCE_QUEUE_SIZE` | `1000` | Drop threshold |
| `RECOGNITION_EVIDENCE_BATCH_ROWS` | `50` | DB flush trigger |
| `RECOGNITION_EVIDENCE_BATCH_MS` | `500` | DB flush interval |

### 1.6 Docker volume

`deploy/docker-compose.onprem.yml`: new named volume `iams-crops-onprem` mounted at `/var/lib/iams/crops` on the `api-gateway-onprem` service. Owned by `appuser` (chown in entrypoint, same pattern as the insightface models volume).

### 1.7 Phase 1 verification

| # | Check | Expected |
|---|---|---|
| 1 | `docker exec iams-api-gateway-onprem alembic upgrade head` | Exits 0; `\d recognition_events` shows the table |
| 2 | Walk into frame of an active schedule for 30 s | `SELECT COUNT(*) FROM recognition_events WHERE schedule_id = :id` grows monotonically |
| 3 | `ls /var/lib/iams/crops/$(date +%Y-%m-%d)/` | Non-empty; each event has `<uuid>-live.jpg`; matched events also have `-reg.jpg` |
| 4 | Histogram: `SELECT width_bucket(similarity, 0, 1, 20), count(*) FROM recognition_events WHERE schedule_id = :id GROUP BY 1` | Bimodal: low-similarity mass (strangers, posters) + high-similarity mass (registered students) |
| 5 | Kill postgres, wait 10 s, restart | `iams_recognition_events_dropped_total` increases; pipeline fps unchanged |
| 6 | Load test: paste 200 tracks/s into the queue | Queue drops after 1000; no fps regression |
| 7 | `curl http://<VPS>/api/v1/recognitions` | 404 (feature gated by `ENABLE_ML=false`) |

---

## Phase 2 — Live panel

**Goal:** an admin watching `/schedules/[id]/live` sees every recognition decision stream in beside the video in real time, with crop-pair + score + threshold marker.

### 2.1 WS contract

New message type on the existing `/api/v1/ws/attendance/{schedule_id}` channel (no new endpoint). Broadcast site: `evidence_writer`'s ws worker, which calls `ws_manager.broadcast_attendance(schedule_id, payload)` at [backend/app/routers/websocket.py:57](../../../backend/app/routers/websocket.py#L57).

Payload:

```json
{
  "type": "recognition_event",
  "event_id": "uuid",
  "track_id": 42,
  "camera_id": "eb226",
  "timestamp": 1714234800.123,
  "server_time_ms": 1714234800123,
  "student_id": "uuid-or-null",
  "student_name": "Maricon G.",
  "similarity": 0.742,
  "threshold_used": 0.3,
  "matched": true,
  "is_ambiguous": false,
  "det_score": 0.91,
  "bbox": {"x1": 820, "y1": 310, "x2": 970, "y2": 480},
  "crop_urls": {
    "live": "/api/v1/recognitions/<event_id>/live-crop",
    "registered": "/api/v1/recognitions/<event_id>/registered-crop"
  }
}
```

Rationale: crops are **always URLs, never base64**. At WHEP + frame_update rates, WS payload is already tight. Browser fetches thumbnails via intersection observer when the row scrolls into view.

### 2.2 REST endpoints

Mount under existing `/api/v1/recognitions/` prefix (new router), gated on `ENABLE_ML=True` and admin-role dependency.

| Method | Path | Purpose |
|---|---|---|
| `GET`  | `/api/v1/recognitions` | Cursor-paginated list. Filters: `schedule_id`, `student_id`, `matched`, `since`, `until`, `cursor`, `limit` (max 200). |
| `GET`  | `/api/v1/recognitions/{event_id}` | Full event detail |
| `GET`  | `/api/v1/recognitions/{event_id}/live-crop` | Returns JPEG bytes (Phase 2-4) or 302 to signed URL (Phase 5) |
| `GET`  | `/api/v1/recognitions/{event_id}/registered-crop` | Same |

Pagination: cursor-based, keyed on `(created_at, id)` descending. **Never offset** — at 1 M rows, offset-pagination's `OFFSET 950000` is a full scan.

### 2.3 Admin portal panel

New component: `admin/src/components/live-feed/RecognitionPanel.tsx`.

Mounted on [admin/src/routes/schedules/[id]/live.tsx](../../../admin/src/routes/schedules/[id]/live.tsx) as a right-side collapsible panel (or bottom sheet on narrower viewports).

Behavior:

- Subscribes to the existing `useAttendanceWs(scheduleId)` hook; filters messages on `type === 'recognition_event'`.
- Virtualized list via `react-virtuoso` (Tanstack-virtual is also fine; Virtuoso's `followOutput` handles auto-scroll-to-bottom cleanly).
- Each row:
  - Timestamp (relative: "2s ago") + absolute on hover.
  - Track ID chip (colored by track_id modulo N; same palette as `DetectionOverlay`).
  - Student avatar + name, or "Unknown" pill for `matched=false`.
  - Pair of thumbnails (registered ↔ live) with a thin divider; lazy-loaded via intersection observer.
  - Score bar: a horizontal bar 0.0–1.0 with a vertical line at `threshold_used`. Score fill is green when `matched`, orange otherwise.
  - Ambiguity badge if `is_ambiguous`.
- Top-of-panel controls:
  - Pause/Resume toggle (essential during demo — freeze the stream to point at a frame).
  - Filter: `All | Matched | Unknown | Ambiguous`.
  - Min-similarity slider.
  - Student picker (for zooming in on a single student's events).
- Non-live (historical) scroll loads more via cursor.

Loading/empty states: skeleton rows while paused-and-filtered; "No recent recognitions" card when the buffer is empty.

### 2.4 Phase 2 verification

| # | Check | Expected |
|---|---|---|
| 1 | Open `/schedules/<id>/live` with session running | Panel appears; rows start streaming within 2 s |
| 2 | Pause, then apply `Matched` filter | Feed freezes; historical rows load via REST; filter applies client-side + server-side on scroll |
| 3 | Click a row with a known student | Thumbnail pair visible; score bar matches number |
| 4 | Walk off-frame for 30 s | Panel continues; no unhandled-promise exceptions in devtools |
| 5 | 500 rows in buffer | List stays smooth (60 fps scroll); memory doesn't grow unboundedly |
| 6 | Unauthorized user (faculty role) hits `/api/v1/recognitions` | 403 |

---

## Phase 3 — Per-student evidence

**Goal:** clicking an attendance row in `/schedules/[id]` opens the existing attendance-details sheet, which now shows the timestamped evidence trail for why that student was marked PRESENT / LATE / EARLY_LEAVE.

### 3.1 REST endpoint

`GET /api/v1/recognitions/summary?schedule_id=&student_id=` (new) returns:

```json
{
  "student_id": "uuid",
  "schedule_id": "uuid",
  "match_count": 42,
  "miss_count": 8,
  "best_match": { event_id, similarity, timestamp },
  "worst_accepted": { event_id, similarity, timestamp },
  "first_match": { event_id, timestamp },
  "last_match": { event_id, timestamp },
  "histogram": [...],                  // 20 buckets 0..1
  "timeline": [                         // per-minute match density
    {"minute": "2026-04-22T08:02:00Z", "matches": 3, "misses": 0},
    ...
  ],
  "threshold_at_session": 0.3
}
```

Pure query aggregation; no new columns.

### 3.2 UI

Extend `admin/src/components/attendance/AttendanceDetailSheet.tsx` (existing per recent commit `b068145`) with a new `<MatchEvidence />` section:

- **Why-PRESENT narrative sentence** rendered at top: `"<name> matched <match_count> times between <first> and <last> (peak similarity <best>, threshold <thr>)."`
- **Histogram** (sparkline-style) with the threshold line overlaid.
- **Timeline scrubber** showing density across the session; hover reveals the minute's match count.
- **Peak evidence**: the best-match event rendered inline — registered crop ↔ live crop, score.
- **"See all matches"** link → opens `/recognitions?schedule_id=…&student_id=…` (Phase 4 route).

### 3.3 Phase 3 verification

| # | Check | Expected |
|---|---|---|
| 1 | Open attendance sheet for a PRESENT student | Evidence section populated; best-match score ≥ threshold |
| 2 | Open sheet for an ABSENT student | Evidence section renders "No matches recorded" gracefully |
| 3 | Open sheet for an EARLY_LEAVE student | Timeline shows match density dropping before `end_time` |
| 4 | Share the `/recognitions?...` URL | Phase 4 route renders filtered list |

---

## Phase 4 — Global page + exports + retention

**Goal:** a cross-schedule audit view, bulk export, and bounded storage.

### 4.1 Route + UI

New route `/recognitions` (admin-only). Component: `admin/src/routes/recognitions/index.tsx`.

Columns: timestamp, schedule (link), student (link), matched (bool pill), similarity, threshold, camera, live-thumbnail, registered-thumbnail.

Filters: date range, schedule, student, camera, matched-only, min/max similarity.
Sort: `created_at DESC` only (cursor forbids alternate sorts at query layer).

Export button: triggers `GET /api/v1/recognitions/export.csv?...` with the same filters. Server streams rows; no row cap up to the filtered set.

### 4.2 Retention job

APScheduler cron, daily at 03:00 local time. Wrapped behind `ENABLE_RECOGNITION_EVIDENCE_RETENTION=True` (default true).

Two passes:

1. Delete crop files older than `RECOGNITION_CROP_RETENTION_DAYS` (default 30).
2. Delete rows older than `RECOGNITION_EVENT_RETENTION_DAYS` (default 365).

Safety:

- Dry-run mode (`RECOGNITION_EVIDENCE_RETENTION_DRY_RUN=True`, default **true** until after Phase 5 cuts over) — logs the target set but does not delete.
- Hard cap of 10 k deletes per run; if a run would exceed, log and stop. Prevents a config mistake from nuking the table.
- Metrics: `iams_recognition_retention_crops_deleted_total`, `iams_recognition_retention_rows_deleted_total`.

### 4.3 Phase 4 verification

| # | Check | Expected |
|---|---|---|
| 1 | `/recognitions` loads across multiple schedules | Paginates via cursor; filter changes re-query |
| 2 | Export 5000-row CSV | Streams (no OOM); row count matches filter count |
| 3 | Set retention to 1 day in dry-run mode, run job | Log shows "would delete N crops, M rows"; disk/DB unchanged |
| 4 | Flip dry-run off, re-run | Disk + DB both shrink; metrics increment |
| 5 | Set retention days to 0 by mistake | Job refuses (hard cap triggers) |

---

## Phase 5 — Enterprise hardening

**Goal:** storage, encryption, access auditing, and signed URLs — the things that make this deployable outside a thesis classroom.

### 5.1 MinIO on the Mac

Add `iams-minio-onprem` service to `deploy/docker-compose.onprem.yml`:

- Image: `minio/minio:RELEASE.2024-XX-XX`.
- Ports: 9000 (API) + 9001 (console).
- Volumes: `iams-minio-data-onprem`.
- Encryption at rest: `MINIO_KMS_SECRET_KEY` seeded via `scripts/.env.local` (new field: `MINIO_ENCRYPTION_KEY=<32 bytes b64>`).
- Bucket: `iams-recognition-evidence`, lifecycle policy: `Expiration: 30d` (matches `RECOGNITION_CROP_RETENTION_DAYS` — single source of truth).

### 5.2 Storage abstraction

New: `backend/app/services/evidence_storage.py`

- Interface: `put(key, bytes) -> None`, `presigned_get(key, ttl) -> str`, `delete(key) -> None`.
- Two implementations: `FilesystemStorage` (Phase 1–4), `MinioStorage` (Phase 5).
- Selected by `RECOGNITION_EVIDENCE_BACKEND` env var (`filesystem` | `minio`).

### 5.3 Cutover

Online migration, no downtime:

1. Set `RECOGNITION_EVIDENCE_BACKEND=minio`, redeploy. New events write to MinIO.
2. Background sync script (`scripts/migrate_crops_to_minio.py`) copies existing filesystem crops → MinIO, updates `live_crop_ref` / `registered_crop_ref` to the MinIO key in-place. Idempotent.
3. Verify: `SELECT COUNT(*) WHERE live_crop_ref NOT LIKE 'minio://%'` = 0.
4. Remove the `iams-crops-onprem` volume on next deploy.

### 5.4 Signed URLs

`/api/v1/recognitions/{id}/live-crop` returns `302 Found` → MinIO presigned URL with TTL 60 s (configurable via `RECOGNITION_EVIDENCE_SIGNED_URL_TTL`). Browser fetches the JPEG directly from MinIO. API container does not proxy bytes.

Implication for the WS payload: `crop_urls.live` becomes the API redirect URL, not the direct MinIO URL. Keeps the URL stable across TTL rotations.

### 5.5 Access audit

Migration: `recognition_access_audit` (schema in Data Model section).

Middleware on the two crop endpoints: before returning the redirect, insert one row with `viewer_user_id`, `event_id`, `crop_kind`, `viewed_at`, `ip`, `user_agent`. Fire-and-forget via `BackgroundTasks` so the response is not blocked.

New admin portal page: `/audit/recognition-access` (admin-only) — read-only table of who viewed which crop when. This is what a school registrar consults when a parent asks "who has looked at my child's face in this system?".

### 5.6 Right-to-delete cascade

When a user deletes their `face_registrations` (existing flow at `backend/app/services/face_service.py`), cascade:

1. Delete all `recognition_events WHERE student_id = :user_id` (CASCADE already set via FK).
2. Delete the associated crop blobs from MinIO (FK CASCADE deletes DB rows but not blobs; a new hook in `face_service` fires the storage deletes).

### 5.7 Phase 5 verification

| # | Check | Expected |
|---|---|---|
| 1 | New event → crop lands in MinIO bucket, not on disk | MinIO console shows object; disk volume shrinks over time |
| 2 | `curl /api/v1/recognitions/<id>/live-crop` as admin | 302 to MinIO signed URL; JPEG resolves; audit row appears |
| 3 | Same call, same event, two different admins | Two audit rows, distinct `viewer_user_id` |
| 4 | TTL expires | Previously-fetched URL 403s; re-fetch via API returns a new one |
| 5 | Delete a student's `face_registrations` | `recognition_events` rows + all associated MinIO blobs disappear |
| 6 | MinIO encryption check | `mc admin config get local encryption` confirms at-rest encryption on |
| 7 | Faculty hits crop URL | 403 at API layer; no MinIO request made |

---

## Non-goals

- **Real-time broadcast to mobile clients.** Faculty + student APKs never see `recognition_event` messages. The panel is admin-portal-only — students and faculty have no legitimate reason to watch the ML feed.
- **Recognition-event search by face similarity.** Finding "all events similar to this face" is a FAISS-over-FAISS query and tempting, but out of scope. If the thesis needs it, add a Phase 6.
- **Manual re-labeling from the admin panel.** The panel is read-only: you cannot "mark this match as wrong" from the UI and feed it back into training. If we ever add adaptive re-enrollment adjustments, they go through the existing FAISS `add_adaptive` path, not a new UI.
- **Federated viewing across schools.** Scope stays single-tenant. The signed-URL + audit-log design is the right primitive if we ever go multi-tenant, but we do not build for that now.
- **VPS recognition events.** VPS has `ENABLE_ML=false`; no events are produced there. Any cross-campus rollup requires an on-prem → on-prem sync that is not in scope.
- **HTTPS for the on-prem MinIO.** Mac's LAN nginx terminates TLS already (if at all); MinIO stays HTTP on the internal Docker network. No external exposure.

## Rollback

Per-phase, newest-first:

```bash
# Rollback Phase 5 — cut back to filesystem storage
# 1. set RECOGNITION_EVIDENCE_BACKEND=filesystem
# 2. run scripts/migrate_crops_to_fs.py (mirror of 5.3 step 2)
# 3. ./scripts/onprem-down.sh && ./scripts/onprem-up.sh
# 4. drop recognition_access_audit table via downgrade migration

# Rollback Phase 4 — disable retention, remove route
# 1. set ENABLE_RECOGNITION_EVIDENCE_RETENTION=false
# 2. revert the /recognitions route + CSV endpoint (single git revert)

# Rollback Phase 3 — remove MatchEvidence from attendance sheet
# 1. git revert the AttendanceDetailSheet diff

# Rollback Phase 2 — disable live panel
# 1. git revert the RecognitionPanel mount in live.tsx
#    (WS messages continue firing, they're just ignored by the UI)

# Rollback Phase 1 — kill the whole feature
# 1. set ENABLE_RECOGNITION_EVIDENCE=false and redeploy
#    (pipeline intercept becomes a no-op; no migration needed)
# 2. if purging data: alembic downgrade -1; drop the crops volume
```

Each phase is a single logical PR; `git revert <sha>` is the primary rollback path. The migration drops are the only destructive steps and are optional.

## Thesis instrumentation (bonus — not a phase)

Once Phase 1 is running, the data unlocks three publishable charts. Query recipes go in [docs/plans/2026-04-22-recognition-evidence/THESIS-QUERIES.sql](THESIS-QUERIES.sql) (to be written during Phase 1 execution):

1. **Similarity distribution matched vs unmatched** — histograms overlaid on one plot. Justifies the threshold choice empirically.
2. **Face-size vs similarity scatter** — the bbox width (from `bbox` jsonb) on X, `similarity` on Y, coloured by `matched`. Directly supports the `buffalo_s → buffalo_l` escalation story from CLAUDE.md.
3. **Borderline-band analysis** — events with `similarity` in `[threshold - 0.1, threshold + 0.1]` bucketed by whether they were correct (cross-ref with labels from attendance ground truth). This is the confusion-matrix-adjacent chart that's actually publishable.

## Lessons

*(Populated during execution of each phase; appended to [memory/lessons.md](../../../memory/lessons.md) per [CLAUDE.md](../../../CLAUDE.md) convention.)*
