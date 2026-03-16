# IAMS Enterprise Architecture Rebuild — Design Document

**Date:** 2026-03-16
**Status:** Approved
**Scope:** Complete system rebuild — enterprise-grade, production-ready

---

## 1. Overview

Rebuild IAMS as an enterprise-grade intelligent attendance monitoring system following industry patterns used by Hikvision, Genetec, and Milestone. The system uses a three-tier architecture (Edge → Cloud → Application) with containerized modular design, event-driven processing via Redis Streams, and real-time WebRTC streaming.

### Deployment Target

- 2 classrooms, 1 Reolink P340 camera per classroom
- 1 RPi 4 per classroom (4GB + 2GB) as lightweight camera gateway
- 1 DigitalOcean VPS (8GB / 4 vCPU, CPU-only)
- Cloud-based architecture (Supabase PostgreSQL)
- Thesis demo — must be polished, smooth, impressive

### Design Goals

1. Buttery-smooth real-time video with instant face recognition
2. Handle 50+ faces simultaneously
3. Real-time attendance dashboards, live counters, charts, alerts
4. End-to-end automation (zero human intervention)
5. Enterprise architecture patterns (event-driven, containerized, health-monitored)

---

## 2. System Architecture

### Three-Tier Design (Enterprise Standard)

```
╔═══════════════════════════════════════════════════════════════╗
║              EDGE TIER — RPi as Camera Gateway                ║
║              (Ultra-lightweight, zero ML)                     ║
║                                                               ║
║   Reolink P340 (12MP, H.265, RTSP, 93° FOV)                  ║
║   Mounted at front of classroom, above whiteboard,            ║
║   angled down toward students                                 ║
║       │                                                       ║
║       ├── Sub Stream (720p, H.264, 15fps)                     ║
║       │       └──→ RPi: FFmpeg -c copy ──→ RTSP push to VPS  ║
║       │            (remux only, ~3% CPU)     (live viewing)   ║
║       │                                                       ║
║       └── Main Stream (12MP, H.265, 20fps)                    ║
║               └──→ RPi: Sample 2-3 FPS → JPEG encode         ║
║                    (decode + compress, ~15% CPU)              ║
║                    └──→ WebSocket to VPS (detection frames)   ║
║                                                               ║
║   RPi Total: ~20% CPU, ~280MB RAM, ~4-5 Mbps upload          ║
╚═══════════════════════════════════════════════════════════════╝
                    │ RTSP              │ WebSocket
                    │ (sub-stream)      │ (JPEG snapshots)
                    │ ~2 Mbps           │ ~2-3 Mbps
                    ▼                   ▼
╔═══════════════════════════════════════════════════════════════╗
║         CLOUD TIER — Single VPS, Multi-Container              ║
║         DigitalOcean 8GB / 4 vCPU                             ║
║                                                               ║
║  Docker Compose (7 containers)                                ║
║  ┌─────────────────────────────────────────────────────────┐  ║
║  │                                                         │  ║
║  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │  ║
║  │  │ API Gateway  │  │ Detection    │  │ Recognition  │  │  ║
║  │  │              │  │ Worker       │  │ Worker       │  │  ║
║  │  │ FastAPI      │  │              │  │              │  │  ║
║  │  │ WebSocket    │  │ SCRFD (ONNX) │  │ ArcFace      │  │  ║
║  │  │ Presence Eng │  │ Track assign │  │ FAISS search │  │  ║
║  │  │ Alert Engine │  │              │  │              │  │  ║
║  │  │ Session Mgr  │  │              │  │              │  │  ║
║  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │  ║
║  │         │                 │                 │           │  ║
║  │         └────────────┬────┴─────────────────┘           │  ║
║  │                      ▼                                  │  ║
║  │              ┌──────────────┐                           │  ║
║  │              │  Redis 7     │  Event Bus (localhost)     │  ║
║  │              │  Streams     │  Zero network latency     │  ║
║  │              │  Cache       │                           │  ║
║  │              └──────────────┘                           │  ║
║  │                                                         │  ║
║  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │  ║
║  │  │ mediamtx │ │ nginx    │ │ coturn   │ │ Dozzle   │   │  ║
║  │  │ RTSP→    │ │ SSL/TLS  │ │ TURN/    │ │ Log      │   │  ║
║  │  │ WebRTC   │ │ proxy    │ │ STUN     │ │ viewer   │   │  ║
║  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘   │  ║
║  └─────────────────────────────────────────────────────────┘  ║
║                                                               ║
║  External: Supabase (PostgreSQL + Auth)                       ║
╚═══════════════════════════════════════════════════════════════╝
                    │ WebRTC             │ WebSocket (WSS)
                    │ (live video)       │ (data + events)
                    ▼                    ▼
╔═══════════════════════════════════════════════════════════════╗
║              APPLICATION TIER — Mobile Apps                   ║
║                                                               ║
║  ┌─────────────────────────┐  ┌─────────────────────────┐    ║
║  │ Faculty App             │  │ Student App             │    ║
║  │                         │  │                         │    ║
║  │ • WebRTC live feed      │  │ • Live attendance       │    ║
║  │ • 60 FPS bbox overlay   │  │   status                │    ║
║  │ • Identity labels       │  │ • Presence score        │    ║
║  │ • Live attendance list  │  │ • Early-leave alerts    │    ║
║  │ • Real-time counters    │  │ • Schedule + calendar   │    ║
║  │ • Charts + heatmaps    │  │ • Attendance history    │    ║
║  │ • Early-leave alerts    │  │ • Face re-registration  │    ║
║  │ • Analytics dashboard   │  │                         │    ║
║  └─────────────────────────┘  └─────────────────────────┘    ║
╚═══════════════════════════════════════════════════════════════╝
```

### Why Multi-Container Monolith (Not Distributed Microservices)

Enterprise surveillance systems at 2-16 camera scale use single-appliance or modular-monolith architectures (Hikvision DeepinMind NVR, Genetec Security Center, Avigilon AI NVR). Distributed microservices add network latency and failure modes without scaling benefit at this scale.

Our containers communicate exclusively via Redis Streams — if we ever need to scale to 50+ cameras, each container can be extracted to its own server with zero code changes.

**Fault isolation is preserved:**
- detection-worker crashes → API still serves cached tracks, worker auto-restarts
- recognition-worker crashes → detection still tracks faces (unnamed), worker auto-restarts
- api-gateway crashes → workers keep processing, API auto-restarts
- All containers: `restart: unless-stopped`

---

## 3. Edge Tier — RPi Camera Gateway

### Role

The RPi is a **network bridge with a frame sampler**. Zero ML, zero AI. It connects the Reolink camera (classroom LAN) to the cloud VPS (internet).

### Dual-Stream Pattern (Enterprise Standard)

This is the same pattern Hikvision and Genetec use — two streams, two purposes:

| Stream | Resolution | Codec | FPS | Purpose | Bandwidth |
|--------|-----------|-------|-----|---------|-----------|
| Sub-stream | 720p | H.264 | 15 | Live viewing (WebRTC) | ~2 Mbps |
| Main stream | 12MP (4512×2512) | H.265 | 2-3 (sampled) | Face detection frames | ~2-3 Mbps |

### RPi Processing

| Task | CPU | RAM | Description |
|------|-----|-----|-------------|
| FFmpeg sub-stream relay | ~3% | 30MB | `-c copy` remux, no transcode |
| Main-stream decode (2-3 FPS) | ~10% | 100MB | H.265 HW decoder on RPi 4 |
| JPEG encode + WS send | ~5% | 50MB | Quality 85, ~300-500KB per frame |
| Python runtime + reconnect | ~2% | 100MB | Auto-reconnect, health heartbeat |
| **Total** | **~20%** | **~280MB** | Works on both 4GB and 2GB RPi |

### Camera Configuration (Reolink P340)

```
RTSP Main: rtsp://admin:<password>@<camera_ip>:554/h264Preview_01_main
RTSP Sub:  rtsp://admin:<password>@<camera_ip>:554/h264Preview_01_sub

Settings to configure:
- Enable RTSP port (disabled by default)
- Enable ONVIF (optional, for discovery)
- Main stream: 12MP, H.265, 20fps
- Sub stream: 720p, H.264, 15fps
```

### Face Pixel Budget (Camera at Front, Looking Down)

| Row | Distance | Face pixels (12MP) | Recognition quality |
|-----|----------|-------------------|-------------------|
| Front row | ~1.5-2m | 160+ px | Excellent |
| Middle | ~3-4m | 80-107 px | Good |
| Back row | ~5-6m | 53-64 px | Workable (SCRFD detects down to 20px) |

### RPi Data Output

**WebSocket message to VPS (2-3 FPS):**
```json
{
  "type": "frame",
  "room_id": "room-uuid",
  "timestamp": "2026-03-16T10:30:00.123Z",
  "frame_b64": "/9j/4AAQ...",
  "frame_width": 4512,
  "frame_height": 2512,
  "source": "reolink_p340"
}
```

**Health heartbeat (every 10s):**
```json
{
  "type": "heartbeat",
  "room_id": "room-uuid",
  "camera_status": "connected",
  "cpu_percent": 18,
  "ram_percent": 14,
  "uptime_seconds": 3600
}
```

### Offline Handling

- `collections.deque(maxlen=100)` — buffers frames during VPS disconnection
- 2-minute TTL per frame (stale frames are useless for attendance)
- Exponential backoff reconnection (1s → 2s → 4s → max 30s)
- Health heartbeat stops → VPS marks RPi as "disconnected"

---

## 4. Video Streaming Pipeline

### Protocol Stack

| Protocol | Path | Latency | Purpose |
|----------|------|---------|---------|
| RTSP/RTP | Reolink → RPi (LAN) | <10ms | Camera to gateway |
| RTSP | RPi → VPS mediamtx (internet) | 50-200ms | Stream relay |
| WebRTC (WHEP) | mediamtx → Mobile app | 100-300ms | Live viewing |
| **Total** | Camera → Faculty phone | **<500ms** | End-to-end |

### mediamtx Configuration

```yaml
logLevel: warn
api: yes                    # REST API on :9997
rtsp: yes                   # Ingest on :8554
webrtc: yes                 # WHEP on :8889
webrtcICEHostNAT1To1IPs:
  - <VPS_PUBLIC_IP>         # Required for NAT traversal

paths:
  room1:
    overridePublisher: yes  # Accept RPi reconnection
  room2:
    overridePublisher: yes
```

### Stream Architecture

```
Reolink P340 (Classroom 1 LAN)
    │
    └── Sub Stream (720p H.264)
            │
            └──→ RPi 1 ──FFmpeg -c copy──→ VPS mediamtx path: /room1
                                                │
                                                ├──→ WebRTC (WHEP) → Faculty App
                                                │    (live video, <500ms latency)
                                                │
                                                └──→ (Available for VPS to pull
                                                      frames if needed as fallback)

Reolink P340 (Classroom 2 LAN)
    │
    └── Sub Stream (720p H.264)
            │
            └──→ RPi 2 ──FFmpeg -c copy──→ VPS mediamtx path: /room2
                                                │
                                                └──→ WebRTC (WHEP) → Faculty App
```

### NAT Traversal

coturn TURN server handles mobile clients behind NAT/cellular:
- STUN: free, works for most WiFi connections
- TURN: relay fallback for strict NAT (cellular networks)
- Configuration: shared secret auth, realm = VPS domain

---

## 5. Face Detection & Recognition Pipeline

### Pipeline Architecture (Event-Driven)

```
RPi sends 12MP JPEG snapshots (2-3 FPS per room)
    │
    ▼
┌──────────────────────────────────────────┐
│  API Gateway — Ingestion Layer           │
│  • Receive JPEG via WebSocket            │
│  • Validate frame (size, format, room)   │
│  • Publish to Redis stream:frames:{room} │
└──────────────────┬───────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────┐
│  Detection Worker Container              │
│                                          │
│  Consumes: stream:frames:{room}          │
│                                          │
│  1. Decode JPEG (12MP)                   │
│  2. Downscale to 1080p for detection     │
│  3. SCRFD face detection (ONNX)          │
│     • Detects faces down to 20px         │
│     • Returns bboxes + landmarks         │
│  4. Map bboxes back to 12MP coordinates  │
│  5. Crop faces from ORIGINAL 12MP frame  │
│     • Result: 53-160px face crops        │
│  6. Track assignment (IoU + centroid)    │
│     • Assign stable track IDs            │
│     • Determine: new or existing track?  │
│                                          │
│  Publishes:                              │
│  • stream:detections:{room} (all tracks) │
│  • stream:recognition_req (new tracks)   │
└──────────────────┬───────────────────────┘
                   │
          ┌────────┴────────┐
          ▼                 ▼
┌─────────────────┐  ┌──────────────────────────────────┐
│  Track Fusion   │  │  Recognition Worker Container     │
│  Engine         │  │                                   │
│  (in API GW)    │  │  Consumes: stream:recognition_req │
│                 │  │                                   │
│  • Kalman       │  │  1. Quality gate check            │
│    filter       │  │     • Blur (Laplacian > 100)      │
│  • 30 FPS       │  │     • Brightness (40-220)         │
│    output       │  │     • Face size (> 5% of frame)   │
│  • Smooth       │  │  2. ArcFace embedding (ONNX)      │
│    bbox motion  │  │     • 512-dim, L2-normalized      │
│                 │  │     • ~20-30ms per face on CPU     │
│                 │  │  3. FAISS IndexFlatIP search       │
│                 │  │     • top-3 nearest neighbors      │
│                 │  │     • ~1ms for 100 faces           │
│                 │  │  4. Threshold: cosine > 0.45       │
│                 │  │     • With 0.10 margin             │
│                 │  │                                   │
│                 │  │  Publishes:                       │
│                 │  │  • stream:recognitions            │
│                 │  │    {track_id, user_id, name,      │
│                 │  │     student_id, similarity}       │
└────────┬────────┘  └──────────────────────────────────┘
         │
         ▼
  WebSocket Broadcaster → Mobile Apps
```

### Performance Characteristics

**Cold start (50 students enter, all unrecognized):**

| Phase | Time | Action |
|-------|------|--------|
| 0-1s | Frame received | RPi sends 12MP JPEG to VPS |
| 1-1.5s | Detection | SCRFD finds 50 faces (~100ms on CPU at 1080p) |
| 1.5-3s | Recognition | ArcFace embeds 50 crops (batch, ~30ms each = 1.5s) |
| 3-3.1s | Matching | FAISS searches 50 embeddings (~1ms total) |
| 3.1-3.5s | Delivery | Redis → Track Fusion → WebSocket → Mobile |
| **Total** | **~3-4s** | **All 50 faces identified** |

**Steady state (everyone seated, tracked):**

| Metric | Value |
|--------|-------|
| Recognition calls | 0 (all tracked) |
| CPU load (detection worker) | ~10% (SCRFD on 2 rooms × 3 FPS) |
| CPU load (recognition worker) | ~0% (idle, waiting for new tracks) |
| New face recognized | <2 seconds |
| Track coast duration | 500ms (survives brief occlusions) |

### Models & Runtime

| Component | Model | Runtime | Input | Output |
|-----------|-------|---------|-------|--------|
| Face Detection | SCRFD (InsightFace buffalo_l) | ONNX Runtime CPU | 640×640 (downscaled) | bboxes + landmarks |
| Face Recognition | ArcFace (InsightFace buffalo_l) | ONNX Runtime CPU | 112×112 (aligned) | 512-dim embedding |
| Vector Search | FAISS IndexFlatIP | faiss-cpu | 512-dim vector | cosine similarity scores |

### ONNX CPU Optimization

```python
# Thread tuning for multi-worker deployment
ORT_INTRA_OP_NUM_THREADS=2   # Threads within single inference
ORT_INTER_OP_NUM_THREADS=1   # Parallel inference operations
```

---

## 6. Track Fusion Engine

### Purpose

Merge fast detections (2-3 FPS from SCRFD) into smooth 30 FPS output for mobile display. Fill gaps between detection frames with Kalman prediction.

### Kalman Filter State

- **State vector (8-dim):** `[cx, cy, w, h, vx, vy, vw, vh]`
- **Process noise (Q):** Low velocity noise (1.0) — students are mostly seated
- **Measurement noise (R):** Trust SCRFD detections closely (4.0)
- **Measurement matrix (H):** Observes `[cx, cy, w, h]` from 8-dim state

### Track Lifecycle

```
Detection received
    │
    ▼
No existing track matches (IoU < 0.3)?
    │                    │
    YES                  NO (matched)
    │                    │
    ▼                    ▼
Create TENTATIVE     Update CONFIRMED track
track                Kalman update step
    │
    ▼ (3 consecutive detections)
Promote to CONFIRMED
    │
    ▼ (track not detected for 500ms)
Mark as LOST
    │
    ▼ (lost for 2 seconds)
DELETE track
```

### Output (30 FPS to WebSocket)

```json
{
  "type": "fused_tracks",
  "room_id": "room-uuid",
  "ts": 1710580200123,
  "tracks": [
    {
      "id": 1,
      "bbox": [0.12, 0.08, 0.22, 0.31],
      "conf": 0.95,
      "state": "confirmed",
      "identity": {
        "user_id": "uuid",
        "name": "Juan Dela Cruz",
        "student_id": "2023-0001",
        "similarity": 0.87
      }
    }
  ]
}
```

Bounding boxes are **normalized (0-1)** so the mobile app can scale to any screen size.

---

## 7. Redis Streams — Event Bus

### Stream Definitions

| Stream | Producer | Consumer(s) | Rate | MAXLEN |
|--------|----------|-------------|------|--------|
| `stream:frames:{room_id}` | API Gateway (ingestion) | Detection Worker | 2-3 msg/s per room | 10 |
| `stream:detections:{room_id}` | Detection Worker | Track Fusion (API GW), Presence Engine | 2-3 msg/s per room | 30 |
| `stream:recognition_req` | Detection Worker (new tracks) | Recognition Worker | 0-50 burst, then ~0 | 100 |
| `stream:recognitions` | Recognition Worker | Track Fusion (API GW) | Event-driven | 100 |
| `stream:attendance:{schedule_id}` | Presence Engine | WebSocket Broadcaster, DB Writer | 1 msg/60s per student | 1000 |
| `stream:alerts` | Alert Engine | WebSocket Broadcaster, Notification Service | Event-driven | 500 |
| `stream:metrics` | All workers | Health Monitor | 1 msg/10s per worker | 100 |

### Consumer Groups

Each worker uses Redis consumer groups for reliable message processing:

```python
# Detection Worker joins consumer group
XREADGROUP GROUP detection-workers worker-1 COUNT 1 BLOCK 5000 STREAMS stream:frames:room1 >

# Acknowledge after processing
XACK stream:frames:room1 detection-workers <message_id>
```

**Benefits:**
- Messages survive worker crashes (unacked messages get redelivered)
- Multiple workers can share load (horizontal scaling ready)
- Message replay for debugging (XRANGE)
- Auto-trimming prevents unbounded memory growth (MAXLEN)

### Why Redis Streams (Not Kafka)

| Aspect | Redis Streams | Kafka |
|--------|--------------|-------|
| Latency | Sub-millisecond | ~5ms |
| Ops complexity | Zero (already in stack) | ZooKeeper + brokers |
| RAM for 2 cameras | ~10MB | ~500MB minimum |
| Setup time | 0 (redis:7-alpine) | Hours |
| Throughput needed | ~10 msg/s | Designed for millions/s |
| Consumer groups | Yes | Yes |
| Message replay | Yes (XRANGE) | Yes |

Same patterns, 1/50th the complexity. Correct choice at this scale.

---

## 8. Presence Engine & Attendance Automation

### Automated Session Lifecycle

```
Schedule table says: "Math 101, Room 1, Mon 10:00-11:00"
    │
    ▼
Auto-Session Manager (checks every 60s via APScheduler)
    │
    ├── 09:55 → Pre-warm: verify RPi connected, FAISS loaded
    │
    ├── 10:00 → START SESSION
    │            • Mark all enrolled students as "pending"
    │            • Begin presence scan cycle (every 60s)
    │            • Notify faculty app: "Session Active"
    │
    ├── 10:01 → First scan
    │            • Query track fusion for identified faces in room
    │            • Students detected → mark "present"
    │            • Publish to stream:attendance
    │            → Faculty dashboard updates: "45/50 present"
    │            → Student apps update: "You're marked present"
    │
    ├── 10:15 → Grace period ends
    │            • Students arriving now → mark "late"
    │            • Still absent → mark "absent"
    │            → Faculty notified: "5 students absent"
    │
    ├── 10:30 → Student leaves (face disappears from tracking)
    │            • Miss count: 1 (10:30), 2 (10:31), 3 (10:32)
    │            • 3rd consecutive miss → EARLY LEAVE ALERT
    │            → Alert published to stream:alerts
    │            → Faculty app: popup with name + severity
    │            → Student app: "You've been flagged"
    │            → DB: early_leave_event record
    │
    ├── 11:00 → END SESSION (auto)
    │            • Finalize all attendance records
    │            • Calculate presence scores: (present_scans / total_scans) × 100%
    │            • Generate summary
    │            → Faculty dashboard: session complete view
    │
    └── Done. Zero human intervention throughout.
```

### Presence Scan Logic

```
Every 60 seconds:
    │
    ├── Get all enrolled students for active session
    ├── Get current identified tracks from Track Fusion
    │
    ├── For each enrolled student:
    │   ├── Found in tracks? → status = "detected", reset miss_count
    │   └── Not found?      → miss_count += 1
    │       ├── miss_count < 3  → still "present" (brief occlusion tolerance)
    │       └── miss_count >= 3 → trigger early-leave alert
    │
    ├── Log presence_log record (per student, per scan)
    ├── Update attendance_record (running status)
    └── Broadcast attendance summary via WebSocket
```

### Early-Leave Severity

| Condition | Severity | Example |
|-----------|----------|---------|
| Left after 75% of class elapsed | Low | Left at 10:50 of a 10:00-11:00 class |
| Left between 50-75% elapsed | Medium | Left at 10:35 |
| Left before 50% elapsed | High | Left at 10:20 |

---

## 9. WebSocket Layer — Real-Time Delivery

### Endpoints

| Endpoint | Data | Rate | Consumers |
|----------|------|------|-----------|
| `WSS /api/v1/ws/stream/{schedule_id}` | Fused tracks (bbox + identity) | 30 FPS | Faculty live feed overlay |
| `WSS /api/v1/ws/attendance/{schedule_id}` | Attendance state changes | Event-driven | Faculty + Student dashboards |
| `WSS /api/v1/ws/alerts/{user_id}` | Early-leave alerts, notifications | Event-driven | Faculty + Student apps |
| `WSS /api/v1/ws/health` | System health metrics | Every 10s | Admin monitoring |

### Message Protocols

**Fused tracks (30 FPS):**
```json
{
  "type": "fused_tracks",
  "room_id": "uuid",
  "ts": 1710580200123,
  "tracks": [
    {
      "id": 1,
      "bbox": [0.12, 0.08, 0.22, 0.31],
      "conf": 0.95,
      "identity": {
        "user_id": "uuid",
        "name": "Juan Dela Cruz",
        "student_id": "2023-0001",
        "similarity": 0.87,
        "state": "confirmed"
      }
    }
  ]
}
```

**Attendance update (event-driven):**
```json
{
  "type": "attendance_update",
  "schedule_id": "uuid",
  "student": {
    "user_id": "uuid",
    "name": "Juan Dela Cruz",
    "student_id": "2023-0001",
    "status": "present",
    "presence_score": 95.5,
    "checked_in_at": "2026-03-16T10:01:00Z"
  },
  "summary": {
    "total_enrolled": 50,
    "present": 45,
    "late": 3,
    "absent": 2,
    "early_leave": 0
  }
}
```

**Early-leave alert:**
```json
{
  "type": "alert",
  "severity": "high",
  "alert_type": "early_leave",
  "student": {
    "user_id": "uuid",
    "name": "Maria Santos",
    "student_id": "2023-0042"
  },
  "message": "Left class at 10:20 AM (33% of class elapsed)",
  "schedule": {
    "subject": "Math 101",
    "room": "Room 201"
  },
  "timestamp": "2026-03-16T10:20:00Z"
}
```

---

## 10. Database Schema

### Core Tables (10 tables, streamlined)

| Table | Purpose | Key Fields |
|-------|---------|------------|
| `users` | All users | email, role (student/faculty/admin), is_active, student_id |
| `face_registrations` | User → FAISS mapping | user_id, faiss_id, status, registered_at |
| `face_embeddings` | Full 512-dim vectors | registration_id, embedding (array), quality_metadata |
| `rooms` | Classrooms | name, camera_rtsp_url, camera_sub_url |
| `schedules` | Class schedules | subject, faculty_id, room_id, day_of_week, start_time, end_time |
| `enrollments` | Student ↔ Schedule | student_id, schedule_id |
| `attendance_records` | Per-session records | student_id, schedule_id, status, presence_score, check_in_at |
| `presence_logs` | 60-second snapshots | student_id, schedule_id, scan_number, detected (bool), bbox |
| `early_leave_events` | Early-leave alerts | student_id, schedule_id, severity, left_at, class_elapsed_pct |
| `audit_logs` | System audit trail | action, actor_id, target, metadata, timestamp |

### Key Relationships

```
users 1──∞ enrollments ∞──1 schedules ∞──1 rooms
users 1──1 face_registrations 1──∞ face_embeddings
users 1──∞ attendance_records ∞──1 schedules
users 1──∞ presence_logs ∞──1 schedules
users 1──∞ early_leave_events ∞──1 schedules
```

---

## 11. Mobile App Architecture

### Tech Stack

| Aspect | Choice | Why |
|--------|--------|-----|
| Framework | React Native (Expo) | Cross-platform, fast development |
| State Management | Zustand | Lightweight, no boilerplate |
| HTTP Client | Axios + interceptors | Auto token refresh, error handling |
| WebSocket | Native WebSocket + custom hooks | Direct, no library overhead |
| Video Player | react-native-webrtc | WebRTC WHEP for live CCTV |
| Animations | react-native-reanimated 3 | 60 FPS UI thread animations |
| Charts | Victory Native | Live attendance charts |
| Design System | Monochrome UA-inspired | Clean, professional |

### Faculty App Screens

| Screen | Features | Data Source |
|--------|----------|-------------|
| **Live Feed** | WebRTC video + 60 FPS bbox overlay + names | WS /ws/stream/{id} |
| **Live Attendance** | Real-time student list, live counter, status badges | WS /ws/attendance/{id} |
| **Dashboard** | Attendance rate charts, presence heatmaps, trends | REST API + WS |
| **Alerts** | Live early-leave notifications with severity | WS /ws/alerts/{id} |
| **Schedule** | Class list, session status (active/upcoming/done) | REST API |
| **Class Detail** | Per-student history, presence scores | REST API |
| **Analytics** | Weekly/monthly trends | REST API |

### Student App Screens

| Screen | Features | Data Source |
|--------|----------|-------------|
| **Home** | Today's schedule, current status, presence score | REST API + WS |
| **Attendance** | Full history with calendar view | REST API |
| **Alerts** | Personal early-leave notifications | WS /ws/alerts/{id} |
| **Profile** | Face re-registration, settings | REST API |

### Mobile Rendering Pipeline (60 FPS Bounding Boxes)

```
WebSocket receives fused_tracks (30 FPS)
    │
    ▼
useDetectionWebSocket hook
    │ Parse JSON, update Zustand store
    ▼
FusedDetectionOverlay component
    │
    ├── For each track:
    │   ├── withSpring() animation (60 FPS interpolation)
    │   ├── bbox position + size animated
    │   ├── Border color: green (confirmed) / yellow (tentative)
    │   ├── Name label with similarity badge
    │   └── Fade-out animation when track lost
    │
    └── Rendered on top of WebRTC video player
```

---

## 12. Monitoring & Health Checks

### Health Endpoint

`GET /api/v1/health` — deep check of all components:

```json
{
  "status": "healthy",
  "uptime_seconds": 86400,
  "version": "2.0.0",
  "components": {
    "database": { "status": "up", "latency_ms": 12 },
    "redis": { "status": "up", "latency_ms": 1, "streams_active": 6 },
    "faiss": { "status": "up", "vectors": 50, "index_size_kb": 100 },
    "mediamtx": { "status": "up", "active_paths": 2 },
    "detection_worker": { "status": "up", "frames_processed_last_min": 360 },
    "recognition_worker": { "status": "up", "recognitions_last_min": 3 },
    "edge_devices": {
      "room-1": { "status": "connected", "last_heartbeat": "2s ago", "fps": 3 },
      "room-2": { "status": "connected", "last_heartbeat": "1s ago", "fps": 2 }
    }
  },
  "pipeline": {
    "detection_fps": 6,
    "avg_detection_ms": 95,
    "avg_recognition_ms": 28,
    "active_sessions": 2,
    "tracked_faces": 87
  }
}
```

### Worker Metrics (via stream:metrics)

Each worker publishes health metrics every 10 seconds:

```json
{
  "worker": "detection-worker",
  "timestamp": "2026-03-16T10:30:10Z",
  "frames_processed": 360,
  "avg_latency_ms": 95,
  "errors_last_min": 0,
  "cpu_percent": 45,
  "ram_mb": 350
}
```

### Structured Logging

All containers use JSON-formatted logs viewable in Dozzle:

```json
{
  "timestamp": "2026-03-16T10:30:00.123Z",
  "level": "INFO",
  "service": "detection-worker",
  "message": "Detected 47 faces in room-1",
  "room_id": "room-1",
  "face_count": 47,
  "latency_ms": 92
}
```

---

## 13. Docker Compose — Production Deployment

```yaml
version: "3.8"

services:
  api-gateway:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: >
      uvicorn app.main:app
      --host 0.0.0.0 --port 8000
      --workers 2
    restart: unless-stopped
    depends_on:
      redis:
        condition: service_healthy
    environment:
      - SERVICE_ROLE=api-gateway
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      resources:
        limits:
          memory: 1.5G
          cpus: "1.5"

  detection-worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: python -m app.workers.detection_worker
    restart: unless-stopped
    depends_on:
      redis:
        condition: service_healthy
    environment:
      - SERVICE_ROLE=detection-worker
      - ORT_INTRA_OP_NUM_THREADS=2
      - ORT_INTER_OP_NUM_THREADS=1
    healthcheck:
      test: ["CMD", "python", "-c", "import redis; r=redis.from_url('redis://redis:6379'); r.ping()"]
      interval: 30s
      timeout: 5s
      retries: 3
    deploy:
      resources:
        limits:
          memory: 1.5G
          cpus: "1.0"

  recognition-worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: python -m app.workers.recognition_worker
    restart: unless-stopped
    depends_on:
      redis:
        condition: service_healthy
    environment:
      - SERVICE_ROLE=recognition-worker
      - ORT_INTRA_OP_NUM_THREADS=2
      - ORT_INTER_OP_NUM_THREADS=1
    healthcheck:
      test: ["CMD", "python", "-c", "import redis; r=redis.from_url('redis://redis:6379'); r.ping()"]
      interval: 30s
      timeout: 5s
      retries: 3
    deploy:
      resources:
        limits:
          memory: 1.5G
          cpus: "1.0"

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 3
    deploy:
      resources:
        limits:
          memory: 300M

  mediamtx:
    image: bluenviron/mediamtx:latest
    restart: unless-stopped
    ports:
      - "8554:8554"       # RTSP ingest
      - "8889:8889/tcp"   # WebRTC WHEP
      - "8189:8189/udp"   # WebRTC UDP
    volumes:
      - ./mediamtx.yml:/mediamtx.yml
    deploy:
      resources:
        limits:
          memory: 256M

  coturn:
    image: coturn/coturn:latest
    restart: unless-stopped
    network_mode: host
    volumes:
      - ./turnserver.conf:/etc/turnserver.conf
    deploy:
      resources:
        limits:
          memory: 256M

  nginx:
    image: nginx:alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - certbot_certs:/etc/letsencrypt
    depends_on:
      - api-gateway
    deploy:
      resources:
        limits:
          memory: 128M

  dozzle:
    image: amir20/dozzle:latest
    restart: unless-stopped
    ports:
      - "9999:8080"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    deploy:
      resources:
        limits:
          memory: 128M

volumes:
  faiss_data:
  face_uploads:
  app_logs:
  certbot_certs:
```

### VPS Resource Allocation

| Container | RAM Limit | CPU Limit | Actual Usage |
|-----------|----------|-----------|-------------|
| api-gateway | 1.5GB | 1.5 cores | ~500MB, 0.5 core |
| detection-worker | 1.5GB | 1.0 core | ~400MB, 0.5 core |
| recognition-worker | 1.5GB | 1.0 core | ~500MB, 0.3 core (burst) |
| redis | 300MB | — | 50MB |
| mediamtx | 256MB | — | 128MB |
| coturn | 256MB | — | 50MB |
| nginx | 128MB | — | 30MB |
| dozzle | 128MB | — | 50MB |
| **Total limits** | **5.6GB / 8GB** | **3.5 / 4 cores** | **~1.7GB / ~1.3 cores** |

---

## 14. Complete Tech Stack

| Layer | Technology | Version | Role |
|-------|-----------|---------|------|
| **Camera** | Reolink P340 | — | 12MP IP camera, RTSP, PoE |
| **Edge OS** | Raspberry Pi OS (Bookworm) | Latest | RPi operating system |
| **Edge Runtime** | Python 3.11 | 3.11 | Camera gateway service |
| **Stream Relay** | FFmpeg | 6.x | RTSP remux (-c copy) |
| **Media Server** | mediamtx | Latest | RTSP → WebRTC bridge |
| **TURN Server** | coturn | Latest | NAT traversal |
| **Backend Framework** | FastAPI | 0.110+ | REST API + WebSocket |
| **ASGI Server** | Uvicorn | 0.29+ | Production ASGI |
| **Detection Model** | SCRFD (InsightFace buffalo_l) | 0.7+ | Face detection, small-face capable |
| **Recognition Model** | ArcFace (InsightFace buffalo_l) | 0.7+ | Face embedding, industry standard |
| **Inference Runtime** | ONNX Runtime | 1.17+ | CPU-optimized inference |
| **Vector Search** | FAISS (faiss-cpu) | 1.7+ | Cosine similarity search |
| **State Estimation** | Kalman Filter (custom) | — | Bbox smoothing, 30 FPS output |
| **Event Bus** | Redis Streams | 7.x | Event-driven pipeline |
| **Cache** | Redis | 7.x | Identity cache, metrics |
| **Database** | PostgreSQL 15 | 15 | Via Supabase (managed) |
| **ORM** | SQLAlchemy | 2.0 | Database access layer |
| **Auth** | Supabase Auth (GoTrue) | Latest | JWT, email verification |
| **Scheduler** | APScheduler | 3.10+ | Background jobs (presence scans) |
| **Reverse Proxy** | nginx | Latest | SSL termination, routing |
| **TLS** | Let's Encrypt (certbot) | Latest | HTTPS certificates |
| **Containers** | Docker + Docker Compose | Latest | Deployment orchestration |
| **Mobile Framework** | React Native (Expo) | SDK 50+ | Cross-platform mobile |
| **Mobile State** | Zustand | 4.x | State management |
| **Mobile HTTP** | Axios | 1.x | API client with interceptors |
| **Mobile Video** | react-native-webrtc | Latest | WebRTC WHEP playback |
| **Mobile Animation** | react-native-reanimated | 3.x | 60 FPS bbox animations |
| **Mobile Charts** | Victory Native | Latest | Analytics visualization |
| **Logging** | Python logging + JSON | Built-in | Structured logs |
| **Log Viewer** | Dozzle | Latest | Web-based Docker log viewer |

---

## 15. Performance Targets

| Metric | Target | How Achieved |
|--------|--------|-------------|
| Video latency (camera → phone) | < 500ms | WebRTC passthrough, no transcode |
| New face → name on screen | < 3 seconds | Event-driven recognition + Redis Streams |
| Bbox smoothness | 60 FPS on mobile | Reanimated spring interpolation of 30 FPS data |
| Detection throughput | 6 frames/sec (2 rooms × 3 FPS) | SCRFD ONNX optimized |
| Cold start (50 faces) | < 4 seconds | Batch ONNX inference |
| Attendance update to dashboard | < 1 second | Redis Stream → WebSocket |
| Early-leave alert delivery | < 5 seconds after 3rd miss | Presence Engine → stream:alerts → WebSocket |
| System uptime | 99.9% during demo | Docker restart policy + health checks |
| RPi CPU usage | < 25% | Gateway only, zero ML |
| VPS CPU usage (steady) | < 40% | Event-driven, recognize only new tracks |

---

## 16. Enterprise Patterns Applied

| Pattern | Implementation | Enterprise Equivalent |
|---------|---------------|----------------------|
| Dual-stream architecture | Main (12MP) for detection, sub (720p) for viewing | Hikvision, Dahua |
| Edge gateway, server intelligence | RPi relays, VPS processes | Genetec Security Center |
| Event-driven pipeline | Redis Streams with consumer groups | Kafka in enterprise (same pattern) |
| Media router | mediamtx RTSP↔WebRTC | Genetec Media Router role |
| Kalman-smoothed tracking | 30 FPS from 3 FPS input | DeepSORT in production systems |
| Event-driven recognition | Only new tracks trigger inference | Avigilon Appearance Search |
| Containerized services | Docker Compose with fault isolation | Kubernetes (same concept, right scale) |
| Health monitoring | Deep health checks, structured JSON logs | Enterprise observability stack |
| Graceful degradation | Offline queue, auto-reconnect, track coasting | Fault-tolerant by design |
| NAT traversal | coturn TURN/STUN | Required for production WebRTC |
| Auto-session lifecycle | Schedule-driven, zero human intervention | Enterprise VMS automation |
| Audit logging | All actions recorded with actor/target/metadata | Compliance requirement |

---

## 17. Security

| Aspect | Implementation |
|--------|---------------|
| Authentication | Supabase Auth (GoTrue) — JWT tokens |
| Authorization | Role-based (student/faculty/admin) via middleware |
| Transport | HTTPS (TLS 1.3) via Let's Encrypt + nginx |
| WebSocket | WSS (encrypted WebSocket over TLS) |
| RTSP | Authenticated (admin:password) on Reolink |
| API Rate Limiting | SlowAPI on auth endpoints (10/min) |
| Edge Auth | RPi authenticates to VPS with API key |
| FAISS Sync | Redis pub/sub notification on index changes |
| Audit Trail | All state-changing actions logged |
