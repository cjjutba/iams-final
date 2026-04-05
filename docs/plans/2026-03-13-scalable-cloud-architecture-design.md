# Scalable Cloud Architecture Design — IAMS

**Date:** 2026-03-13
**Approach:** Optimized Monolith (Approach A)
**Status:** Approved

## Constraints

- 2 RPis, 2 cameras, 2 classrooms, 1 TP-Link router
- ~50 students per room, ~100 total concurrent faces
- $48/mo DigitalOcean droplet (4 vCPU / 8GB RAM, CPU only)
- Cloud-accessible (mobile app works remotely)
- Admin dashboard deferred — focus on reliable 2-room operation

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                   CLOUD (DigitalOcean $48/mo Droplet)                │
│                   4 vCPU / 8GB RAM / Ubuntu                         │
│                                                                     │
│  ┌──────────┐    ┌──────────────────────────────────────────────┐   │
│  │  nginx   │───>│  FastAPI (4 Uvicorn workers)                 │   │
│  │ :80/:443 │    │  ONNX Runtime + FAISS (mmap shared)          │   │
│  └──────────┘    │  Async Batch Face Processing Pipeline        │   │
│                  └──────────────────────┬───────────────────────┘   │
│                                         │                           │
│  ┌──────────┐  ┌──────────┐  ┌─────────┴──┐  ┌────────────┐       │
│  │ mediamtx │  │  coturn  │  │   Redis    │  │  certbot   │       │
│  │ :8554    │  │  :3478   │  │   :6379    │  │            │       │
│  └──────────┘  └──────────┘  └────────────┘  └────────────┘       │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    ▼             ▼              ▼
              RPi #1 (A)   RPi #2 (B)    Mobile Apps
                    │                       │
                    └──── TP-Link Router ───┘
                              │
                         Supabase (Auth + DB)
```

### Docker Compose Stack (6 services)

1. **iams-backend** — FastAPI, 4 Uvicorn workers, ONNX Runtime + FAISS
2. **redis** — Batch queue, pub/sub, presence state, distributed locks
3. **mediamtx** — RTSP ingest from RPis, WebRTC (WHEP) egress to mobile
4. **coturn** — TURN relay for WebRTC NAT traversal
5. **nginx** — Reverse proxy, TLS termination, WebSocket upgrade
6. **certbot** — Auto-renewing HTTPS certificates

## Section 1: Multi-Worker Backend

### Problem

Current: 1 Uvicorn worker because ML models + FAISS are loaded in-process.
Cannot utilize all 4 vCPUs. Sequential face processing.

### Solution

Run 4 Uvicorn workers with shared resources:

| Resource | Strategy | RAM Impact |
|----------|----------|------------|
| ONNX model weights | OS copy-on-read after fork() shares read-only pages | ~300MB shared |
| FAISS index | Memory-mapped file (IO_FLAG_MMAP) | ~2MB shared |
| Face queues | Redis lists | ~5MB |
| WebSocket broadcast | Redis pub/sub | Negligible |
| Batch lock | Redis distributed lock | Negligible |

### RAM Budget (8GB)

| Component | RAM |
|-----------|-----|
| Ubuntu OS + Docker | ~1 GB |
| ONNX Runtime (shared) | ~300 MB |
| FAISS index (mmap) | ~2 MB |
| 4 Uvicorn workers | ~400 MB x 4 = ~1.6 GB |
| Redis | ~50 MB |
| mediamtx + coturn + nginx | ~200 MB |
| **Total** | **~3.2 GB** |
| **Headroom** | **~4.8 GB free** |

## Section 2: Async Batch Face Processing Pipeline

### Problem

Current: synchronous 1-face-at-a-time processing. RPi waits for response.
50 faces = 50 sequential inference calls = ~25 seconds.

### Solution

Async fire-and-forget with batch processing:

1. RPi POSTs face crop → endpoint returns **202 Accepted** immediately
2. Face data pushed to **Redis queue** (per room: `face_queue:room_a`)
3. **Batch worker triggers** when:
   - Queue reaches 10+ faces (batch threshold), OR
   - 3 seconds elapsed since last batch (time threshold)
4. Worker acquires **Redis distributed lock** (only 1 worker processes per cycle)
5. **ONNX Runtime batch inference** — all faces in single forward pass
6. **FAISS batch search** — all embeddings in single query
7. Results → DB write + Redis pub/sub → WebSocket broadcast

### Performance (4 vCPU / 8GB, CPU)

| Step | 1 face | Batch of 50 |
|------|--------|-------------|
| ONNX ArcFace embedding | ~100-150ms | ~2-3s |
| FAISS search (1000 students) | ~0.5ms | ~25ms |
| DB write + WebSocket notify | ~10ms | ~200ms |
| **Total** | **~150ms** | **~3-4s** |

## Section 3: RPi Smart Sampler

### Problem

Sending every detected face every 3 seconds floods the backend with redundant data
(50 unchanged faces x every 3 seconds = 17 faces/sec).

### Solution — Smart Sampler

New component between MediaPipe detector and sender:

| Rule | What it does |
|------|-------------|
| Face tracking | IoU-based track IDs for detected faces |
| Dedup window | Skip face if same track ID sent in last 5 seconds |
| Best frame | Pick highest confidence + least blur within window |
| New face = immediate | New track ID → send immediately (fast first-recognition) |
| Face gone = notify | Track ID gone for 10+ seconds → send face_left event |

### Effect

| Scenario | Without | With Smart Sampler |
|----------|---------|-------------------|
| 50 students sitting (stable) | 17 faces/sec | 2-3 faces/sec |
| 5 students enter | 55 sent | 5 sent immediately |
| Student leaves | Detected at next 60s scan | face_left within 10 seconds |

### Edge Code Changes

- `detector.py` — add IoU-based face tracking
- `processor.py` — best-frame selection
- `sender.py` — fire-and-forget (202), add face_left events
- `config.py` — SEND_INTERVAL=3, DEDUP_WINDOW=5, FACE_GONE_TIMEOUT=10
- `queue_manager.py` — no changes

## Section 4: Event-Driven Presence Tracking

### Problem

Current: single APScheduler job every 60s, timer-based.
Early leave takes 3 minutes to detect. Sequential room processing.

### Solution — Hybrid event-driven + confirmation

**On every batch result (real-time):**
- Update `last_seen` timestamp per student in Redis
- Reset miss counter
- Push `student_checked_in` via WebSocket

**Every 60 seconds (confirmation check):**
- For each enrolled student: if `last_seen > 60s ago` AND RPi reports `face_gone` → increment miss counter
- If miss_counter >= 3 → trigger early_leave_event, WebSocket alert
- Calculate running presence_score = (present_scans / total_scans) x 100%
- Bulk write presence_logs to Supabase

**State in Redis (fast, shared across workers):**
```
presence:{room}:{student_id} = {
  last_seen: timestamp,
  miss_count: 0,
  present_count: 42,
  total_scans: 45
}
```

### Timing Improvement

| Metric | Current | New |
|--------|---------|-----|
| Walk-in to recognition | ~60 seconds | ~3-4 seconds |
| Walk-in to phone notification | ~60-120 seconds | ~3-4 seconds |
| Early leave detection | ~4-5 minutes | ~3-4 minutes |
| Early leave awareness | None until alert | Warning at miss count 1 (~1 min) |

## Section 5: WebSocket Across Workers

### Problem

Current: single-worker in-memory WebSocket manager.
4 workers = clients split across workers, messages don't reach everyone.

### Solution — Redis pub/sub bridge

- Each worker runs its own WebSocket connection manager
- When batch worker produces results → PUBLISH to Redis channel `ws_broadcast`
- All 4 workers subscribe → each pushes to its own connected clients
- Full coverage regardless of which worker a client connected to

### Event Types

| Event | Recipient | When |
|-------|-----------|------|
| `attendance_update` | Faculty (room) | Every batch cycle |
| `student_checked_in` | Specific student | First recognition |
| `presence_warning` | Faculty | Miss count = 1 |
| `early_leave_alert` | Faculty + Student | Miss count = 3 |
| `presence_score` | Student | Every 60s |
| `session_started` | All enrolled | Schedule begins |
| `session_ended` | All enrolled | Schedule ends |

## Section 6: Network Topology

### Physical Setup

- RPi #1 (192.168.0.10) → Classroom A
- RPi #2 (192.168.0.11) → Classroom B
- Both on TP-Link WiFi (5GHz preferred)
- Uplink via school ISP to DigitalOcean VPS

### Bandwidth (per RPi)

| Data | Bandwidth |
|------|-----------|
| Face crops (smart sampled) | ~50-80 KB/s |
| RTSP stream relay | ~63 KB/s |
| **Total per RPi** | **~130 KB/s** |
| **Both RPis combined** | **~260 KB/s** |

### TP-Link Configuration

- DHCP reservations for RPi static IPs
- 5GHz band preferred
- QoS: prioritize RPi MAC addresses (optional)
- No port forwarding needed (RPis initiate outbound only)

### RPi .env

```bash
# RPi #1
ROOM_ID=room_a
BACKEND_URL=https://167.71.217.44
RTSP_RELAY_URL=rtsp://167.71.217.44:8554/room_a
SCAN_INTERVAL=3
SEND_INTERVAL=3

# RPi #2
ROOM_ID=room_b
BACKEND_URL=https://167.71.217.44
RTSP_RELAY_URL=rtsp://167.71.217.44:8554/room_b
SCAN_INTERVAL=3
SEND_INTERVAL=3
```

### Failure Recovery

| Failure | Impact | Recovery |
|---------|--------|----------|
| WiFi drops | Faces queue locally (500 max, 5min TTL) | Auto-reconnect, flush queue |
| ISP down | Both RPis queue, stream pauses | Queue flushes when ISP returns |
| VPS down | RPis get connection refused | Retry every 10s, auto-resume |
| RPi crash | Only that room affected | systemd auto-restarts service |
| Router restart | Brief ~30s interruption | DHCP reassigns, connections resume |
| Camera disconnect | RPi logs error | Auto-reconnects when camera back |

## Section 7: Registration-Recognition Pipeline Alignment

### Problem

If registration (mobile selfie) and recognition (CCTV) use different preprocessing
or models, embeddings live in different vector spaces and matching fails.

### Solution — Single shared pipeline

Both paths use the exact same:
1. **Detection:** InsightFace SCRFD (same model)
2. **Alignment:** 5-point landmark warp (normalizes pose)
3. **Preprocessing:** CLAHE + resize 112x112 + RGB normalize [-1,1]
4. **Embedding:** ArcFace ONNX (same weights) → 512-dim L2-normalized
5. **Registration:** average 3-5 embeddings → FAISS store
6. **Recognition:** single embedding → FAISS search

### Registration Captures (Mobile)

1. Front-facing, eyes forward
2. Slight left turn (~15 degrees)
3. Slight right turn (~15 degrees)
4. Slight up tilt (~10 degrees) — simulates CCTV ceiling angle
5. Slight down tilt (~10 degrees) — simulates looking at desk

### Quality Gates (same thresholds for both paths)

- Face detection confidence >= 0.5
- Face size >= 5% of image area
- Blur score (Laplacian variance) >= 35
- Brightness between 40-220
- Anti-spoof: LBP texture + FFT frequency

### Cross-Capture Validation (registration only)

- All 3-5 embeddings must have cosine similarity > 0.7 with each other
- Embedding variance below threshold
- Average embedding L2-normalized before FAISS store

### Code Change

Extract preprocessing + embedding into single shared function `embed_face()` used by
both registration and recognition paths. Registration endpoint sends images to backend
for embedding — same ONNX model processes everything.

## Section 8: End-to-End Timeline

Student walks into Classroom A → faculty gets notification:

```
0.0s   Student walks in
0.1s   Camera captures frame                    (RPi, local)
0.13s  MediaPipe detects new face               (RPi, local)
0.15s  Smart Sampler: new track, immediate send  (RPi, local)
0.3s   POST face to backend                      (RPi → VPS)
0.4s   202 Accepted, face queued in Redis        (VPS)
3.0s   Batch timer fires, worker acquires lock   (VPS)
3.5s   ONNX batch embed + FAISS search           (VPS)
3.6s   Student identified → DB + Redis publish   (VPS)
3.7s   WebSocket push to faculty + student       (VPS → phones)

TOTAL: ~3.7 seconds from walk-in to notification
```

## Summary of All Changes

### Backend
- InsightFace PyTorch → ONNX Runtime
- Add Redis (queue, pub/sub, distributed lock, presence state)
- Async 202 face endpoint + batch worker
- Event-driven presence tracking + 60s confirmation
- 4 Uvicorn workers with shared FAISS (mmap) and ONNX
- Shared `embed_face()` function for registration + recognition
- WebSocket broadcast via Redis pub/sub

### Edge (RPi)
- Add Smart Sampler (IoU tracking, dedup, best-frame, face_gone)
- Fire-and-forget sender (202 response)
- Reduce send interval from 60s to 3-5s

### Mobile
- New WebSocket event handlers (presence_warning, presence_score)
- Remove polling, rely on WebSocket push
- Add up/down tilt guidance to face registration capture UI

### Infrastructure
- Add Redis to docker-compose.prod.yml
- Update nginx for WebSocket routing across workers
- Configure Uvicorn workers=4
- Update deploy.sh
