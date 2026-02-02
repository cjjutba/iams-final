# Technical Specification

## System Requirements

### Hardware

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| Laptop CPU | Intel i5 10th Gen | Intel i5 12th Gen |
| Laptop GPU | GTX 1650 | RTX 3050+ |
| Laptop RAM | 8 GB | 16 GB |
| RPi Model | Raspberry Pi 4 (2GB) | Raspberry Pi 4 (4GB) |
| Camera | 720p USB | 1080p Pi Camera Module 3 |
| Storage | 256 GB SSD | 512 GB SSD |

### Software

| Component | Version |
|-----------|---------|
| Python | 3.11+ |
| PostgreSQL | 15+ (Supabase) |
| CUDA | 11.8 |
| React Native | 0.73+ |
| Node.js | 20+ |
| TypeScript | 5.x |

### Network

| Requirement | Specification |
|-------------|---------------|
| WiFi | 5 GHz preferred |
| Bandwidth | 10 Mbps minimum |
| Latency | < 50ms local network |

---

## Performance Targets

| Metric | Target | Maximum |
|--------|--------|---------|
| Face detection time | 30ms | 50ms |
| Face recognition time | 50ms | 100ms |
| End-to-end latency | 200ms | 500ms |
| Scan interval | 60s | configurable |
| Concurrent users (mobile) | 50 | 100 |
| Faces in database | 500 | 1000 |

---

## API Specifications

### Base URL
```
Development: http://localhost:8000/api/v1
Production: https://api.domain.com/api/v1
```

### Authentication
- Type: Bearer Token (JWT) — from Supabase Auth or backend-issued
- Header: `Authorization: Bearer <token>`
- Token expiry: 30 minutes (configurable)
- Refresh token expiry: 7 days (Supabase)
- Mobile: Supabase client for login/signup; backend verifies JWT on protected routes

### Rate Limits
| Endpoint Type | Limit |
|---------------|-------|
| Auth endpoints | 10 req/min |
| Face processing | 60 req/min |
| General API | 100 req/min |

### Response Format
```
Success:
{
  "success": true,
  "data": { ... },
  "message": "Operation completed"
}

Error:
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message"
  }
}
```

---

## Edge API Contract (RPi → Server)

The edge device sends cropped faces to the server. This contract defines request and response shapes so RPi and server stay in sync.

### Endpoint
```
POST /api/v1/face/process
Content-Type: application/json
```

### Request
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| room_id | string (UUID) | Yes | Room/session identifier |
| timestamp | string (ISO 8601) | Yes | Capture time |
| faces | array | Yes | One or more face objects |
| faces[].image | string | Yes | Base64-encoded JPEG |
| faces[].bbox | array [x, y, w, h] | No | Bounding box for tracking |

Example:
```json
{
  "room_id": "uuid-of-room-or-schedule",
  "timestamp": "2024-01-15T10:00:00Z",
  "faces": [
    {
      "image": "base64_encoded_jpeg_data",
      "bbox": [100, 80, 120, 120]
    }
  ]
}
```

### Response
| Field | Type | Description |
|-------|------|-------------|
| success | boolean | Operation success |
| data.processed | integer | Number of faces processed |
| data.matched | array | Recognized users |
| data.matched[].user_id | string | User UUID |
| data.matched[].confidence | float | Similarity score |
| data.unmatched | integer | Count of unrecognized faces |

Example:
```json
{
  "success": true,
  "data": {
    "processed": 2,
    "matched": [
      {"user_id": "uuid", "confidence": 0.85},
      {"user_id": "uuid", "confidence": 0.92}
    ],
    "unmatched": 0
  }
}
```

### Errors
| Code | When |
|------|------|
| 400 | Invalid JSON, missing room_id/timestamp/faces, or invalid image |
| 401 | Missing or invalid auth (if endpoint is protected) |
| 500 | Server/recognition error |

---

## Face Recognition Specifications

### Input Requirements
| Parameter | Value |
|-----------|-------|
| Image format | JPEG, PNG |
| Minimum resolution | 112x112 |
| Recommended resolution | 160x160 |
| Face angle | ±30° yaw, ±20° pitch |
| Minimum face size | 80x80 pixels in frame |

### Model Specifications
| Parameter | Value |
|-----------|-------|
| Model | FaceNet (InceptionResnetV1) |
| Embedding size | 512 dimensions |
| Input size | 160x160x3 |
| Distance metric | Cosine similarity |
| Match threshold | 0.6 |
| Training dataset | VGGFace2 |

### FAISS Index
| Parameter | Value |
|-----------|-------|
| Index type | IndexFlatIP (Inner Product) |
| Dimensions | 512 |
| Search type | Exact nearest neighbor |
| Top-K | 1 |

---

## Presence Tracking Specifications

### Timing
| Parameter | Default | Range |
|-----------|---------|-------|
| Scan interval | 60 seconds | 30-120 seconds |
| Early leave threshold | 3 consecutive misses | 2-5 misses |
| Grace period (late) | 15 minutes | 5-30 minutes |
| Session buffer | 5 minutes before/after | configurable |

### Status Definitions
| Status | Condition |
|--------|-----------|
| Present | Detected at start, presence score ≥ 80% |
| Late | First detected after grace period |
| Early Leave | Flagged by miss threshold |
| Absent | Never detected during session |

### Presence Score
```
Score = (scans_detected / total_scans) × 100%
```

---

## Database Specifications

### Connection Pool
| Parameter | Value |
|-----------|-------|
| Min connections | 5 |
| Max connections | 20 |
| Connection timeout | 30 seconds |
| Idle timeout | 300 seconds |

### Table Sizes (Estimated)
| Table | Rows (1 year, 500 students) |
|-------|----------------------------|
| users | 600 |
| face_registrations | 600 |
| schedules | 200 |
| enrollments | 5,000 |
| attendance_records | 100,000 |
| presence_logs | 2,000,000 |
| early_leave_events | 5,000 |

### Indexes
| Table | Indexed Columns |
|-------|-----------------|
| users | email, student_id |
| attendance_records | student_id + date, schedule_id + date |
| presence_logs | attendance_id, scan_time |
| schedules | day_of_week + start_time |

---

## WebSocket Specifications

### Connection
```
URL: ws://localhost:8000/api/v1/ws/{user_id}
Protocol: WebSocket
Heartbeat: 30 seconds
```

### Events
| Event | Direction | Payload |
|-------|-----------|---------|
| attendance_update | Server → Client | { student_id, status, timestamp } |
| early_leave | Server → Client | { student_id, schedule_id, timestamp } |
| session_start | Server → Client | { schedule_id, start_time } |
| session_end | Server → Client | { schedule_id, summary } |
| ping | Both | { type: "ping" } |
| pong | Both | { type: "pong" } |

---

## Mobile App Specifications (React Native)

### Supported Platforms
| Platform | Minimum Version |
|----------|-----------------|
| Android | API 24 (Android 7.0) |
| iOS | iOS 12.0 |

### Registration Flows
| User | Flow |
|------|------|
| Student | Onboarding → Welcome → Login or Register. Register: Step 1 verify ID (manual or scan) → Step 2 account (email, phone, password) → Step 3 face (3–5 angles) → Review & submit. |
| Faculty | Welcome → Login only (pre-seeded; no self-registration in MVP). |

### Permissions Required
| Permission | Purpose |
|------------|---------|
| Camera | Face registration |
| Internet | API communication |
| Notifications | Alerts |

### Offline Behavior
| Feature | Offline Support |
|---------|-----------------|
| View cached attendance | Yes |
| Login | No |
| Face registration | No |
| Real-time updates | No |

---

## Security Specifications

### Authentication
| Mechanism | Details |
|-----------|---------|
| Password hashing | bcrypt, cost factor 12 |
| JWT algorithm | HS256 |
| Token storage | Secure storage (mobile) |

### Data Protection
| Data | Protection |
|------|------------|
| Passwords | Hashed, never stored plain |
| Face images | Not stored (only embeddings) |
| Embeddings | Stored in FAISS, not reversible |
| API traffic | HTTPS in production |

### Access Control
| Role | Permissions |
|------|-------------|
| Student | View own data only |
| Faculty | View class data, manage attendance |
| Admin | Full system access |

---

## Edge Device Specifications

### Processing Pipeline
| Stage | Time Budget |
|-------|-------------|
| Frame capture | 10ms |
| Face detection | 30ms |
| Crop + compress | 10ms |
| Network send | 20ms |
| **Total per frame** | **70ms** |

### Resource Limits
| Resource | Limit |
|----------|-------|
| CPU usage | < 80% |
| Memory usage | < 512 MB |
| Network bandwidth | < 1 Mbps |
| Storage | < 100 MB |

### Recovery Behavior
| Failure | Recovery |
|---------|----------|
| Camera disconnect | Retry every 5 seconds |
| Server unreachable | Queue locally, retry every 10 seconds (see implementation.md) |
| Out of memory | Restart service |
| Crash | Auto-restart via systemd |

---

## Configuration Parameters

### Environment Variables
| Variable | Description | Default |
|----------|-------------|---------|
| SUPABASE_URL | Supabase project URL | - |
| SUPABASE_ANON_KEY | Supabase anon key (for backend if needed) | - |
| DATABASE_URL | PostgreSQL connection (Supabase pooler or local) | - |
| SECRET_KEY | JWT signing key (if custom auth) | - |
| FAISS_INDEX_PATH | Path to FAISS file | ./data/faiss.index |
| RECOGNITION_THRESHOLD | Match threshold | 0.6 |
| SCAN_INTERVAL | Seconds between scans | 60 |
| EARLY_LEAVE_THRESHOLD | Missed scans to flag | 3 |
| EDGE_SERVER_URL | Backend URL for RPi | - |
| API_BASE_URL | Backend URL for mobile app | - |