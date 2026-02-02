# Implementation Guide

## Overview
This document explains how each component works and connects together.

---

## 1. Edge Device (Raspberry Pi)

### What It Does
- Captures video frames from camera
- Detects faces in each frame
- Crops detected faces
- Sends cropped faces to server

### How It Works

```
Camera → Frame → Detect Faces → Crop → Compress → Send to Server
```

| Step | Input | Output | Tool |
|------|-------|--------|------|
| Capture | Camera stream | Raw frame (640x480) | picamera2 / OpenCV |
| Detect | Raw frame | Face bounding boxes | MediaPipe |
| Crop | Frame + boxes | Face images (112x112) | OpenCV |
| Compress | Face images | JPEG (70% quality) | OpenCV |
| Send | JPEG bytes | HTTP response | httpx |

### Key Settings
- Frame rate: 15 FPS
- Resolution: 640x480
- Face crop size: 112x112 pixels
- Compression: JPEG 70%
- Send interval: Every detected face

### RPi Queue Policy (Server Unreachable)
When the server is unreachable, the edge device queues faces locally to avoid data loss and retries until the connection is restored.

| Parameter | Value | Description |
|-----------|-------|-------------|
| Queue max size | 500 items | Drop oldest if full to bound memory |
| Queue TTL | 5 minutes | Discard items older than 5 min |
| Retry interval | 10 seconds | Retry POST after failure |
| Retry max attempts | 3 per batch | Then re-queue and retry later |
| Batch size on send | 1 face per request | Per API contract (see api-reference.md) |

Implementation: use a bounded in-memory queue (e.g. `collections.deque(maxlen=500)`). On successful POST, clear sent item; on failure, re-queue and sleep before retry. Log queue depth and drops for monitoring.

---

## 2. Backend Server

### What It Does
- Receives cropped faces from RPi
- Recognizes who the face belongs to
- Tracks student presence over time
- Detects early leaves
- Serves mobile app API
- Pushes real-time updates

### Module Breakdown

#### Authentication Module
| Function | Description |
|----------|-------------|
| Register | Create new user account |
| Login | Verify credentials, return JWT |
| Verify Token | Check JWT validity |
| Refresh Token | Issue new token |

#### Face Module
| Function | Description |
|----------|-------------|
| Register Face | Save face embedding to FAISS |
| Recognize Face | Match incoming face against database |
| Generate Embedding | Convert face image to 512-dim vector |
| Search Similar | Find closest match in FAISS |

#### Attendance Module
| Function | Description |
|----------|-------------|
| Mark Present | Record student check-in |
| Log Presence | Record periodic scan result |
| Get Records | Fetch attendance history |
| Calculate Score | Compute presence percentage |

#### Presence Module
| Function | Description |
|----------|-------------|
| Start Session | Begin tracking for a class |
| Run Scan | Check who is present now |
| Track Misses | Count consecutive absences |
| Flag Early Leave | Mark student who left |
| End Session | Finalize attendance records |

#### Notification Module
| Function | Description |
|----------|-------------|
| Connect Client | Handle WebSocket connection |
| Push Update | Send attendance change |
| Send Alert | Notify early leave |

### Tracking Service (DeepSORT)
DeepSORT runs on the **server**, not on the RPi. The server receives multiple cropped faces per frame (or per batch) from the RPi. DeepSORT is used to associate the same physical person across consecutive frames using track IDs, so that repeated recognitions of the same face are counted once per scan and identity is stable. Flow: RPi sends faces with optional bounding boxes → server recognizes each face → tracking service assigns/updates track IDs → presence service uses track IDs to avoid double-counting and to compute "detected in this scan" per student.

---

## 3. Face Recognition Pipeline

### Registration Flow
```
1. User opens mobile app
2. User captures face photos (5 angles)
3. App sends photos to server
4. Server generates embedding for each
5. Server averages embeddings
6. Server saves to FAISS index
7. Server links embedding ID to user
```

### Face Registration Rules (Mobile)
| Rule | Value | Description |
|------|-------|-------------|
| Number of images | 3–5 | Require at least 3, accept up to 5 |
| Resolution | Min 112×112, recommended 160×160 | Reject if too small |
| Rejection | Blur, multiple faces, no face | Validate before upload; return 400 with reason |
| Session | Tied to authenticated user | No anonymous registration |

### Recognition Flow
```
1. RPi sends cropped face
2. Server generates embedding
3. Server searches FAISS (top 1 match)
4. If similarity > 0.6 → match found
5. Server returns user ID
6. Server marks attendance
```

### Embedding Details
- Model: FaceNet (InceptionResnetV1)
- Input: 160x160 RGB image
- Output: 512-dimensional vector
- Distance: Cosine similarity
- Threshold: 0.6 (adjustable)

### FAISS Index Lifecycle
The FAISS index and the `face_registrations` table must stay in sync.

| Operation | Action |
|-----------|--------|
| **Add** | Generate embedding(s), add vector(s) to FAISS, get index id(s). Insert row in `face_registrations` with `embedding_id` = FAISS id, `user_id`. Persist FAISS index to disk after add. |
| **Update (re-register)** | For the user, mark previous `face_registrations` row inactive or delete. Remove old id from FAISS (or rebuild index without that id). Then perform Add. |
| **Remove (user deactivated/deleted)** | Delete or mark inactive the `face_registrations` row. Remove the corresponding vector from FAISS (or rebuild index excluding that id). Persist FAISS index to disk. |
| **Rebuild** | If FAISS does not support single-vector delete: export all active embeddings from DB, rebuild FAISS from scratch, save file. Prefer doing this during low traffic. |

Implementation note: FAISS `IndexFlatIP` does not support native delete. Options are (1) rebuild index on remove, or (2) mark embedding as inactive in a side structure and filter at search time. Document the chosen approach in the face service.

---

## 4. Continuous Presence Tracking

### Schedule and Session Semantics
Presence and attendance are scoped to a **schedule** and **date**.

| Concept | Definition |
|---------|------------|
| **Schedule** | A class slot: subject, faculty, room, day_of_week, start_time, end_time (and optional semester/academic_year). |
| **Current class** | The schedule for which (date, current time) falls within [start_time, end_time] on the given day_of_week. If multiple overlap, use the first match or a defined rule (e.g. by room). |
| **Session** | One instance of that schedule on a given date: from session start (e.g. start_time or 5 min before) until session end (e.g. end_time or 5 min after). |
| **Enrolled student** | Any user with an enrollment record for that schedule. |
| **Active schedule** | Schedule where is_active = true and (optional) current date is within semester/academic_year. |

All times should be stored and compared in a consistent timezone (e.g. UTC or school local); document the choice in config.

### How It Works
```
Every 60 seconds:
  For each enrolled student:
    If face detected in latest scan:
      → Reset miss counter to 0
      → Log as "present"
    Else:
      → Increment miss counter
      → Log as "not detected"
      
    If miss counter >= 3:
      → Flag as "early leave"
      → Send alert to faculty
```

### State Per Student
| Field | Type | Description |
|-------|------|-------------|
| last_seen | timestamp | Last time face was detected |
| miss_count | integer | Consecutive missed scans |
| total_scans | integer | Total scans in session |
| total_present | integer | Scans where detected |
| flagged | boolean | Early leave flagged |

### Presence Score
```
Score = (total_present / total_scans) × 100%
```

---

## 5. Student and Faculty Registration Flows (Summary)

### App Entry (React Native)
1. **Onboarding** — 4–5 slides: what is IAMS, how attendance works, face registration info, privacy.
2. **Welcome** — User selects "Student" or "Faculty".

### Student Registration (3 steps + review)
1. **Step 1 – Verify identity:** Enter Student ID (manual) or optionally scan/upload ID. Backend validates against university data (CSV/JRMSU). Show name, course, year; user confirms "Is this me?"
2. **Step 2 – Account setup:** Email (pre-filled if from university), phone, password. Create account in Supabase Auth (or backend); store profile in Supabase/Postgres.
3. **Step 3 – Face registration:** Capture 3–5 angles in React Native app; upload to backend; backend generates embeddings and saves to FAISS.
4. **Review & submit:** Summary screen; user agrees to terms and submits. Backend validates and finalizes (link face to user).

### Faculty (MVP)
- **No self-registration.** Faculty accounts are **pre-seeded** from client list (JRMSU). Faculty only **login** (email + password) via Supabase Auth. Message on login: "Faculty accounts are created by the administrator. Contact your department if you need access."

### University Data (JRMSU)
- Student validation and faculty list come from **university data** (CSV export from client). Import once or sync via script. Backend checks Student ID against this data before allowing registration.

### Auth and Database (Supabase)
- **Supabase** provides hosted PostgreSQL and Auth. Backend connects to Supabase Postgres for users, schedules, attendance. Mobile app uses Supabase Auth for login/signup (students) and login only (faculty). Backend can verify JWT from Supabase on protected routes.

---

## 6. Mobile App (React Native)

### Student Features
| Screen | Purpose |
|--------|---------|
| Onboarding | 4–5 intro slides |
| Welcome | Select Student or Faculty |
| Student Login | Student ID + password |
| Student Register | Steps: verify ID → account → face → review |
| Face Registration | Capture 3–5 angles (part of register or separate) |
| Dashboard | Today's attendance status |
| History | Past attendance records |
| Profile | View/edit info |

### Faculty Features
| Screen | Purpose |
|--------|---------|
| Welcome | Select Faculty |
| Faculty Login | Email + password (pre-seeded; no register) |
| Dashboard | Current class overview |
| Live Attendance | Real-time student list |
| Alerts | Early leave notifications |
| Reports | Export attendance data |
| Manual Entry | Override attendance |

### Real-time Updates
- WebSocket connection to backend
- Auto-reconnect on disconnect
- Updates attendance list instantly
- Shows alerts as notifications

### Tech (React Native)
- State: Zustand or React Context
- HTTP: axios; Auth: Supabase client
- Camera: react-native-vision-camera or expo-camera
- Storage: AsyncStorage for tokens/cache

---

## 7. Database Operations

### User Registration
```
1. Validate input
2. Hash password
3. Insert into users table
4. Return user ID
```

### Attendance Recording
```
1. Receive recognized user ID
2. Find active schedule for current time
3. Check if record exists for today
4. If no → Create new record (check-in time)
5. If yes → Update (presence logged)
```

### Early Leave Recording
```
1. Presence service flags student
2. Create early_leave_events record
3. Update attendance status to "early_leave"
4. Trigger notification
```

---

## 8. Data Synchronization

### RPi → Server
- Protocol: HTTP POST
- Endpoint: /api/v1/face/process
- Payload: See api-reference.md (Edge API contract: single face or batch, Base64 JPEG, optional room_id/session_id, timestamp).
- Response: Recognition result (matched user_id, confidence, or unmatched).

### Backend → Mobile (React Native)
- Protocol: WebSocket
- Events: attendance_update, early_leave, session_end
- Format: JSON

### Offline Handling
- RPi: Queue faces locally if server unreachable (see RPi Queue Policy above).
- Mobile: Cache last known state; sync when connection restored.

---

## 9. Error Handling

| Error | Response |
|-------|----------|
| Face not detected | Skip frame, continue |
| Face not recognized | Log as unknown, continue |
| Server unreachable | Queue on RPi, retry (see queue policy) |
| Database error | Return 500, log error |
| Invalid token | Return 401, prompt re-login |
| WebSocket disconnect | Auto-reconnect |
