# IAMS: Intelligent Attendance Monitoring System
## Complete System Technical Reference

**Version:** 1.0
**Date:** March 30, 2026
**Institution:** Jose Rizal Memorial State University (JRMSU)
**Program:** Bachelor of Science in Computer Engineering (BSCpE)

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [System Architecture](#2-system-architecture)
3. [Technology Stack](#3-technology-stack)
4. [Face Recognition and AI Pipeline](#4-face-recognition-and-ai-pipeline)
5. [Edge Device (Raspberry Pi)](#5-edge-device-raspberry-pi)
6. [Backend Server (FastAPI)](#6-backend-server-fastapi)
7. [Android Mobile Application](#7-android-mobile-application)
8. [Database Design](#8-database-design)
9. [Real-Time Communication (WebSocket)](#9-real-time-communication-websocket)
10. [Media Streaming Architecture](#10-media-streaming-architecture)
11. [Continuous Presence Tracking and Attendance Logic](#11-continuous-presence-tracking-and-attendance-logic)
12. [Security and Anti-Spoofing](#12-security-and-anti-spoofing)
13. [Deployment and Production Environment](#13-deployment-and-production-environment)
14. [API Endpoints Reference](#14-api-endpoints-reference)
15. [User Flows](#15-user-flows)
16. [System Configuration Parameters](#16-system-configuration-parameters)
17. [Hardware Requirements](#17-hardware-requirements)
18. [Software Dependencies](#18-software-dependencies)

---

## 1. System Overview

### 1.1 What is IAMS?

IAMS (Intelligent Attendance Monitoring System) is a CCTV-based facial recognition attendance system designed for academic institutions. It automates the process of attendance tracking by using IP cameras installed in classrooms, combined with state-of-the-art face recognition AI models running on a cloud server, and a native Android mobile application for both students and faculty.

### 1.2 Problem Statement

Traditional attendance systems in educational institutions rely on manual roll calls, sign-in sheets, or basic biometric scanners. These methods are:
- **Time-consuming** — manual roll calls consume valuable class time
- **Prone to fraud** — proxy attendance (signing in for absent classmates) is common
- **Difficult to track continuously** — a student may sign in then leave early without detection
- **Lacking real-time visibility** — faculty cannot see at-a-glance who is present during class

### 1.3 Solution

IAMS solves these problems by:
- **Automated face recognition** — students are identified automatically via CCTV cameras; no manual intervention needed
- **Continuous presence monitoring** — the system scans every few seconds throughout the class session, not just at the start
- **Early-leave detection** — if a student disappears from the camera for a sustained period, the system generates an alert
- **Real-time dashboard** — faculty can view a live video feed with face overlays showing who is present, directly on their Android phone
- **Anti-spoofing measures** — the system includes checks to prevent photo-based attacks during face registration

### 1.4 Key Design Principles

1. **Three independent systems** — video delivery, face detection, and attendance tracking operate independently, ensuring that a failure in one does not affect the others
2. **Edge device simplicity** — the Raspberry Pi performs no AI processing; it is a dumb relay, keeping costs low and maintenance simple
3. **Server-side intelligence** — all AI inference (face detection, recognition, tracking) runs on the cloud server where compute resources can be scaled
4. **On-device augmentation** — the Android app uses Google ML Kit for real-time face detection at 30fps on the phone itself, providing smooth visual feedback independent of server processing speed

---

## 2. System Architecture

### 2.1 High-Level Architecture Diagram

```
+-------------------+         +-------------------+         +--------------------+
|   Reolink IP      |  RTSP   |   Raspberry Pi    |  RTSP   |   mediamtx         |
|   Camera          |-------->|   (FFmpeg relay)   |-------->|   (on VPS)         |
|   (EB226/EB227)   |         |   No ML/AI        |         |   RTSP + WebRTC    |
+-------------------+         +-------------------+         +--------------------+
                                                                    |
                              +-------------------------------------+----------+
                              |                                                |
                              v                                                v
                    +-------------------+                          +--------------------+
                    |   FastAPI Backend  |                          |   Android App      |
                    |   (on same VPS)    |                          |   (Student/Faculty) |
                    |                   |                          |                    |
                    | - Frame Grabber   |    WebSocket             | - ExoPlayer/WebRTC |
                    | - SCRFD Detection |------------------------>| - ML Kit (30fps)   |
                    | - ArcFace Recog.  |    (names + bboxes)     | - Face Overlays    |
                    | - ByteTrack       |                          | - Attendance Panel |
                    | - FAISS Index     |                          +--------------------+
                    | - Presence Logic  |
                    | - PostgreSQL      |
                    | - Redis Cache     |
                    +-------------------+
```

### 2.2 The Three Independent Systems

| System | Purpose | Where It Runs | Failure Impact |
|--------|---------|---------------|----------------|
| **Video Delivery** | Smooth live video for faculty | mediamtx (VPS) -> WebRTC -> Phone | If backend is down, video still works |
| **Face Detection** | Real-time bounding boxes on phone | ML Kit on Android phone (30fps) | If backend/network is down, boxes still appear |
| **Attendance Tracking** | Identify who is present, log attendance | FastAPI backend (VPS) | If phone disconnects, attendance still records |

This separation ensures:
- Faculty always see smooth video regardless of backend processing speed
- Bounding boxes appear instantly on the phone (no network round-trip needed)
- Attendance is tracked even if no faculty member is watching the live feed

### 2.3 Data Flow

1. **Camera to Cloud:** Reolink camera streams RTSP to Raspberry Pi, which relays it to mediamtx on the VPS
2. **Cloud to Phone (Video):** mediamtx serves WebRTC to the Android app via the WHEP protocol for low-latency video
3. **Cloud Processing:** The FastAPI backend grabs frames from mediamtx's RTSP output, runs face detection + recognition, and updates attendance records in PostgreSQL
4. **Cloud to Phone (Data):** The backend broadcasts recognition results (names, bounding boxes, attendance counts) to the Android app via WebSocket
5. **Phone Rendering:** The Android app overlays ML Kit's real-time face boxes with the backend's recognized names using IoU (Intersection over Union) matching

---

## 3. Technology Stack

### 3.1 Backend Technologies

| Technology | Version | Purpose |
|-----------|---------|---------|
| **Python** | 3.11+ | Primary backend language |
| **FastAPI** | 0.128.0 | Async web framework for REST API and WebSocket |
| **Uvicorn** | 0.40.0 | ASGI server with hot-reload (development) |
| **SQLAlchemy** | 2.0.46 | ORM for PostgreSQL database access |
| **PostgreSQL** | 16 | Primary relational database (self-hosted in Docker) |
| **Redis** | 7 | In-memory cache for identity lookups and pub/sub |
| **APScheduler** | 3.10.4 | Background job scheduling (session lifecycle, health checks) |
| **InsightFace** | 0.7.3 | Face detection (SCRFD) and recognition (ArcFace) models |
| **FAISS** | 1.13.2 | Facebook AI Similarity Search for fast face matching |
| **OpenCV** | 4.13.0 | Image processing (headless, no GUI) |
| **ONNX Runtime** | 1.21.0+ | Neural network inference engine |
| **Supervision** | 0.24.0 | ByteTrack multi-object tracking |
| **FFmpeg** | System | RTSP frame grabbing via subprocess |
| **Pydantic** | 2.12.5 | Request/response data validation |
| **Pillow** | 12.1.0 | Image processing (Python Imaging Library) |
| **NumPy** | 2.4.2 | Numerical computing for embedding vectors |
| **slowapi** | 0.1.9+ | API rate limiting |
| **Alembic** | 1.18.3 | Database migration tool |
| **Ruff** | 0.8.0+ | Python linter and formatter |

### 3.2 Android App Technologies

| Technology | Version | Purpose |
|-----------|---------|---------|
| **Kotlin** | 1.9+ | Primary mobile language |
| **Jetpack Compose** | Latest | Declarative UI framework |
| **Material 3** | Latest | UI design system (monochrome theme) |
| **ExoPlayer (Media3)** | Latest | RTSP/WebRTC video playback |
| **Google ML Kit** | Latest | On-device face detection (30fps) |
| **CameraX** | Latest | Camera capture for face registration |
| **Retrofit 2** | Latest | HTTP client for REST API calls |
| **OkHttp 3** | Latest | HTTP/WebSocket networking |
| **Hilt** | Latest | Dependency injection |
| **Navigation Compose** | Latest | Screen navigation |
| **DataStore** | Latest | Secure token persistence |
| **WebRTC (libwebrtc)** | Latest | WHEP video streaming |
| **Coil** | Latest | Image loading |
| **Lottie** | Latest | Loading/transition animations |

### 3.3 Infrastructure Technologies

| Technology | Purpose |
|-----------|---------|
| **Docker** | Containerization of all services |
| **Docker Compose** | Multi-container orchestration |
| **Nginx** | Reverse proxy, SSL termination, static file serving |
| **mediamtx** | RTSP ingestion server + WebRTC (WHEP) endpoint |
| **coturn** | TURN server for WebRTC NAT traversal |
| **Let's Encrypt** | Free SSL/TLS certificates |
| **DigitalOcean** | Cloud VPS hosting |
| **Dozzle** | Docker container log viewer |
| **Adminer** | Database administration web UI |

### 3.4 Edge Device Technologies

| Technology | Purpose |
|-----------|---------|
| **Raspberry Pi 4/5** | Edge compute device (relay only) |
| **FFmpeg** | RTSP stream relay from camera to VPS |
| **Python 3** | Control script for FFmpeg subprocess |

### 3.5 AI/ML Models

| Model | Type | Purpose | Details |
|-------|------|---------|---------|
| **SCRFD** | Face Detection | Detect face locations in frames | Part of InsightFace buffalo_l, 5-point landmark, det_size=480 |
| **ArcFace (ResNet50)** | Face Recognition | Generate 512-dimensional face embeddings | Cosine similarity for matching, part of InsightFace buffalo_l |
| **FAISS IndexFlatIP** | Vector Search | Fast nearest-neighbor search for face matching | Inner product on L2-normalized vectors (equivalent to cosine similarity) |
| **ByteTrack** | Multi-Object Tracking | Track face identities across frames | Maintains track IDs, handles occlusion, lost-track buffer |
| **Google ML Kit Face Detection** | On-Device Detection | Real-time face bounding boxes on phone | Runs at 30fps, no network required |

---

## 4. Face Recognition and AI Pipeline

### 4.1 Overview

The face recognition system operates in two distinct modes:
1. **Registration Mode** — a student captures 3-5 selfie images at different angles via the Android app's camera; these are processed and stored as face embeddings
2. **Recognition Mode** — the backend continuously grabs frames from CCTV cameras, detects faces, generates embeddings, and matches them against the stored database

### 4.2 Face Registration Pipeline

```
Student's Phone (CameraX)
        |
        | Capture 3-5 face images at different angles
        v
  ML Kit Face Detection (on-device, ensures face is present)
        |
        | Upload images to backend
        v
  Backend: POST /api/v1/face/register
        |
        v
  SCRFD Face Detection
        | Detect face bounding box + 5 landmarks
        v
  Quality Gating
        | - Blur check (Laplacian variance > 10 for mobile)
        | - Brightness check (mean pixel 40-220)
        | - Face size check (>= 5% of image area)
        | - Detection confidence (>= 0.5)
        v
  Anti-Spoofing Checks
        | - Embedding variance across angles (>= 0.1 cosine distance)
        | - LBP texture analysis (uniformity <= 0.15)
        | - FFT frequency analysis (high-freq energy <= 0.20)
        v
  ArcFace Embedding Generation
        | Generate 512-dimensional embedding per image
        v
  Embedding Averaging + L2 Normalization
        | Average all valid embeddings into single vector
        v
  FAISS Index Addition
        | Store in IndexFlatIP with user_id mapping
        v
  Database Record
        | Save face_registration with embedding_id
        v
  Registration Complete
```

### 4.3 Face Recognition Pipeline (CCTV)

```
mediamtx RTSP Output
        |
        v
  FrameGrabber (FFmpeg subprocess)
        | Read RTSP stream, output BGR frames (480x360, 10fps)
        v
  SCRFD Face Detection
        | Detect all faces in frame with bounding boxes
        v
  ByteTrack Multi-Object Tracker
        | Associate detections to existing tracks (track_id)
        | New track? -> proceed to recognition
        | Known track? -> reuse cached identity (re-verify every 15s)
        v
  ArcFace Embedding Generation
        | Generate 512-dim embedding for new/re-verify faces
        v
  FAISS Nearest Neighbor Search (top-k=3)
        | Search index for closest matching embeddings
        v
  Similarity Threshold Check
        | Cosine similarity > 0.25? -> MATCH
        | Top-1 margin > 0.05 over top-2? -> Confident match
        v
  Identity Assignment
        | Assign name + user_id to track
        | Cache for 15 seconds before re-verification
        v
  Presence Tracking Service
        | Update presence timers, detect early leaves
        v
  WebSocket Broadcast
        | Send frame_update (10fps) + attendance_summary (5-10s)
        | to all connected Android app clients
```

### 4.4 AI Models in Detail

#### 4.4.1 SCRFD (Sample and Computation Redistribution for Efficient Face Detection)

SCRFD is a high-performance face detection model that is part of the InsightFace library. It provides:
- **Face bounding boxes** — pixel coordinates of detected faces
- **5-point facial landmarks** — eyes, nose, mouth corners for alignment
- **Detection confidence score** — probability that the detection is a real face

Configuration:
- Detection size: 480 pixels (balances speed and accuracy)
- Detection threshold: 0.5 (minimum confidence to accept a detection)
- Runs on ONNX Runtime with CPU execution (CoreML on macOS for development)

#### 4.4.2 ArcFace (Additive Angular Margin Loss for Deep Face Recognition)

ArcFace is a face recognition model based on ResNet50 architecture. It generates a 512-dimensional embedding vector for each detected face. Key properties:
- **Embedding dimension:** 512 floating-point values
- **Distance metric:** Cosine similarity (computed as inner product on L2-normalized vectors)
- **Cross-domain capability:** Embeddings from mobile selfies can be matched against CCTV frames
- **Model package:** InsightFace buffalo_l (~500MB download)

The model is loaded once at server startup and shared across all processing threads.

#### 4.4.3 FAISS (Facebook AI Similarity Search)

FAISS is a library for efficient similarity search on dense vectors. IAMS uses it to quickly find the closest matching face embedding from the database of registered students.

- **Index type:** `IndexFlatIP` (Flat Index with Inner Product)
- **Search method:** Exact nearest neighbor (no approximation)
- **Vector dimension:** 512
- **Distance metric:** Inner product on L2-normalized vectors = cosine similarity
- **Persistence:** Saved to disk at `data/faiss/faces.index`, memory-mapped for multi-worker access
- **Synchronization:** Redis pub/sub notifies all Uvicorn workers when the index is updated

#### 4.4.4 ByteTrack (Multi-Object Tracking)

ByteTrack maintains identity continuity across video frames. Without tracking, the system would need to run face recognition on every face in every frame (computationally expensive). With tracking:
- Face recognition (ArcFace + FAISS) is only called for **new tracks** or every **15 seconds** for re-verification
- A track maintains a stable `track_id` even if the face is briefly occluded
- Lost tracks are kept in a buffer for 5 seconds before being discarded

Configuration:
- Track activation threshold: 0.1 (low, to detect even partially visible faces)
- Match threshold: 0.8 (IoU for associating detections to tracks)
- Lost track buffer: 50 frames (5 seconds at 10fps)

#### 4.4.5 Google ML Kit Face Detection (On-Device)

Google ML Kit runs entirely on the Android phone with no network requirements:
- **Frame rate:** 30fps face detection on live video
- **Input:** TextureView frames from ExoPlayer's WebRTC video
- **Output:** Face bounding boxes drawn as real-time overlays
- **Purpose:** Provides immediate visual feedback to faculty; backend recognition results (names) are matched to ML Kit bounding boxes using IoU overlap

### 4.5 Cross-Domain Face Matching

A unique challenge in IAMS is that face registration images are captured as **mobile phone selfies** (close-up, well-lit, frontal) while recognition happens on **CCTV camera frames** (distant, variable lighting, various angles). This is called **cross-domain matching**.

Key adaptations:
- Recognition threshold is set relatively low (0.25) to account for domain differences
- Adaptive threshold system monitors match quality over time and adjusts
- Multiple registration images (3-5 angles) provide robustness
- The same SCRFD + ArcFace pipeline processes both domains, ensuring embedding compatibility

---

## 5. Edge Device (Raspberry Pi)

### 5.1 Purpose and Design Philosophy

The Raspberry Pi serves as a **dumb RTSP relay** — it receives the RTSP video stream from the Reolink IP camera on the local network and forwards it to the mediamtx server on the cloud VPS. The RPi performs **zero AI/ML processing**.

This design choice was made because:
1. **Cost efficiency** — a basic Raspberry Pi (no GPU) is sufficient
2. **Reliability** — fewer processes running means fewer points of failure
3. **Scalability** — all ML runs on the VPS, which can be scaled vertically
4. **Maintenance** — the RPi rarely needs updates; it just relays video

### 5.2 How It Works

```
Reolink Camera (192.168.88.10)
        |
        | RTSP stream (H.264, 1080p or sub-stream)
        v
  Raspberry Pi
        |
        | FFmpeg subprocess relay
        | Command: ffmpeg -i rtsp://camera -c copy -f rtsp rtsp://vps:8554/{room}/raw
        v
  mediamtx on VPS (167.71.217.44:8554)
```

The `StreamRelay` class:
- Spawns an FFmpeg subprocess that reads from the camera's RTSP URL
- Outputs to the VPS mediamtx server using RTSP publish
- Uses `-c copy` (no transcoding) to minimize CPU usage
- Monitors the FFmpeg process every 5 seconds; restarts if it dies
- Runs in a continuous loop — the RPi is always-on during school hours

### 5.3 Configuration

The RPi is configured via environment variables:
```
ROOM_ID=eb226                    # Identifies which classroom this RPi serves
RTSP_MAIN=rtsp://admin:pass@192.168.88.10:554/h264Preview_01_main
VPS_RTSP_URL=rtsp://167.71.217.44:8554
```

### 5.4 Network Setup

- The RPi connects to the campus WiFi network (same LAN as the IP camera)
- It establishes an outbound RTSP connection to the VPS (no inbound ports needed)
- If the network drops, the FFmpeg process exits and the relay loop restarts it automatically

### 5.5 Supported Cameras

The system currently supports two Reolink IP cameras:
- **EB226** — installed in classroom EB226
- **EB227** — installed in classroom EB227

Each camera has a dedicated RPi relay or shares a multi-stream relay.

---

## 6. Backend Server (FastAPI)

### 6.1 Architecture Pattern

The backend follows a layered architecture:

```
Routers (API endpoints)
    |
    v
Services (Business logic)
    |
    v
Repositories (Database queries)
    |
    v
Models (SQLAlchemy ORM)
```

### 6.2 Directory Structure

```
backend/app/
├── main.py                  # FastAPI app creation, startup/shutdown events, APScheduler
├── config.py                # Settings via Pydantic BaseSettings + environment variables
├── database.py              # SQLAlchemy engine, SessionLocal factory, Base class
├── redis_client.py          # Redis connection pool for identity cache + pub/sub
├── models/                  # SQLAlchemy ORM models
│   ├── user.py              # Users table (student, faculty, admin roles)
│   ├── face_registration.py # Face registration records (user -> FAISS mapping)
│   ├── face_embedding.py    # Individual face embedding vectors
│   ├── room.py              # Classroom/room definitions with camera endpoints
│   ├── schedule.py          # Class schedules (subject, faculty, room, time)
│   ├── enrollment.py        # Student-to-schedule enrollment links
│   ├── attendance_record.py # Daily attendance records per student per class
│   ├── presence_log.py      # Per-scan presence detection logs
│   └── early_leave_event.py # Early leave detection events
├── schemas/                 # Pydantic request/response models
│   ├── auth.py              # Login, register, token schemas
│   ├── face.py              # Face registration schemas
│   ├── attendance.py        # Attendance record schemas
│   └── ...
├── routers/                 # FastAPI route handlers
│   ├── auth.py              # Authentication endpoints
│   ├── face.py              # Face registration endpoints
│   ├── attendance.py        # Attendance data endpoints
│   ├── presence.py          # Presence tracking endpoints
│   ├── schedules.py         # Schedule management endpoints
│   ├── rooms.py             # Room information endpoints
│   ├── users.py             # User profile endpoints
│   ├── notifications.py     # System notification endpoints
│   ├── websocket.py         # WebSocket connections (attendance + alerts)
│   └── health.py            # System health check endpoint
├── services/
│   ├── auth_service.py      # JWT generation, user authentication
│   ├── face_service.py      # Face registration + recognition logic
│   ├── attendance_engine.py # Frame grab -> detect -> recognize -> DB
│   ├── frame_grabber.py     # Persistent RTSP frame source via FFmpeg
│   ├── realtime_pipeline.py # Async session processing (10fps loop)
│   ├── realtime_tracker.py  # ByteTrack + ArcFace identity tracking
│   ├── track_presence_service.py  # Continuous time-based presence
│   ├── presence_service.py  # Legacy scan-based presence (every 15s)
│   ├── identity_cache.py    # Redis-backed identity lookup cache
│   └── ml/
│       ├── insightface_model.py  # SCRFD + ArcFace model wrapper
│       ├── faiss_manager.py      # FAISS index management
│       ├── face_quality.py       # Image quality gating
│       └── anti_spoof.py         # Anti-spoofing detection
├── repositories/            # Database query layer
│   ├── user_repository.py
│   ├── attendance_repository.py
│   ├── schedule_repository.py
│   └── ...
└── utils/
    ├── security.py          # JWT encoding/decoding, password hashing
    ├── dependencies.py      # FastAPI dependency injection
    └── exceptions.py        # Custom exception classes
```

### 6.3 Startup Sequence

When the FastAPI backend starts:

1. **APScheduler initializes** — schedules recurring jobs:
   - FAISS health check every 30 minutes
   - Session lifecycle manager every 30 seconds (starts/stops pipelines based on active schedules)
2. **Database connection** — SQLAlchemy engine connects to PostgreSQL
3. **Redis connection pool** — establishes connection to Redis for caching
4. **InsightFace model load** — downloads and loads buffalo_l model (~500MB on first run)
5. **FAISS index load** — loads or creates the face embedding index from disk
6. **FAISS reconciliation** — syncs database `face_registrations` with the FAISS index to ensure consistency
7. **WebSocket Redis subscriber** — listens for cross-worker broadcast messages
8. **Session pipeline maps** — empty at start, populated by the session lifecycle job as classes begin

### 6.4 Session Lifecycle Management

The backend automatically manages attendance tracking sessions:

1. Every 30 seconds, the scheduler checks which classes are currently active (based on `schedules` table)
2. For each active schedule that doesn't have a running pipeline:
   - Creates a `FrameGrabber` for the room's RTSP stream
   - Creates a `RealtimeTracker` (ByteTrack + ArcFace)
   - Creates a `TrackPresenceService` (presence monitoring)
   - Starts the `SessionPipeline` async task (10fps processing loop)
3. When a class ends, the pipeline is stopped and resources are cleaned up
4. This is fully automatic — no manual intervention from faculty is needed

### 6.5 Frame Grabber

The `FrameGrabber` maintains a persistent FFmpeg subprocess:
- **Input:** RTSP stream URL from mediamtx
- **Output:** Raw BGR frames at 480x360 resolution, 10fps
- **FFmpeg command:** `ffmpeg -i rtsp://... -f rawvideo -pixel_format bgr24 -s 480x360 -r 10 -`
- A daemon thread continuously drains FFmpeg's stdout, keeping only the latest frame
- Staleness detection: if no new frame arrives for 30 seconds, the subprocess is killed and restarted
- Thread-safe: `.grab()` returns a copy of the latest frame

### 6.6 Realtime Tracker

The `RealtimeTracker` combines detection and tracking:
- Runs SCRFD face detection on every frame
- ByteTrack associates detections to persistent tracks
- For new tracks: runs ArcFace embedding + FAISS search
- For known tracks: reuses cached identity (name, user_id, confidence)
- Re-verifies identity every 15 seconds
- Outputs `TrackFrame` objects with normalized bounding boxes (0-1 range)

Performance: approximately 15ms per frame on a modern server, sustaining 10fps processing.

### 6.7 Identity Cache (Redis)

To avoid redundant database lookups, recognized identities are cached in Redis:
- Key: user_id -> user name + metadata
- TTL: session duration
- Redis pub/sub notifies all Uvicorn workers when the FAISS index changes

---

## 7. Android Mobile Application

### 7.1 Architecture

The Android app is built with **Kotlin** and **Jetpack Compose**, following modern Android development practices:
- **Single Activity architecture** — `MainActivity` hosts all Compose screens
- **Hilt dependency injection** — centralized dependency management
- **MVVM pattern** — ViewModels manage screen state
- **Material 3 monochrome theme** — consistent, institution-appropriate UI

### 7.2 App Structure

```
android/app/src/main/java/com/iams/app/
├── IAMSApplication.kt              # @HiltAndroidApp entry point
├── MainActivity.kt                 # @AndroidEntryPoint single activity
├── di/
│   └── NetworkModule.kt            # Hilt module: Retrofit, OkHttp, ApiService
├── data/
│   ├── api/
│   │   ├── ApiService.kt           # Retrofit interface (all API endpoints)
│   │   ├── AuthInterceptor.kt      # Adds Bearer token to all requests
│   │   ├── TokenAuthenticator.kt   # Refreshes token on 401 responses
│   │   ├── TokenManager.kt         # DataStore-based secure token storage
│   │   └── AttendanceWebSocketClient.kt  # OkHttp WebSocket for real-time
│   └── model/
│       └── Models.kt               # All Kotlin data classes
└── ui/
    ├── theme/                       # Material 3 monochrome color scheme
    ├── navigation/                  # Routes, NavHost, NavViewModel
    ├── components/
    │   ├── RtspVideoPlayer.kt       # ExoPlayer RTSP composable
    │   ├── NativeWebRtcVideoPlayer.kt  # WebRTC WHEP video player
    │   ├── FaceDetectionProcessor.kt   # ML Kit TextureView processor
    │   ├── FaceOverlay.kt           # Canvas overlay for face bounding boxes
    │   ├── HybridFaceOverlay.kt     # ML Kit boxes + WebSocket name matching
    │   ├── FaceCaptureView.kt       # CameraX face registration capture
    │   ├── IAMSBottomBar.kt         # Bottom navigation bar
    │   └── IAMSHeader.kt            # Top app bar
    ├── auth/
    │   ├── LoginScreen.kt           # Student/Faculty login
    │   ├── RegisterScreen.kt        # 4-step student registration
    │   └── ...
    ├── student/
    │   ├── StudentHomeScreen.kt     # Dashboard
    │   ├── StudentScheduleScreen.kt # Class schedule
    │   ├── StudentHistoryScreen.kt  # Attendance history
    │   ├── StudentAnalyticsScreen.kt # Analytics charts
    │   └── StudentProfileScreen.kt  # Profile management
    └── faculty/
        ├── FacultyHomeScreen.kt     # Dashboard
        ├── FacultyLiveFeedScreen.kt # Live CCTV + attendance (crown jewel)
        ├── FacultyScheduleScreen.kt # Class schedule
        ├── FacultyAlertsScreen.kt   # Early leave alerts
        └── FacultyProfileScreen.kt  # Profile management
```

### 7.3 Navigation Structure

```
Splash Screen
    |
    v
Onboarding (first launch)
    |
    v
Welcome Screen
    |
    +---> Student Login ---> Student Tabs (Home, Schedule, History, Profile)
    |
    +---> Faculty Login ---> Faculty Tabs (Home, Schedule, Analytics, Alerts, Profile)
```

### 7.4 Key Screens

#### Faculty Live Feed Screen (Crown Jewel)
This is the most complex and important screen in the application:
- **Video layer:** NativeWebRtcVideoPlayer streams live CCTV via WHEP (WebRTC)
- **Detection layer:** ML Kit processes video frames at 30fps, drawing real-time face bounding boxes
- **Recognition layer:** WebSocket receives backend recognition results (names, confidence scores)
- **Overlay matching:** HybridFaceOverlay matches ML Kit boxes to WebSocket detections using IoU (Intersection over Union)
- **Attendance panel:** Shows real-time present/absent count, list of detected students

#### Face Registration Screen
- Uses CameraX to capture front-facing camera images
- ML Kit detects face in real-time, shows guide overlay
- Captures 3-5 images at different angles
- Uploads to backend for processing
- Shows registration status and completion

### 7.5 Data Layer

#### API Client (Retrofit)
- Base URL configurable per environment
- `AuthInterceptor` automatically adds `Authorization: Bearer <token>` to all requests
- `TokenAuthenticator` intercepts 401 responses and attempts token refresh
- `TokenManager` persists JWT tokens in Android DataStore (encrypted preferences)

#### WebSocket Client
- OkHttp-based WebSocket connection to `/api/v1/ws/attendance/{scheduleId}`
- Receives `frame_update` messages at 10fps with track data
- Receives `attendance_summary` messages every 5-10 seconds
- Automatic reconnection on disconnect

### 7.6 Build Configuration

- **Minimum SDK:** 26 (Android 8.0)
- **Target SDK:** 35 (Android 15)
- **JVM Target:** 17
- **Build system:** Gradle with Kotlin DSL

---

## 8. Database Design

### 8.1 Database Technology

- **Engine:** PostgreSQL 16 (Alpine-based Docker image)
- **Hosting:** Self-hosted in Docker — runs locally via Docker Desktop during development, and on the DigitalOcean VPS in production
- **ORM:** SQLAlchemy 2.0 (synchronous engine with psycopg2 driver)
- **Initialization:** Schema created via `init.sql` and seeded via `seed.sql`, both mounted into the PostgreSQL container at startup
- **Persistence:** Data stored in a Docker named volume (`postgres_data`) that survives container restarts

### 8.2 Entity Relationship Overview

```
users (1) ----< (many) face_registrations
users (1) ----< (many) face_embeddings
users (1) ----< (many) enrollments
users (1) ----< (many) attendance_records
users (1) ----< (many) early_leave_events
users (1) ----< (many) notifications

schedules (1) ----< (many) enrollments
schedules (1) ----< (many) attendance_records
schedules (1) >---- (1) rooms
schedules (1) >---- (1) users [faculty]

attendance_records (1) ----< (many) presence_logs
```

### 8.3 Core Tables

#### `users`
The central user table for all system actors.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| email | VARCHAR | Unique email address |
| hashed_password | VARCHAR | Bcrypt-hashed password |
| first_name | VARCHAR | User's first name |
| last_name | VARCHAR | User's last name |
| role | ENUM | 'student', 'faculty', or 'admin' |
| student_id | VARCHAR | Unique student ID (nullable for faculty) |
| course | VARCHAR | Academic program (e.g., "BSCpE") |
| year_level | INTEGER | Year level (1-4) |
| section | VARCHAR | Section letter |
| is_active | BOOLEAN | Account active flag |
| email_verified | BOOLEAN | Email verification status |
| email_verified_at | TIMESTAMP | When email was verified |
| created_at | TIMESTAMP | Account creation time |
| updated_at | TIMESTAMP | Last modification time |

#### `face_registrations`
Links a user to their position in the FAISS index.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| user_id | UUID | FK to users |
| embedding_id | INTEGER | Position in FAISS index |
| embedding_vector | BYTEA | Raw 512-dim embedding stored as bytes |
| is_active | BOOLEAN | Active registration flag |
| created_at | TIMESTAMP | Registration time |

#### `face_embeddings`
Stores individual face embedding vectors (one per captured image).

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| user_id | UUID | FK to users |
| embedding | BYTEA | 512-dimensional float vector as bytes |
| quality_score | FLOAT | Image quality score |
| created_at | TIMESTAMP | Capture time |

#### `rooms`
Defines classroom locations with associated camera streams.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| name | VARCHAR | Room name (e.g., "EB226") |
| building | VARCHAR | Building name |
| floor | INTEGER | Floor number |
| camera_endpoint | VARCHAR | RTSP URL for the camera |
| stream_key | VARCHAR | mediamtx path identifier |
| is_active | BOOLEAN | Room availability flag |

#### `schedules`
Defines class sessions with time, location, and faculty assignments.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| subject_code | VARCHAR | Subject code (e.g., "CPE401") |
| subject_name | VARCHAR | Subject name |
| faculty_id | UUID | FK to users (faculty) |
| room_id | UUID | FK to rooms |
| day_of_week | INTEGER | 0=Monday through 6=Sunday |
| start_time | TIME | Class start time |
| end_time | TIME | Class end time |
| target_course | VARCHAR | For auto-enrollment (e.g., "BSCpE") |
| target_year_level | INTEGER | For auto-enrollment |
| is_active | BOOLEAN | Schedule active flag |

#### `enrollments`
Links students to their class schedules.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| student_id | UUID | FK to users (student) |
| schedule_id | UUID | FK to schedules |
| enrolled_at | TIMESTAMP | Enrollment time |
| **Unique constraint** | | (student_id, schedule_id) |

#### `attendance_records`
Stores daily attendance results per student per class.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| student_id | UUID | FK to users |
| schedule_id | UUID | FK to schedules |
| date | DATE | Attendance date |
| status | ENUM | PRESENT, LATE, ABSENT, EARLY_LEAVE, EXCUSED |
| check_in_time | TIMESTAMP | First detection time |
| check_out_time | TIMESTAMP | Last detection time |
| presence_score | FLOAT | Percentage of scans where student was detected (0-100) |
| total_scans | INTEGER | Total number of scans during the class |
| scans_present | INTEGER | Number of scans where student was detected |
| **Unique constraint** | | (student_id, schedule_id, date) |

#### `presence_logs`
Granular per-scan detection records.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| attendance_record_id | UUID | FK to attendance_records |
| scan_number | INTEGER | Sequential scan number |
| scan_time | TIMESTAMP | When the scan occurred |
| detected | BOOLEAN | Was the student detected? |
| confidence | FLOAT | Recognition confidence score |

#### `early_leave_events`
Records when a student leaves class early.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| student_id | UUID | FK to users |
| schedule_id | UUID | FK to schedules |
| detected_at | TIMESTAMP | When early leave was detected |
| severity | VARCHAR | 'high', 'medium', or 'low' |
| resolved_at | TIMESTAMP | When student returned (nullable) |

### 8.4 Additional Tables

| Table | Purpose |
|-------|---------|
| `notifications` | System notification messages |
| `notification_preferences` | Per-user notification settings |
| `refresh_tokens` | JWT refresh token tracking for invalidation |
| `system_settings` | Global configuration key-value store |
| `student_record` | Extended student profile information |
| `faculty_record` | Extended faculty profile information |

---

## 9. Real-Time Communication (WebSocket)

### 9.1 WebSocket Endpoints

The system provides two WebSocket endpoints for real-time data:

| Endpoint | Purpose |
|----------|---------|
| `/api/v1/ws/attendance/{scheduleId}` | Real-time attendance tracking for a specific class session |
| `/api/v1/ws/alerts/{userId}` | Real-time alerts for a specific user (faculty) |

### 9.2 Attendance WebSocket Protocol

The attendance WebSocket broadcasts multiple message types:

#### `frame_update` (10fps)
Sent at the processing frame rate, contains current tracking data:
```json
{
  "type": "frame_update",
  "timestamp": 1711789200.5,
  "tracks": [
    {
      "track_id": 1,
      "bbox": [0.15, 0.20, 0.35, 0.60],
      "name": "Juan Dela Cruz",
      "user_id": "550e8400-e29b-41d4-a716-446655440000",
      "confidence": 0.92,
      "status": "recognized"
    },
    {
      "track_id": 2,
      "bbox": [0.50, 0.25, 0.70, 0.65],
      "name": null,
      "user_id": null,
      "confidence": 0.0,
      "status": "detecting"
    }
  ],
  "fps": 10.2,
  "processing_ms": 15.3
}
```

- `bbox` coordinates are **normalized to 0-1 range** (x1, y1, x2, y2)
- The Android app matches these to ML Kit detections using IoU (Intersection over Union)

#### `attendance_summary` (every 5-10 seconds)
Periodic summary of the current attendance state:
```json
{
  "type": "attendance_summary",
  "schedule_id": "550e8400-e29b-41d4-a716-446655440000",
  "present_count": 25,
  "total_enrolled": 45,
  "absent": ["Maria Torres", "Pedro Santos"],
  "late": ["Juan Dela Cruz"],
  "early_leave": ["Ana Reyes"]
}
```

#### `check_in`
Sent when a student is first detected:
```json
{
  "type": "check_in",
  "student_name": "Juan Dela Cruz",
  "user_id": "uuid",
  "time": "2026-03-30T08:05:23Z"
}
```

#### `early_leave`
Sent when a student has been absent for more than the threshold:
```json
{
  "type": "early_leave",
  "student_name": "Ana Reyes",
  "user_id": "uuid",
  "absent_since": "2026-03-30T09:15:00Z",
  "severity": "high"
}
```

#### `early_leave_return`
Sent when a previously flagged student returns:
```json
{
  "type": "early_leave_return",
  "student_name": "Ana Reyes",
  "user_id": "uuid",
  "returned_at": "2026-03-30T09:20:00Z"
}
```

### 9.3 Multi-Worker Support

In production, multiple Uvicorn workers may be running. WebSocket broadcasts use Redis pub/sub to ensure all connected clients (regardless of which worker they're connected to) receive the same messages.

---

## 10. Media Streaming Architecture

### 10.1 mediamtx

mediamtx is a real-time media server that handles RTSP ingestion and WebRTC delivery. It sits at the center of the video delivery pipeline.

**Ports:**
| Port | Protocol | Purpose |
|------|----------|---------|
| 8554 | RTSP | Receives streams from RPi (publish) and serves to backend (read) |
| 8889 | HTTP | WHEP endpoint for WebRTC delivery to Android app |
| 9997 | HTTP | Internal API for stream management |

**Stream Paths:**
| Path | Source | Description |
|------|--------|-------------|
| `eb226/raw` | RPi relay | Raw Reolink camera feed for EB226 |
| `eb227/raw` | RPi relay | Raw Reolink camera feed for EB227 |
| `eb226` | Backend/general | Processed or direct access path |
| `eb227` | Backend/general | Processed or direct access path |

### 10.2 Video Flow: Camera to Phone

```
Camera (RTSP H.264)
    |
    v
RPi FFmpeg Relay (-c copy, no transcoding)
    |
    v
mediamtx (RTSP ingest on :8554)
    |
    +---> RTSP output ---> Backend FrameGrabber (480x360, 10fps for recognition)
    |
    +---> WHEP endpoint (:8889) ---> Android WebRTC Player (smooth HD video)
```

### 10.3 WebRTC (WHEP)

The Android app uses the **WHEP (WebRTC-HTTP Egress Protocol)** to receive video:
- The app sends an HTTP POST to `http://vps:8889/{stream_path}/whep`
- mediamtx responds with an SDP offer
- A WebRTC peer connection is established
- Video is delivered with sub-second latency

ICE servers for NAT traversal:
- **STUN:** `stun:stun.l.google.com:19302` (free Google STUN)
- **TURN:** coturn server on VPS (ports 3478 UDP, 49152-49200)

### 10.4 coturn (TURN Server)

coturn handles NAT traversal for WebRTC when direct peer-to-peer connections fail:
- Required when the Android phone is behind a restrictive NAT/firewall
- Relays media through the VPS
- UDP ports 3478 (signaling) and 49152-49200 (media relay range)

---

## 11. Continuous Presence Tracking and Attendance Logic

### 11.1 How Attendance is Tracked

IAMS uses **continuous presence tracking** rather than a single check-in:

1. **Session starts** — when a scheduled class begins, the backend starts processing CCTV frames
2. **Every frame (10fps)** — faces are detected and tracked using ByteTrack
3. **Per-track identity** — new faces are recognized via ArcFace + FAISS; known tracks reuse cached identity
4. **Presence timers** — each recognized student has a running timer tracking how long they've been visible
5. **Absence detection** — if a student hasn't been seen for more than 60 seconds, an early-leave event is triggered
6. **Database writes** — presence data is flushed to the database every 10 seconds (buffered for performance)
7. **Session ends** — when the class ends, final attendance records are computed

### 11.2 Attendance Status Determination

| Status | Condition |
|--------|-----------|
| **PRESENT** | Student detected within the first few minutes; presence score >= threshold |
| **LATE** | Student detected but check-in time is past the grace period |
| **ABSENT** | Student never detected during the class session |
| **EARLY_LEAVE** | Student was present but left before class ended (absent > 60s, not returned) |
| **EXCUSED** | Manually set by faculty |

### 11.3 Presence Score

The **presence score** quantifies how consistently a student was present:

```
Presence Score = (total_time_present / total_session_duration) x 100%
```

- A score of 100% means the student was visible in every processed frame
- A score of 60% means the student was visible for 60% of the class duration
- The score accounts for brief absences (e.g., bathroom breaks) that don't trigger early-leave

### 11.4 Early Leave Detection

The system uses time-based detection:
- If a tracked student hasn't been seen for more than **60 seconds** (configurable), an early-leave event is generated
- The event includes a **severity** level:
  - **High** — student left in the first half of class
  - **Medium** — student left in the second half
  - **Low** — student left near the end of class
- If the student returns, the event is resolved and a `early_leave_return` WebSocket message is sent
- Faculty receive alerts via the `/api/v1/ws/alerts/{userId}` WebSocket

### 11.5 Legacy Scan-Based System

The original implementation used 15-second interval scans:
- Every 15 seconds, the backend grabs a frame and processes it
- 3 consecutive missed scans (45 seconds) triggers early-leave
- This system is retained for backward compatibility but superseded by the continuous tracker

---

## 12. Security and Anti-Spoofing

### 12.1 Authentication

- **JWT (JSON Web Tokens)** with HS256 signing
- **Access tokens** — 30-minute expiry
- **Refresh tokens** — longer expiry, stored in database for invalidation
- **Token refresh** — automatic on 401 response via `TokenAuthenticator` in Android app
- **Password hashing** — Bcrypt

### 12.2 API Security

- **Rate limiting** — via slowapi (e.g., 10 registration requests per minute)
- **CORS** — configured to allow only authorized origins
- **Input validation** — Pydantic models validate all request data
- **SQL injection prevention** — SQLAlchemy ORM parameterizes all queries
- **Bearer token authentication** — all API endpoints require valid JWT

### 12.3 Anti-Spoofing Measures

During face registration, the system performs several checks to prevent photo-based attacks:

#### Embedding Variance Check
- Compares the cosine distance between embeddings from different angles
- If all images produce nearly identical embeddings (variance < 0.1), it's likely a flat photo being re-photographed
- Real faces show natural variation across angles

#### LBP (Local Binary Pattern) Texture Analysis
- Analyzes the texture pattern of the face region
- Printed photos and screens have different texture characteristics than real skin
- Threshold: texture uniformity <= 0.15

#### FFT (Fast Fourier Transform) Frequency Analysis
- Analyzes the frequency spectrum of the face image
- Screen displays and printed photos introduce characteristic high-frequency patterns
- Threshold: high-frequency energy <= 0.20

### 12.4 Image Quality Gating

Before any face embedding is generated, the image must pass quality checks:

| Check | Mobile Threshold | CCTV Threshold | Purpose |
|-------|-----------------|----------------|---------|
| Blur (Laplacian variance) | > 10 | > 100 | Reject blurry images |
| Brightness (mean pixel) | 40-220 | 40-220 | Reject too dark/bright |
| Face size (% of image) | >= 5% | >= 5% | Reject tiny/distant faces |
| Detection confidence | >= 0.5 | >= 0.5 | Reject uncertain detections |

---

## 13. Deployment and Production Environment

### 13.1 Production Infrastructure

The entire IAMS backend runs on a **DigitalOcean Droplet** (Virtual Private Server):

- **IP Address:** 167.71.217.44
- **OS:** Ubuntu Linux
- **Deployment:** Docker Compose
- **SSL:** Let's Encrypt certificates via Nginx

### 13.2 Docker Compose Services (Production)

| Service | Image | Purpose | Resource Limits |
|---------|-------|---------|-----------------|
| `api-gateway` | Custom FastAPI | Backend API + attendance engine | 1.5GB RAM, 1 CPU |
| `redis` | redis:7-alpine | Identity cache + pub/sub | 128MB RAM |
| `mediamtx` | bluenviern/mediamtx | RTSP ingest + WebRTC (WHEP) | - |
| `coturn` | coturn/coturn | TURN server for WebRTC NAT traversal | - |
| `postgres` | postgres:16-alpine | PostgreSQL database | - |
| `nginx` | nginx:alpine | Reverse proxy + SSL termination | - |
| `dozzle` | amir20/dozzle | Docker log viewer (admin) | - |
| `adminer` | adminer | Database admin UI (admin) | - |

### 13.3 Docker Compose Services (Local Development)

The local development stack mirrors production with hot-reload:

```yaml
services:
  postgres:     # Port 5432, persistent volume
  redis:        # Port 6379
  mediamtx:     # Ports 8554 (RTSP), 8889 (WHEP), 9997 (API)
  coturn:       # Ports 3478 (UDP), 49152-49200
  api-gateway:  # Port 8000, volume-mounted for hot reload
  dozzle:       # Port 9999
  adminer:      # Port 8080
```

**Hot reload:** The backend Python code is volume-mounted into the container. When you edit any Python file, uvicorn's watchfiles auto-restarts the server.

### 13.4 Nginx Configuration

Nginx acts as the front-facing reverse proxy:
- **Port 80** — HTTP (redirects to HTTPS)
- **Port 443** — HTTPS with Let's Encrypt SSL
- **Proxy rules:**
  - `/api/v1/*` → FastAPI backend (port 8000)
  - `/api/v1/ws/*` → WebSocket upgrade to FastAPI
  - `/admin/*` → Static React admin dashboard
- **WebSocket support** — upgrades `Connection: Upgrade` headers

### 13.5 Deployment Process

Deployments are executed via a shell script (`deploy/deploy.sh`):

```
1. rsync: Copy backend/, admin/, deploy/ configs to VPS
2. ssh: Connect to VPS
3. docker build: Build new api-gateway image
4. docker compose up -d: Start/restart services
5. Health check: GET /api/v1/health to verify deployment
```

### 13.6 Persistent Volumes

| Volume | Purpose |
|--------|---------|
| `postgres_data` | PostgreSQL database files |
| `faiss_data` | FAISS face embedding index |
| `face_uploads` | Backup copies of registered face images |

### 13.7 Environment Variables

The production server requires the following environment variables:

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string (e.g., `postgresql://admin:123@postgres:5432/iams`) |
| `JWT_SECRET_KEY` | Secret key for JWT token signing (HS256) |
| `REDIS_URL` | Redis connection URL (e.g., `redis://localhost:6379/0`) |
| `RESEND_API_KEY` | (Optional) Resend API key for email verification |

### 13.8 Network Architecture

```
Internet
    |
    v
DigitalOcean VPS (167.71.217.44)
    |
    +-- Nginx (:80, :443)
    |       |
    |       +---> api-gateway (:8000)  [FastAPI]
    |       +---> static files         [React Admin]
    |
    +-- mediamtx (:8554, :8889)
    |       |
    |       +---> RPi connects here (RTSP publish)
    |       +---> Android app connects here (WHEP)
    |       +---> Backend grabs frames here (RTSP read)
    |
    +-- coturn (:3478, :49152-49200)
    |       |
    |       +---> WebRTC TURN relay
    |
    +-- Redis (:6379, internal only)
    +-- PostgreSQL (:5432, internal Docker container)
```

---

## 14. API Endpoints Reference

### 14.1 Authentication

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/api/v1/auth/check-student-id` | Check if student ID exists in system | No |
| POST | `/api/v1/auth/verify-student-id` | Verify student ID + birthdate | No |
| POST | `/api/v1/auth/register` | Create student account (rate limited: 10/min) | No |
| POST | `/api/v1/auth/login` | Login with email + password, returns JWT | No |
| POST | `/api/v1/auth/refresh` | Refresh access token using refresh token | No |
| GET | `/api/v1/auth/me` | Get current user profile | Yes |
| POST | `/api/v1/auth/change-password` | Change password | Yes |
| POST | `/api/v1/auth/forgot-password` | Request password reset | No |
| POST | `/api/v1/auth/logout` | Invalidate refresh token | Yes |

### 14.2 Face Registration

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/api/v1/face/register` | Upload 3-5 face images for registration | Yes |
| POST | `/api/v1/face/reregister` | Update existing face registration | Yes |
| GET | `/api/v1/face/status` | Check face registration status | Yes |

### 14.3 Schedules

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/api/v1/schedules/` | List all schedules | Yes |
| GET | `/api/v1/schedules/me` | Get current user's schedules | Yes |
| GET | `/api/v1/schedules/{id}` | Get schedule details | Yes |
| GET | `/api/v1/schedules/active-at/{time}` | Get schedules active at given time | Yes |

### 14.4 Attendance

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/api/v1/attendance/me` | Student's attendance history | Yes |
| GET | `/api/v1/attendance/me/summary` | Student's overall attendance summary | Yes |
| GET | `/api/v1/attendance/today/{scheduleId}` | Today's attendance for a class | Yes |
| GET | `/api/v1/attendance/live/{scheduleId}` | Real-time attendance state | Yes |
| GET | `/api/v1/attendance/schedule/{scheduleId}/summary` | Class attendance summary | Yes |
| GET | `/api/v1/attendance/{id}` | Specific attendance record | Yes |
| GET | `/api/v1/attendance/{id}/presence-logs` | Detailed scan logs for a record | Yes |
| GET | `/api/v1/attendance/alerts` | Student's early-leave alerts | Yes |

### 14.5 Presence

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/api/v1/presence/session/{scheduleId}` | Current session state | Yes |
| POST | `/api/v1/presence/scan` | Trigger manual scan (admin only) | Yes (Admin) |
| GET | `/api/v1/presence/check/{studentId}/{scheduleId}` | Check student's current status | Yes |

### 14.6 Other Endpoints

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/api/v1/rooms/` | List all rooms | Yes |
| GET | `/api/v1/rooms/{id}` | Room details | Yes |
| GET | `/api/v1/users/{userId}` | User profile | Yes |
| GET | `/api/v1/health` | System health check | No |

### 14.7 WebSocket

| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/ws/attendance/{scheduleId}` | Real-time attendance stream (frame_update, attendance_summary, check_in, early_leave) |
| `GET /api/v1/ws/alerts/{userId}` | Real-time alerts for faculty (early-leave notifications) |

---

## 15. User Flows

### 15.1 Student Registration Flow

```
Step 1: Verify Student ID
    Student enters their student ID number
    System checks it against the pre-loaded student records
    If valid, returns student details for confirmation

Step 2: Create Account
    Student fills in email and password
    System creates account in database
    Email verification is sent (optional, via Resend)

Step 3: Email Verification
    Student clicks verification link in email
    Account is marked as email_verified

Step 4: Face Registration
    Student opens face registration screen
    CameraX activates front camera
    ML Kit guides student to position face correctly
    Student captures 3-5 images at different angles:
        - Front facing
        - Slight left turn
        - Slight right turn
        - Slight tilt up
        - Slight tilt down
    Images uploaded to backend
    Backend processes: SCRFD detect → quality gate → anti-spoof → ArcFace embed → FAISS store
    Registration confirmed

Step 5: Ready
    Student can now be automatically recognized in CCTV-monitored classrooms
```

### 15.2 Faculty Daily Flow

```
1. Faculty opens app → sees today's class schedule
2. When class is in session, tap "Live Feed"
3. Live Feed screen shows:
    - Real-time CCTV video (WebRTC, smooth HD)
    - ML Kit face bounding boxes (30fps, instant)
    - Recognized student names overlaid on boxes (from backend via WebSocket)
    - Attendance panel: present count / total enrolled
    - List of detected students with check-in times
    - Alert indicators for early-leave events
4. After class, view attendance reports/analytics
5. Early-leave alerts received in real-time via push notification
```

### 15.3 Automatic Attendance Flow (No User Interaction)

```
1. Schedule lifecycle manager detects class starting (checks every 30 seconds)
2. Creates SessionPipeline for the classroom's camera
3. FrameGrabber starts reading RTSP stream from mediamtx
4. For each frame (10fps):
    a. SCRFD detects all faces
    b. ByteTrack associates detections to tracks
    c. New tracks: ArcFace embed → FAISS search → identity assigned
    d. Known tracks: cached identity reused
5. TrackPresenceService maintains running timers per student
6. Every 10 seconds: flush presence data to database
7. WebSocket broadcasts frame_update (10fps) and attendance_summary (5-10s)
8. Early-leave detected when student absent > 60 seconds
9. Class ends → pipeline stopped → final attendance records computed
```

---

## 16. System Configuration Parameters

### 16.1 Face Recognition Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| `INSIGHTFACE_MODEL` | `buffalo_l` | InsightFace model package (~500MB) |
| `INSIGHTFACE_DET_SIZE` | 480 | SCRFD detection input size (pixels) |
| `INSIGHTFACE_DET_THRESH` | 0.5 | Minimum detection confidence |
| `RECOGNITION_THRESHOLD` | 0.25 | Minimum cosine similarity for a match |
| `RECOGNITION_MARGIN` | 0.05 | Required gap between top-1 and top-2 match |
| `RECOGNITION_TOP_K` | 3 | Number of nearest neighbors to retrieve |
| `MIN_FACE_IMAGES` | 3 | Minimum images for registration |
| `MAX_FACE_IMAGES` | 5 | Maximum images for registration |

### 16.2 Image Quality Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| `QUALITY_BLUR_THRESHOLD` | 100 | Laplacian variance minimum (CCTV) |
| `QUALITY_BLUR_THRESHOLD_MOBILE` | 10 | Laplacian variance minimum (mobile selfie) |
| `QUALITY_BRIGHTNESS_MIN` | 40 | Minimum mean pixel brightness |
| `QUALITY_BRIGHTNESS_MAX` | 220 | Maximum mean pixel brightness |
| `QUALITY_MIN_FACE_SIZE_RATIO` | 0.05 | Minimum face area as fraction of image |

### 16.3 Tracking and Presence Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| `PROCESSING_FPS` | 10 | Backend frame processing rate |
| `WS_BROADCAST_FPS` | 10 | WebSocket message broadcast rate |
| `TRACK_LOST_TIMEOUT` | 5s | ByteTrack lost-track buffer |
| `REVERIFY_INTERVAL` | 15s | Re-run ArcFace on known tracks |
| `TRACK_CONFIRM_FRAMES` | 1 | Frames before recognizing new track |
| `EARLY_LEAVE_TIMEOUT` | 60s | Absence duration before early-leave alert |
| `PRESENCE_FLUSH_INTERVAL` | 10s | Buffered database write interval |

### 16.4 Frame Grabber Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| `FRAME_GRABBER_FPS` | 10 | Frame capture rate |
| `FRAME_GRABBER_WIDTH` | 480 | Frame width (pixels) |
| `FRAME_GRABBER_HEIGHT` | 360 | Frame height (pixels) |

### 16.5 Adaptive Threshold Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| `ADAPTIVE_THRESHOLD_ENABLED` | True | Enable automatic threshold adjustment |
| `ADAPTIVE_THRESHOLD_FLOOR` | 0.35 | Minimum threshold value |
| `ADAPTIVE_THRESHOLD_CEILING` | 0.30 | Cross-domain (selfie→CCTV) ceiling |
| `ADAPTIVE_THRESHOLD_MIN_SAMPLES` | 50 | Minimum matches before adjusting |
| `ADAPTIVE_THRESHOLD_WINDOW` | 500 | Rolling window of recent matches |

---

## 17. Hardware Requirements

### 17.1 IP Camera

| Specification | Requirement |
|---------------|-------------|
| **Model** | Reolink (or equivalent with RTSP support) |
| **Protocol** | RTSP with H.264 encoding |
| **Resolution** | 1080p or higher recommended |
| **Mounting** | Ceiling-mounted, covering the entire classroom |
| **Network** | Wired Ethernet or WiFi on campus LAN |

### 17.2 Raspberry Pi (Edge Device)

| Specification | Requirement |
|---------------|-------------|
| **Model** | Raspberry Pi 4 or 5 |
| **RAM** | 2GB minimum (FFmpeg relay only) |
| **Storage** | 16GB microSD |
| **Network** | WiFi (same LAN as camera) + internet access |
| **OS** | Raspberry Pi OS Lite |
| **Software** | Python 3, FFmpeg |
| **Power** | USB-C power supply, always-on |

### 17.3 Cloud Server (VPS)

| Specification | Requirement |
|---------------|-------------|
| **Provider** | DigitalOcean (or equivalent) |
| **CPU** | 2+ vCPUs recommended |
| **RAM** | 4GB minimum (InsightFace model requires ~1.5GB) |
| **Storage** | 50GB SSD |
| **Network** | Public IP, ports 80/443/8554/8889/3478 open |
| **OS** | Ubuntu 22.04 or later |
| **Software** | Docker, Docker Compose |

### 17.4 Android Device (Student/Faculty)

| Specification | Requirement |
|---------------|-------------|
| **OS** | Android 8.0 (API 26) or higher |
| **Camera** | Front-facing camera (for face registration) |
| **Network** | WiFi or mobile data |
| **RAM** | 3GB+ recommended (for ML Kit + video playback) |

---

## 18. Software Dependencies

### 18.1 Backend Python Dependencies

```
# ===== Core Framework =====
fastapi==0.128.0          # Async web framework
uvicorn==0.40.0           # ASGI server
sqlalchemy==2.0.46        # ORM for PostgreSQL
pydantic==2.12.5          # Data validation
pydantic-settings==2.12.0 # Settings management via env vars
alembic==1.18.3           # Database migration tool
python-multipart==0.0.22  # Multipart file uploads
python-dotenv==1.2.1      # .env file loading

# ===== Database =====
psycopg2-binary==2.9.11   # PostgreSQL driver
greenlet==3.3.1           # SQLAlchemy async support

# ===== Authentication & Security =====
python-jose==3.5.0        # JWT token encoding/decoding
passlib==1.7.4            # Password hashing (bcrypt)
bcrypt==4.0.1             # Bcrypt backend
email-validator==2.3.0    # Email format validation
slowapi>=0.1.9            # API rate limiting

# ===== ML / Face Recognition =====
insightface>=0.7.3        # SCRFD + ArcFace models
onnxruntime>=1.21.0       # Neural network inference
faiss-cpu==1.13.2         # Vector similarity search (FAISS)
numpy==2.4.2              # Numerical computing
pillow==12.1.0            # Image processing (PIL)
opencv-python-headless==4.13.0.90  # Computer vision (no GUI)
supervision>=0.24.0       # ByteTrack multi-object tracking

# ===== Redis =====
redis[hiredis]>=5.0.0     # Redis client with C parser

# ===== HTTP / Networking =====
httpx==0.28.1             # Async HTTP client
websockets==16.0          # WebSocket support
aiofiles>=24.0.0          # Async file I/O

# ===== Scheduling =====
apscheduler==3.10.4       # Background job scheduler

# ===== Utilities =====
watchfiles==1.1.1         # Hot reload for development

# ===== Testing =====
pytest==9.0.2             # Test framework
pytest-asyncio==1.3.0     # Async test support

# ===== Linting & Type Checking =====
ruff>=0.8.0               # Python linter and formatter
mypy>=1.13.0              # Static type checker
```

### 18.2 Android App Dependencies (Key Libraries)

```
// Compose & UI
androidx.compose.material3     # Material 3 design
androidx.navigation.compose    # Navigation

// Video & Camera
androidx.media3:exoplayer      # Video playback (RTSP)
androidx.camera:camera-core    # CameraX for face registration
io.github.nichetoolkit:stream-webrtc-android  # WebRTC

// Face Detection
com.google.mlkit:face-detection  # ML Kit on-device

// Networking
com.squareup.retrofit2         # REST API client
com.squareup.okhttp3           # HTTP + WebSocket
com.google.code.gson           # JSON serialization

// DI & Architecture
com.google.dagger:hilt-android  # Dependency injection
androidx.datastore              # Token persistence

// Image & Animation
io.coil-kt:coil-compose        # Image loading
com.airbnb.android:lottie-compose  # Animations
```

---

## Summary

IAMS is a comprehensive, multi-component system that combines edge computing (Raspberry Pi), cloud AI (InsightFace, FAISS, ByteTrack), real-time streaming (mediamtx, WebRTC), and a native Android application to deliver automated, continuous, and fraud-resistant attendance monitoring for academic institutions.

The system's three-tier independence (video delivery, face detection, attendance tracking) ensures reliability, while the combination of server-side AI and on-device ML Kit provides both accurate recognition and responsive user experience. The continuous presence tracking with early-leave detection goes beyond traditional attendance systems, providing comprehensive classroom monitoring.

**Key differentiators:**
1. Fully automated — no manual roll call or check-in required
2. Continuous monitoring — not just check-in, but throughout the entire class
3. Anti-spoofing — prevents photo-based attendance fraud
4. Real-time visibility — faculty see live attendance on their phone
5. Early-leave detection — alerts when students leave class prematurely
6. Cross-domain matching — selfie registration works with CCTV recognition
